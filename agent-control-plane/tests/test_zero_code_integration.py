import json
import tempfile
import unittest
from pathlib import Path

from agent_control_plane.integration import collect_trace_files, default_config, render_github_actions, run_check


CONTRACT = {
    "schema_version": "1",
    "agent": {"name": "support-agent"},
    "default": {"decision": "DENY"},
    "rules": [
        {"id": "read", "decision": "ALLOW", "when": [{"field": "action", "value": "search_customer"}]},
        {"id": "refund", "decision": "DENY", "when": [{"field": "action", "value": "issue_refund"}]},
    ],
}


class ZeroCodeIntegrationTest(unittest.TestCase):
    def test_collects_existing_framework_native_json_without_app_instrumentation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            traces = root / "test-results"
            traces.mkdir()
            (traces / "agent-trace.json").write_text(json.dumps({
                "output": [{"type": "function_call", "name": "search_customer", "arguments": '{"id":"c1"}'}]
            }), encoding="utf-8")
            collected = collect_trace_files(root, ["**/*trace*.json"])
            self.assertEqual(len(collected), 1)
            self.assertEqual(collected[0].events, ({"action": "search_customer", "context": {"id": "c1"}},))

    def test_check_gates_denied_action_from_existing_test_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            traces = root / ".acp" / "traces"
            traces.mkdir(parents=True)
            (traces / "run.json").write_text(json.dumps([
                {"tool": "search_customer", "arguments": {"id": "c1"}},
                {"tool": "issue_refund", "arguments": {"amount": 500}},
            ]), encoding="utf-8")
            report = run_check(root, default_config(), CONTRACT)
            self.assertEqual(report["summary"]["counts"]["ALLOW"], 1)
            self.assertEqual(report["summary"]["counts"]["DENY"], 1)
            self.assertFalse(report["summary"]["ci_pass"])
            self.assertEqual(report["sources"][0]["events"], 2)

    def test_missing_events_fails_explicitly(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "No tool-call events found"):
                run_check(Path(tmp), default_config(), CONTRACT)

    def test_ci_runs_existing_tests_before_acp_gate(self):
        workflow = render_github_actions("python -m unittest discover -s tests -v")
        self.assertIn("Run existing agent/integration tests unchanged", workflow)
        self.assertIn("run: python -m unittest discover -s tests -v", workflow)
        self.assertIn("acp check --config .acp/config.json", workflow)
        self.assertNotIn("@acp", workflow)


if __name__ == "__main__":
    unittest.main()
