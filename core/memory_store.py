import json
import os
import threading
from datetime import datetime, timezone


class LintMemoryStore:
    def __init__(self, path: str = None, max_entries: int = 80, max_context_chars: int = 4000):
        self.path = path or os.getenv("LINT_MEMORY_FILE", ".lint_memory.json")
        self.max_entries = max_entries
        self.max_context_chars = max_context_chars
        self._lock = threading.Lock()

    def _read_all(self):
        if not os.path.exists(self.path):
            return []
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
                if isinstance(payload, list):
                    return payload
        except (OSError, json.JSONDecodeError):
            return []
        return []

    def _write_all(self, entries):
        with open(self.path, "w", encoding="utf-8") as handle:
            json.dump(entries[-self.max_entries:], handle, ensure_ascii=False, indent=2)

    def add_entry(self, kind: str, prompt: str, response: str, metadata: dict = None):
        item = {
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "kind": (kind or "chat").strip()[:32],
            "prompt": (prompt or "").strip()[:2000],
            "response": (response or "").strip()[:2000],
            "metadata": metadata or {},
        }
        with self._lock:
            entries = self._read_all()
            entries.append(item)
            self._write_all(entries)

    def clear(self):
        with self._lock:
            if os.path.exists(self.path):
                os.remove(self.path)

    def get_entries(self):
        with self._lock:
            return self._read_all()

    def get_context(self) -> str:
        entries = self.get_entries()
        if not entries:
            return ""

        lines = []
        current_chars = 0
        for item in reversed(entries):
            line = (
                f"[{item.get('timestamp', '')}] {item.get('kind', 'chat')}: "
                f"prompt={item.get('prompt', '')} | response={item.get('response', '')}"
            )
            line = line.replace("\n", " ").strip()
            line_len = len(line) + 1
            if current_chars + line_len > self.max_context_chars:
                break
            lines.append(line)
            current_chars += line_len
        lines.reverse()
        return "\n".join(lines)

    def describe(self) -> str:
        entries = self.get_entries()
        if not entries:
            return "memory empty (0 entries)."
        latest = entries[-1].get("timestamp", "unknown")
        return f"memory entries: {len(entries)} | last updated: {latest}"
