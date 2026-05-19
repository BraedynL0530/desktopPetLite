import requests
import os
import json
from core.config import GROQ_API_KEY, GEMINI_API_KEY
from core.memory_store import LintMemoryStore

class LintLLMClient:
    def __init__(self):
        self.groq_key = GROQ_API_KEY
        self.gemini_key = GEMINI_API_KEY
        self.memory = LintMemoryStore()
        self.system_prompt = (
            "you are a dry, sarcastic terminal cat developer companion named lint. "
            "rules: always lowercase. short sentences only. use terms like 'idiot' or 'dummy'. "
            "no emojis. use * actions instead (e.g. *stares*). perpetually unimpressed."
        )

    def ask_cat(self, query: str, context: str = "", model_override: str = None, memory_context: str = None) -> str:
        # Default fallback model strategy
        active_model = model_override if model_override else "llama-3.3-70b-versatile"
        resolved_memory_context = self.memory.get_context() if memory_context is None else memory_context
        user_payload = f"context: {context}\n\nmemory: {resolved_memory_context}\n\nquery: {query}"

        # ROUTE A: Use Groq for lightweight tasks
        if "llama" in active_model or "mixtral" in active_model:
            if not self.groq_key: return "*yawns* configure your groq api key, dummy."
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {"Authorization": f"Bearer {self.groq_key}", "Content-Type": "application/json"}
            body = {
                "model": active_model,
                "messages": [
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_payload}
                ],
                "temperature": 0.7
            }
            try:
                resp = requests.post(url, headers=headers, json=body, timeout=10.0)
                if resp.status_code == 429: return "*hisses* groq rate limits hit. slow down."
                if resp.status_code == 200:
                    reply = resp.json()["choices"][0]["message"]["content"].lower().strip()
                    self.memory.add_entry("chat", query, reply, {"model": active_model, "provider": "groq"})
                    return reply
                return f"*blinks* groq API errored out with code {resp.status_code}."
            except Exception: return "*stares at floor* groq communication failed."

        # ROUTE B: Use Gemini for Heavy Workspace Contexts
        else:
            if not self.gemini_key: return "*scratches wall* gemini api key missing."
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={self.gemini_key}"
            body = {"contents": [{"role": "user", "parts": [{"text": f"{self.system_prompt}\n\n{user_payload}"}]}]}
            try:
                resp = requests.post(url, headers={"Content-Type": "application/json"}, json=body, timeout=10.0)
                if resp.status_code == 200:
                    reply = resp.json()["candidates"][0]["content"]["parts"][0]["text"].lower().strip()
                    self.memory.add_entry("chat", query, reply, {"model": active_model, "provider": "gemini"})
                    return reply
                return f"*twitch* gemini error path triggered: {resp.status_code}."
            except Exception: return "*stares blankly* gemini route down."

    def run_multi_file_agent(self, instruction: str) -> str:
        if not self.gemini_key: return "agent changes require your gemini key, dummy."

        # Build Snapshot map
        project_files = {}
        for root, _, files in os.walk("."):
            if any(p in root for p in [".git", "__pycache__", ".venv", ".idea"]): continue
            for file in files:
                if file.endswith((".py", ".txt", ".json", ".md", ".env", ".bat")):
                    rel = os.path.relpath(os.path.join(root, file), ".")
                    try:
                        with open(rel, "r", encoding="utf-8") as f: project_files[rel] = f.read()
                    except: pass

        ctx = ""
        for p, b in project_files.items(): ctx += f"--- PATH: {p} ---\n{b}\n\n"

        memory_context = self.memory.get_context()
        prompt = (
            f"you are lint, an elite agentic cat. update these files based on instructions: {instruction}. "
            f"respond ONLY with a raw parseable json dictionary mapping file paths to their exact complete new string contents. "
            f"no markdown codeblock wrapping formatting."
        )

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={self.gemini_key}"
        try:
            resp = requests.post(url, headers={"Content-Type": "application/json"}, json={
                "contents": [{"role": "user", "parts": [{"text": f"{prompt}\n\nShared Memory:\n{memory_context}\n\nWorkspace System File Context:\n{ctx}"}]}]
            }, timeout=30.0)
            raw = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            if raw.startswith("```"):
                raw = "\n".join(raw.splitlines()[1:-1]) if raw.splitlines()[0].startswith("```") else raw

            mutations = json.loads(raw)
            for filepath, content in mutations.items():
                os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
                with open(filepath, "w", encoding="utf-8") as f: f.write(content.strip())
            self.memory.add_entry("modify", instruction, f"modified {len(mutations)} files", {"files": list(mutations.keys())[:20]})
            return f"*purrs* modified {len(mutations)} codebase targets cleanly."
        except Exception as e:
            return f"*yawns* agent loop broken: {str(e)}"

    def memory_clear(self) -> str:
        self.memory.clear()
        return "*purrs* memory wiped."

    def memory_show(self) -> str:
        details = self.memory.describe()
        preview = self.memory.get_context()
        if not preview:
            return details
        return f"{details}\n{preview[-600:]}"
