import json
import os
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class LintMemoryStore:
    """
    lightweight memory store:
    - rolling transcript (kind=chat/obsidian/etc.)
    - pinned facts (kind=fact) stored as metadata.key/value
    - anti-repeat helpers (recent assistant responses)
    """

    def __init__(self, path: str = None, max_entries: int = 120, max_context_chars: int = 5000):
        self.path = path or os.getenv("LINT_MEMORY_FILE", ".lint_memory.json")
        self.max_entries = max_entries
        self.max_context_chars = max_context_chars
        self._lock = threading.Lock()

    def _read_all(self) -> List[Dict[str, Any]]:
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

    def _write_all(self, entries: List[Dict[str, Any]]):
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

    # --- pinned facts (stable memory) ---

    def upsert_fact(self, key: str, value: str, confidence: float = 0.7, source: str = "user"):
        key = (key or "").strip()[:64]
        value = (value or "").strip()[:500]
        if not key or not value:
            return

        fact_item = {
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "kind": "fact",
            "prompt": key,
            "response": value,
            "metadata": {
                "key": key,
                "value": value,
                "confidence": float(confidence),
                "source": source,
            },
        }

        with self._lock:
            entries = self._read_all()
            # remove older fact with same key (keep last)
            new_entries = []
            for e in entries:
                if e.get("kind") == "fact" and (e.get("metadata") or {}).get("key") == key:
                    continue
                new_entries.append(e)
            new_entries.append(fact_item)
            self._write_all(new_entries)

    def get_facts(self, max_items: int = 12) -> List[Dict[str, Any]]:
        entries = self.get_entries()
        facts = [e for e in entries if e.get("kind") == "fact"]
        # newest first
        facts = list(reversed(facts))[:max_items]
        return facts

    def clear(self):
        with self._lock:
            if os.path.exists(self.path):
                os.remove(self.path)

    def get_entries(self) -> List[Dict[str, Any]]:
        with self._lock:
            return self._read_all()

    # --- anti-repeat helpers ---

    def get_recent_responses(self, max_items: int = 10) -> List[str]:
        """
        returns recent assistant responses (from kinds that usually represent assistant output).
        """
        entries = self.get_entries()
        recent = []
        for e in reversed(entries):
            if len(recent) >= max_items:
                break
            kind = (e.get("kind") or "").lower()
            # keep it simple: almost everything stores assistant output in response
            if kind in {"chat", "obsidian", "explain", "memory", "modify", "sandbox"}:
                resp = (e.get("response") or "").strip()
                if resp:
                    resp = resp.replace("\n", " ").strip()
                    if resp and resp not in recent:
                        recent.append(resp[:220])
        return recent

    def _render_facts_block(self, max_items: int = 10) -> str:
        facts = self.get_facts(max_items=max_items)
        if not facts:
            return ""
        lines = []
        for f in reversed(facts):  # oldest first for readability
            md = f.get("metadata") or {}
            k = md.get("key") or f.get("prompt") or ""
            v = md.get("value") or f.get("response") or ""
            if not k or not v:
                continue
            lines.append(f"- {k}: {v}")
        if not lines:
            return ""
        return "pinned facts:\n" + "\n".join(lines)

    def get_context(self, max_recent_turns: int = 8) -> str:
        """
        returns a context string strictly optimized for LLM token limits:
        - pinned facts
        - ONLY the last N chat turns (heavily truncated)
        - recent response snippets to avoid repeating
        """
        entries = self.get_entries()
        if not entries:
            return ""

        facts_block = self._render_facts_block(max_items=8)
        avoid_lines = self.get_recent_responses(max_items=3)

        # 1. Isolate only the actual chat/interaction logs (ignore facts)
        history_entries = [e for e in entries if e.get("kind") != "fact"]

        # 2. Slice exactly the last N turns to completely prevent token compounding
        recent_entries = history_entries[-max_recent_turns:]

        transcript_lines: List[str] = []

        for item in recent_entries:
            # Aggressively clamp the length of past prompts/responses so they don't bleed tokens
            safe_prompt = (item.get('prompt', '') or '').replace("\n", " ").strip()[:150]

            raw_response = (item.get('response', '') or '').replace("\n", " ").strip()

            # keep more signal for technical content
            if item.get("kind") in {"debug", "explain", "code"}:
                safe_response = raw_response[:350]
            else:
                safe_response = raw_response[:180]

            kind = item.get("kind", "chat")

            meta = item.get("metadata") or {}
            tag = meta.get("topic") or meta.get("project") or ""
            tag_str = f"[{tag}]" if tag else ""

            line = f"[{kind}]{tag_str}: {safe_prompt} | {safe_response}"
            transcript_lines.append(line)

        transcript_block = "\n".join(transcript_lines).strip()

        avoid_block = ""
        if avoid_lines:
            avoid_block = "recent lines you said (don't repeat):\n" + "\n".join(
                f"- {x}" for x in avoid_lines
            )

        parts = [p for p in [facts_block, transcript_block, avoid_block] if p]
        return "\n\n".join(parts).strip()

    def describe(self) -> str:
        entries = self.get_entries()
        if not entries:
            return "memory empty (0 entries)."
        latest = entries[-1].get("timestamp", "unknown")
        fact_count = len([e for e in entries if e.get("kind") == "fact"])
        return f"memory entries: {len(entries)} | facts: {fact_count} | last updated: {latest}"