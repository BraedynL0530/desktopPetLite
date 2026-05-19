import unittest

from core.pi_agent import PiDevBridge


class TestNormalizeLlmPayload(unittest.TestCase):
    def test_parses_json_with_fence_and_extra_text(self):
        raw = (
            "here you go\n"
            "```json\n"
            '{"summary":"ok","rationale":"because","commands_run":["python3 launcher.py --help"],'
            '"mutations":{"test.txt":"hello"},"done":true}\n'
            "```\n"
            "thanks"
        )

        payload = PiDevBridge._normalize_llm_payload(raw)

        self.assertEqual(payload["summary"], "ok")
        self.assertEqual(payload["mutations"], {"test.txt": "hello"})
        self.assertTrue(payload["done"])

    def test_normalizes_dict_without_mutations_key(self):
        payload = PiDevBridge._normalize_llm_payload('{"foo.txt":"bar"}')

        self.assertEqual(payload["mutations"], {"foo.txt": "bar"})
        self.assertFalse(payload["done"])
        self.assertEqual(payload["commands_run"], [])

    def test_raises_for_unparseable_payload(self):
        with self.assertRaises(ValueError):
            PiDevBridge._normalize_llm_payload("not json")


class TestDiffReport(unittest.TestCase):
    def test_report_includes_parse_recovery_section(self):
        report = PiDevBridge._render_diff_report(
            "task",
            ["note"],
            ["python3 launcher.py --help"],
            {},
            ["loop 1: parse retry 1 triggered (bad json)."],
        )

        self.assertIn("## JSON Parse Recovery", report)
        self.assertIn("parse retry 1 triggered", report)


if __name__ == "__main__":
    unittest.main()
