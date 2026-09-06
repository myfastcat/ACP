import json
import tempfile
import unittest
from pathlib import Path

from agent_control_plane.integration import render_github_actions
from agent_control_plane.openai_zero_code import OpenAIAgentsTraceCollector


class _FunctionData:
    type = "function"

    def export(self):
        return {"type": "function", "name": "issue_refund", "input": '{"amount":500}', "output": None}


class _OtherData:
    type = "generation"

    def export(self):
        return {"type": "generation"}


class _Span:
    def __init__(self, data):
        self.span_data = data


class OpenAIZeroCodeTest(unittest.TestCase):
    def test_collects_function_span_as_tool_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            collector = OpenAIAgentsTraceCollector(Path(tmp))
            collector.on_span_end(_Span(_FunctionData()))
            collector.flush()
            files = list(Path(tmp).glob("openai-agents-*.json"))
            self.assertEqual(len(files), 1)
            events = json.loads(files[0].read_text(encoding="utf-8"))
            self.assertEqual(events, [{"tool": "issue_refund", "arguments": {"amount": 500}}])

    def test_ignores_non_function_spans(self):
        with tempfile.TemporaryDirectory() as tmp:
            collector = OpenAIAgentsTraceCollector(Path(tmp))
            collector.on_span_end(_Span(_OtherData()))
            collector.flush()
            self.assertEqual(list(Path(tmp).glob("*.json")), [])

    def test_generated_ci_uses_zero_code_bootstrap(self):
        workflow = render_github_actions("python -m unittest discover -s tests -v")
        self.assertIn("agent_control_plane.zero_code_runner", workflow)
        self.assertIn("python -m unittest discover -s tests -v", workflow)
        self.assertNotIn("@acp", workflow)


if __name__ == "__main__":
    unittest.main()
