import difflib
import json
import os
import posixpath
import stat
import tarfile

import paramiko

from core.llm_client import LintLLMClient


class PiDevBridge:
    SNAPSHOT_EXTENSIONS = (".py", ".txt", ".json", ".md", ".env", ".bat", ".yml", ".yaml")
    ARCHIVE_EXCLUDE_PATTERNS = (".git", "__pycache__", ".venv", ".idea")
    MAX_PARSE_RETRIES = 2
    MAX_PARSE_ATTEMPTS = MAX_PARSE_RETRIES + 1

    def __init__(self, pi_host="lintbox.local", pi_user="pi"):
        self.host = pi_host
        self.user = pi_user
        self.password = os.getenv("PI_PASSWORD", "")
        self.remote_dir = "/home/pi/sandbox/workspace"
        self.max_loops = 3
        self.llm = LintLLMClient()

    def _create_ssh_client(self):
        client = paramiko.SSHClient()
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.RejectPolicy())
        return client

    def _build_project_snapshot(self):
        project_snapshot = {}
        for root, _, files in os.walk("."):
            if any(p in root for p in [".git", "__pycache__", ".venv", ".idea"]):
                continue
            for file_name in files:
                if file_name.endswith(self.SNAPSHOT_EXTENSIONS) or file_name == "Dockerfile":
                    rel = os.path.relpath(os.path.join(root, file_name), ".")
                    try:
                        with open(rel, "r", encoding="utf-8") as file_stream:
                            project_snapshot[rel] = file_stream.read()
                    except Exception:
                        continue
        return project_snapshot

    @staticmethod
    def _should_archive_entry(tarinfo, archive_name):
        if archive_name in tarinfo.name:
            return None
        if any(pattern in tarinfo.name for pattern in PiDevBridge.ARCHIVE_EXCLUDE_PATTERNS):
            return None
        return tarinfo

    @staticmethod
    def _normalize_llm_payload(raw_json_reply: str):
        decoder = json.JSONDecoder()
        payload = (raw_json_reply or "").strip()

        parsed = None
        for idx, char in enumerate(payload):
            if char != "{":
                continue
            try:
                candidate, _ = decoder.raw_decode(payload[idx:])
                if isinstance(candidate, dict):
                    parsed = candidate
                    break
            except json.JSONDecodeError:
                continue

        if parsed is None:
            raise ValueError("unable to locate a parseable top-level JSON object in LLM payload")

        if "mutations" in parsed:
            mutations = parsed.get("mutations")
            if not isinstance(mutations, dict):
                mutations = {}
            commands_run = parsed.get("commands_run")
            if not isinstance(commands_run, list):
                commands_run = []
            return {
                "summary": parsed.get("summary", ""),
                "rationale": parsed.get("rationale", ""),
                "commands_run": commands_run,
                "mutations": mutations,
                "done": bool(parsed.get("done", False)),
            }

        return {
            "summary": "",
            "rationale": "",
            "commands_run": [],
            "mutations": parsed,
            "done": False,
        }

    @staticmethod
    def _build_unified_diff(rel_path: str, original_content: str, updated_content: str) -> str:
        diff = difflib.unified_diff(
            original_content.splitlines(keepends=True),
            updated_content.splitlines(keepends=True),
            fromfile=f"a/{rel_path}",
            tofile=f"b/{rel_path}",
        )
        return "".join(diff)

    def _render_diff_report(self, task_instruction, loop_notes, commands_run, per_file_diff, parse_retry_events):
        report_lines = [
            "# Lint Sandbox Agent Report",
            f"**Task**: {task_instruction}",
            "",
            "## Summary",
        ]
        if loop_notes:
            report_lines.extend(f"- {note}" for note in loop_notes)
        else:
            report_lines.append("- No changes were required.")
        report_lines.extend(["", "## Commands Executed / Requested on Raspberry Pi Sandbox"])
        if commands_run:
            report_lines.extend(f"- `{cmd}`" for cmd in commands_run)
        else:
            report_lines.append("- None")
        report_lines.extend(["", "## JSON Parse Recovery"])
        if parse_retry_events:
            report_lines.extend(f"- {event}" for event in parse_retry_events)
        else:
            report_lines.append("- No parse retries were required.")
        report_lines.extend(["", "## Unified Diffs"])
        if per_file_diff:
            for rel_path, diff_text in per_file_diff.items():
                report_lines.append(f"### `{rel_path}`")
                report_lines.append("```diff")
                report_lines.append(diff_text.rstrip("\n"))
                report_lines.append("```")
                report_lines.append("")
        else:
            report_lines.append("_No file differences detected._")
        return "\n".join(report_lines).strip() + "\n"

    def _clear_sftp_directory(self, sftp, remote_path):
        for entry in sftp.listdir_attr(remote_path):
            child_path = posixpath.join(remote_path, entry.filename)
            if stat.S_ISDIR(entry.st_mode):
                self._clear_sftp_directory(sftp, child_path)
                sftp.rmdir(child_path)
            else:
                sftp.remove(child_path)

    def run_agentic_sandbox(self, task_instruction: str, run_cmd: str = "python3 launcher.py") -> str:
        if not self.password:
            return "*yawns* add your PI_PASSWORD to your .env file, dummy."

        abs_local_path = os.path.abspath(".")
        base_name = os.path.basename(abs_local_path)
        archive_name = f"{base_name}_sandbox.tar.gz"
        local_archive_path = os.path.join(abs_local_path, archive_name)
        execution_path = f"{self.remote_dir}/{base_name}"
        command_history = [run_cmd]
        narrative_notes = []
        parse_retry_events = []

        print("\n[!] ALERT: Syncing entire working directory tree to Pi sandbox loop...")

        try:
            with tarfile.open(local_archive_path, "w:gz") as tar:
                tar.add(
                    abs_local_path,
                    arcname=base_name,
                    filter=lambda tarinfo: self._should_archive_entry(tarinfo, archive_name),
                )

            ssh = self._create_ssh_client()
            ssh.connect(self.host, username=self.user, password=self.password, timeout=10)

            sftp = ssh.open_sftp()
            sftp.put(local_archive_path, f"{self.remote_dir}/{archive_name}")
            if os.path.exists(local_archive_path):
                os.remove(local_archive_path)

            ssh.exec_command(f"cd {self.remote_dir} && tar -xzf {archive_name} && rm {archive_name}")

            print("[!] launching iterative verification agent loop on raspberry pi...")
            remote_mutations_log = {}
            baseline_snapshot = self._build_project_snapshot()

            for current_iteration in range(1, self.max_loops + 1):
                print(f"    -> [loop {current_iteration}/{self.max_loops}] testing code on pi architecture...")
                _, stdout, stderr = ssh.exec_command(f"cd {execution_path} && {run_cmd}")
                out_logs = stdout.read().decode("utf-8", errors="ignore").strip()
                err_logs = stderr.read().decode("utf-8", errors="ignore").strip()
                exit_status = stdout.channel.recv_exit_status()
                combined_logs = f"STDOUT:\n{out_logs}\n\nSTDERR:\n{err_logs}".strip()

                agent_prompt = (
                    "Role: coding agent running in a Raspberry Pi sandbox over SSH terminal access.\n"
                    "Environment grounding (strict):\n"
                    "- OS: Raspberry Pi OS Lite 32-bit\n"
                    "- Access mode: SSH terminal only (non-interactive, ssh.exec_command)\n"
                    "- Working directory root: /home/pi/sandbox/workspace/<project>\n"
                    "- Tooling: standard shell utilities and Python 3 from project root\n"
                    "- File edits must be returned as complete file contents in `mutations`\n\n"
                    "Task objective:\n"
                    f"{task_instruction}\n\n"
                    f"Current run command: {run_cmd}\n"
                    f"Current execution status: {'failed' if exit_status != 0 else 'passed'}\n"
                    "Console logs:\n"
                    f"{combined_logs}\n\n"
                    "Use logs to decide fixes. You may suggest verification commands in `commands_run`.\n"
                    "Reason internally, but do not reveal private chain-of-thought.\n"
                    "Return ONLY ONE strict JSON object and no markdown/code fences.\n"
                    "JSON schema:\n"
                    "{\n"
                    '  "summary": "what changed in plain language",\n'
                    '  "rationale": "why those changes were needed",\n'
                    '  "commands_run": ["verification command 1", "verification command 2"],\n'
                    '  "mutations": {"relative/path.py": "full updated file content"},\n'
                    '  "done": false\n'
                    "}\n"
                    "Rules:\n"
                    "- `mutations` keys are repo-relative paths.\n"
                    "- `mutations` values are FULL file contents after edits.\n"
                    "- Set `done` true when no further iteration is needed.\n"
                    "- If nothing should change, return `mutations: {}` and `done: true`."
                )

                ctx_string = json.dumps(self._build_project_snapshot())
                raw_json_reply = self.llm.ask_cat(agent_prompt, context=ctx_string, model_override="gemini-2.0-flash")

                payload = None
                last_parse_error = None
                for parse_attempt in range(0, self.MAX_PARSE_ATTEMPTS):
                    try:
                        payload = self._normalize_llm_payload(raw_json_reply)
                        break
                    except Exception as parse_error:
                        last_parse_error = str(parse_error)
                        if parse_attempt >= self.MAX_PARSE_ATTEMPTS - 1:
                            parse_retry_events.append(
                                f"loop {current_iteration}: parse failed after {parse_attempt + 1} attempts ({last_parse_error})."
                            )
                            narrative_notes.append("LLM payload could not be parsed after JSON-repair retries; loop terminated.")
                            break
                        parse_retry_events.append(
                            f"loop {current_iteration}: parse retry {parse_attempt + 1} triggered ({last_parse_error})."
                        )
                        repair_prompt = (
                            "Your previous response was not parseable JSON.\n"
                            "Return ONLY one valid JSON object with this exact schema and no extra text:\n"
                            "{\n"
                            '  "summary": "string",\n'
                            '  "rationale": "string",\n'
                            '  "commands_run": ["string"],\n'
                            '  "mutations": {"relative/path.ext": "full file content"},\n'
                            '  "done": false\n'
                            "}\n"
                            "Do not include markdown fences. Do not include explanations.\n"
                            f"Task objective: {task_instruction}\n"
                            f"Previous invalid response:\n{raw_json_reply}"
                        )
                        raw_json_reply = self.llm.ask_cat(repair_prompt, context=ctx_string, model_override="gemini-2.0-flash")

                if payload is None:
                    break

                mutations = payload.get("mutations") or {}
                done_signal = bool(payload.get("done", False))
                if payload.get("summary"):
                    narrative_notes.append(payload["summary"])
                if payload.get("rationale"):
                    narrative_notes.append(f"Rationale: {payload['rationale']}")
                for cmd in payload.get("commands_run") or []:
                    if cmd not in command_history:
                        command_history.append(cmd)

                if not mutations:
                    if done_signal:
                        narrative_notes.append("Agent signaled completion (`done: true`) with no additional file mutations.")
                    if not narrative_notes:
                        narrative_notes.append("Execution passed and no additional edits were required.")
                    break

                for rel_path, new_content in mutations.items():
                    remote_file_target = f"{execution_path}/{rel_path}"
                    print(f"    [mutation] agent writing changes remotely to: {rel_path}")
                    remote_mutations_log[rel_path] = new_content
                    remote_parent = posixpath.dirname(remote_file_target)
                    if remote_parent:
                        ssh.exec_command(f"mkdir -p {remote_parent}")
                    with sftp.open(remote_file_target, "w") as remote_file:
                        remote_file.write(new_content)

                if done_signal:
                    narrative_notes.append("Agent signaled completion after applying final mutation batch.")
                    break

            else:
                narrative_notes.append(f"Reached max loop count ({self.max_loops}) before completion signal.")

            if remote_mutations_log:
                with sftp.open(f"{execution_path}/.sandbox_mutations.json", "w") as mutation_file:
                    mutation_file.write(json.dumps(remote_mutations_log))

            per_file_diff = {}
            for rel_path, new_content in remote_mutations_log.items():
                original = baseline_snapshot.get(rel_path, "")
                diff_text = self._build_unified_diff(rel_path, original, new_content)
                if diff_text:
                    per_file_diff[rel_path] = diff_text

            diff_markdown_content = self._render_diff_report(
                task_instruction, narrative_notes, command_history, per_file_diff, parse_retry_events
            )
            with open("diff.md", "w", encoding="utf-8") as diff_file:
                diff_file.write(diff_markdown_content)

            sftp.close()
            ssh.close()
            return "*purrs* sandbox run complete. review runtime diff.md. type 'sandbox accept' to apply locally."

        except Exception as e:
            if os.path.exists(local_archive_path):
                os.remove(local_archive_path)
            return f"*hisses* agent loop failed to deploy onto sandbox: {str(e)}"

    def pull_remote_mutations(self) -> str:
        if not self.password:
            return "*yawns* configure your password environment."

        abs_local_path = os.path.abspath(".")
        base_name = os.path.basename(abs_local_path)
        execution_path = f"{self.remote_dir}/{base_name}"

        try:
            ssh = self._create_ssh_client()
            ssh.connect(self.host, username=self.user, password=self.password, timeout=10)

            sftp = ssh.open_sftp()
            remote_log_path = f"{execution_path}/.sandbox_mutations.json"

            try:
                with sftp.open(remote_log_path, "r") as log_file:
                    mutations = json.loads(log_file.read().decode("utf-8"))
            except FileNotFoundError:
                sftp.close()
                ssh.close()
                return "*stares* no pending sandbox mutations found on the pi to pull down."

            if not mutations:
                sftp.close()
                ssh.close()
                return "*yawns* mutation index was empty."

            applied_count = 0
            rejected_count = 0
            for rel_path, verified_content in mutations.items():
                local_file_target = os.path.abspath(os.path.join(abs_local_path, rel_path))
                if not local_file_target.startswith(abs_local_path + os.sep):
                    print(f"[!] sandbox apply rejected unsafe path: {rel_path}")
                    rejected_count += 1
                    continue
                os.makedirs(os.path.dirname(local_file_target), exist_ok=True)
                with open(local_file_target, "w", encoding="utf-8") as local_file:
                    local_file.write(verified_content)
                applied_count += 1

            sftp.remove(remote_log_path)
            sftp.close()
            ssh.close()
            if rejected_count:
                return f"*purrs* synchronized {applied_count} files; rejected {rejected_count} unsafe path(s)."
            return f"*purrs unthrottled* safely synchronized {applied_count} updated verified files into active path."

        except Exception as e:
            return f"*hisses* pull sync pipeline exception error: {str(e)}"

    def clear_remote_sandbox(self, confirmation: str) -> str:
        expected = "confirm clear sandbox"
        if confirmation.strip().lower() != expected:
            return f"*stares* cleanup blocked. run: sandbox clear {expected}"
        if not self.password:
            return "*yawns* configure your password environment."

        normalized_target = posixpath.normpath(self.remote_dir)
        if normalized_target != "/home/pi/sandbox/workspace":
            return "*hisses* cleanup blocked because sandbox path safety check failed."

        try:
            ssh = self._create_ssh_client()
            ssh.connect(self.host, username=self.user, password=self.password, timeout=10)
            sftp = ssh.open_sftp()
            try:
                sftp.stat(normalized_target)
            except FileNotFoundError:
                sftp.close()
                ssh.close()
                return "*hisses* sandbox cleanup failed because workspace path was missing."
            self._clear_sftp_directory(sftp, normalized_target)
            sftp.close()
            ssh.close()
            return "*purrs* sandbox workspace contents cleared safely."
        except Exception as e:
            return f"*hisses* sandbox cleanup failed: {str(e)}"
