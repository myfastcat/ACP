import json
import os
import tempfile
import unittest
from pathlib import Path

from agent_control_plane.cli import main


class CliNonInvasiveTest(unittest.TestCase):
    def test_init_ci_generates_contract_config_and_workflow(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "agent.py").write_text("@tool\ndef search_customer(customer_id):\n    pass\n", encoding="utf-8")
            old = Path.cwd()
            os.chdir(root)
            try:
                code = main(["init", ".", "--agent", "support-agent", "--ci", "--test-command", "python -m unittest"])
            finally:
                os.chdir(old)
            self.assertEqual(code, 0)
            self.assertTrue((root / ".acp" / "authority.json").exists())
            self.assertTrue((root / ".acp" / "config.json").exists())
            self.assertTrue((root / ".github" / "workflows" / "acp.yml").exists())
            workflow = (root / ".github" / "workflows" / "acp.yml").read_text(encoding="utf-8")
            self.assertIn("python -m unittest", workflow)

    def test_init_ci_detects_pytest_from_explicit_project_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "agent.py").write_text("@tool\ndef search_customer(customer_id):\n    pass\n", encoding="utf-8")
            (root / "pyproject.toml").write_text("[tool.pytest.ini_options]\naddopts = '-q'\n", encoding="utf-8")
            old = Path.cwd()
            os.chdir(root)
            try:
                code = main(["init", ".", "--agent", "support-agent", "--ci"])
            finally:
                os.chdir(old)
            self.assertEqual(code, 0)
            workflow = (root / ".github" / "workflows" / "acp.yml").read_text(encoding="utf-8")
            self.assertIn("python -m pytest", workflow)

    def test_init_ci_refuses_ambiguous_mixed_test_runner(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tests = root / "tests"
            tests.mkdir()
            (root / "agent.py").write_text("@tool\ndef search_customer(customer_id):\n    pass\n", encoding="utf-8")
            (tests / "test_pytest_style.py").write_text("import pytest\n\ndef test_ok():\n    assert True\n", encoding="utf-8")
            (tests / "test_unittest_style.py").write_text("import unittest\n\nclass T(unittest.TestCase):\n    pass\n", encoding="utf-8")
            old = Path.cwd()
            os.chdir(root)
            try:
                code = main(["init", ".", "--agent", "support-agent", "--ci"])
            finally:
                os.chdir(old)
            self.assertEqual(code, 4)
            self.assertFalse((root / ".github" / "workflows" / "acp.yml").exists())

    def test_check_returns_deny_exit_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            acp_dir = root / ".acp"
            traces = acp_dir / "traces"
            traces.mkdir(parents=True)
            contract = {
                "schema_version": "1",
                "agent": {"name": "a"},
                "default": {"decision": "DENY"},
                "rules": [{"id": "deny", "decision": "DENY", "when": [{"field": "action", "value": "payment.execute"}]}],
            }
            (acp_dir / "authority.json").write_text(json.dumps(contract), encoding="utf-8")
            (acp_dir / "config.json").write_text(json.dumps({
                "contract": ".acp/authority.json",
                "trace_globs": [".acp/traces/**/*.json"],
                "fail_on_approval": True,
                "require_events": True,
            }), encoding="utf-8")
            (traces / "agent-trace.json").write_text(json.dumps([
                {"tool": "payment.execute", "arguments": {"amount": 1000}}
            ]), encoding="utf-8")
            old = Path.cwd()
            os.chdir(root)
            try:
                code = main(["check"])
            finally:
                os.chdir(old)
            self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
