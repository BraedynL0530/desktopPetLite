import difflib
import json
import os
import posixpath
import tarfile

import paramiko

from core.llm_client import LintLLMClient


class PiDevBridge:
    SNAPSHOT_EXTENSIONS = (".py", ".txt", ".json", ".md", ".env", ".bat", ".yml", ".yaml")

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
    def _normalize_llm_payload(raw_json_reply: str):
        payload = raw_json_reply.strip()
        if payload.startswith("```"):
            lines = payload.splitlines()
            if len(lines) >= 3:
                payload = "\n".join(lines[1:-1])
        parsed = json.loads(payload)
        if isinstance(parsed, dict) and "mutations" in parsed:
            return parsed
        if isinstance(parsed, dict):
            return {"mutations": parsed, "summary": "", "rationale": "", "commands_run": []}
        return {"mutations": {}, "summary": "", "rationale": "", "commands_run": []}

    @staticmethod
    def _build_unified_diff(rel_path: str, original_content: str, updated_content: str) -> str:
        diff = difflib.unified_diff(
            original_content.splitlines(keepends=True),
            updated_content.splitlines(keepends=True),
            fromfile=f"a/{rel_path}",
            tofile=f"b/{rel_path}",
        )
        return "".join(diff)

    def _render_diff_report(self, task_instruction, loop_notes, commands_run, per_file_diff):
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
        report_lines.extend(["", "## Commands Executed on Raspberry Pi Sandbox"])
        if commands_run:
            report_lines.extend(f"- `{cmd}`" for cmd in commands_run)
        else:
            report_lines.append("- None")
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

        print("\n[!] ALERT: Syncing entire working directory tree to Pi sandbox loop...")

        try:
            with tarfile.open(local_archive_path, "w:gz") as tar:
                tar.add(
                    abs_local_path,
                    arcname=base_name,
                    filter=lambda tarinfo: None if any(x in tarinfo.name for x in [".git", "__pycache__", ".venv", ".idea", archive_name]) else tarinfo,
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
                    "Role: coding agent running in a Raspberry Pi development sandbox.\n"
                    "Environment constraints:\n"
                    "- OS: Raspberry Pi Linux\n"
                    "- Project path: /home/pi/sandbox/workspace/<project>\n"
                    "- Prefer standard shell tools + Python 3\n"
                    "- Run checks using shell commands from project root when required\n\n"
                    "Task objective:\n"
                    f"{task_instruction}\n\n"
                    f"Current run command: {run_cmd}\n"
                    f"Current execution status: {'failed' if exit_status != 0 else 'passed'}\n"
                    "Console logs:\n"
                    f"{combined_logs}\n\n"
                    "Reason internally, but do not reveal private chain-of-thought.\n"
                    "Return ONLY strict JSON with this shape:\n"
                    "{\n"
                    '  "summary": "what changed in plain language",\n'
                    '  "rationale": "why those changes were needed",\n'
                    '  "commands_run": ["cmd1", "cmd2"],\n'
                    '  "mutations": {"relative/path.py": "full updated file content"}\n'
                    "}\n"
                    "If nothing should change, return an empty mutations object."
                )

                ctx_string = json.dumps(self._build_project_snapshot())
                raw_json_reply = self.llm.ask_cat(agent_prompt, context=ctx_string, model_override="gemini-2.0-flash")

                try:
                    payload = self._normalize_llm_payload(raw_json_reply)
                except Exception:
                    narrative_notes.append("LLM returned an unparseable payload; loop terminated.")
                    break

                mutations = payload.get("mutations") or {}
                if payload.get("summary"):
                    narrative_notes.append(payload["summary"])
                if payload.get("rationale"):
                    narrative_notes.append(f"Rationale: {payload['rationale']}")
                for cmd in payload.get("commands_run") or []:
                    if cmd not in command_history:
                        command_history.append(cmd)

                if not mutations:
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

            if remote_mutations_log:
                with sftp.open(f"{execution_path}/.sandbox_mutations.json", "w") as mutation_file:
                    mutation_file.write(json.dumps(remote_mutations_log))

            per_file_diff = {}
            for rel_path, new_content in remote_mutations_log.items():
                original = baseline_snapshot.get(rel_path, "")
                diff_text = self._build_unified_diff(rel_path, original, new_content)
                if diff_text:
                    per_file_diff[rel_path] = diff_text

            diff_markdown_content = self._render_diff_report(task_instruction, narrative_notes, command_history, per_file_diff)
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
            for rel_path, verified_content in mutations.items():
                local_file_target = os.path.abspath(os.path.join(abs_local_path, rel_path))
                if not local_file_target.startswith(abs_local_path + os.sep):
                    continue
                os.makedirs(os.path.dirname(local_file_target), exist_ok=True)
                with open(local_file_target, "w", encoding="utf-8") as local_file:
                    local_file.write(verified_content)
                applied_count += 1

            sftp.remove(remote_log_path)
            sftp.close()
            ssh.close()
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
            _, stdout, _ = ssh.exec_command(f'test -d "{normalized_target}" && echo ok || echo missing')
            if stdout.read().decode("utf-8", errors="ignore").strip() != "ok":
                ssh.close()
                return "*hisses* sandbox cleanup failed because workspace path was missing."
            ssh.exec_command(f'cd "{normalized_target}" && find . -mindepth 1 -maxdepth 1 -exec rm -rf -- {{}} +')
            ssh.close()
            return "*purrs* sandbox workspace contents cleared safely."
        except Exception as e:
            return f"*hisses* sandbox cleanup failed: {str(e)}"
