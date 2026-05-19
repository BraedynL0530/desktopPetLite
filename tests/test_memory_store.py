import os
import tempfile
import unittest
from unittest.mock import patch

from core.llm_client import LintLLMClient
from core.memory_store import LintMemoryStore


class _MockResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class TestMemoryStore(unittest.TestCase):
    def test_store_describe_and_clear(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "memory.json")
            store = LintMemoryStore(path=path, max_entries=5, max_context_chars=200)
            store.add_entry("chat", "hello", "world")
            self.assertIn("memory entries: 1", store.describe())
            self.assertTrue(store.get_context())
            store.clear()
            self.assertEqual(store.describe(), "memory empty (0 entries).")

    def test_store_persists_across_instances(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "memory.json")
            LintMemoryStore(path=path).add_entry("chat", "persist", "yes")
            store2 = LintMemoryStore(path=path)
            self.assertIn("persist", store2.get_context())

    def test_llm_payload_includes_memory_context(self):
        captured = {}
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "memory.json")
            client = LintLLMClient()
            client.groq_key = "test-key"
            client.memory = LintMemoryStore(path=path, max_entries=10, max_context_chars=400)
            client.memory.add_entry("chat", "first", "second")

            def _fake_post(url, headers=None, json=None, timeout=0):
                captured["json"] = json
                return _MockResponse(200, {"choices": [{"message": {"content": "ok"}}]})

            with patch("core.llm_client.requests.post", side_effect=_fake_post):
                reply = client.ask_cat("next question")

            self.assertEqual(reply, "ok")
            payload = captured["json"]["messages"][1]["content"]
            self.assertIn("memory:", payload)
            self.assertIn("first", payload)
            self.assertIn("next question", payload)


if __name__ == "__main__":
    unittest.main()
