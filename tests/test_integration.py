import tempfile
import unittest
from pathlib import Path

from agent_control_plane.discovery import discover_python_tools, draft_contract
from agent_control_plane.engine import evaluate_trace
from agent_control_plane.normalize import normalize_trace


class IntegrationTests(unittest.TestCase):
    def test_discovers_tools_and_drafts_conservative_contract(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "agent.py").write_text(
                """
from agents import function_tool

@function_tool
def search_customer(customer_id: str):
    pass

@mcp.tool()
def issue_refund(amount: int):
    pass

@tool
def update_customer(name: str):
    pass
""",
                encoding="utf-8",
            )
            tools = discover_python_tools(root)
            self.assertEqual({t.name for t in tools}, {"search_customer", "issue_refund", "update_customer"})
            contract = draft_contract("support-agent", tools)
            decisions = {r["when"][0]["value"]: r["decision"] for r in contract["rules"]}
            self.assertEqual(decisions["search_customer"], "ALLOW")
            self.assertEqual(decisions["issue_refund"], "DENY")
            self.assertEqual(decisions["update_customer"], "REQUIRE_APPROVAL")
            self.assertEqual(contract["default"]["decision"], "DENY")
            self.assertTrue(contract["acp_generated"]["review_required"])

    def test_normalizes_openai_responses_function_calls(self):
        raw = {"output": [{"type": "function_call", "name": "create_order", "arguments": '{"amount": 42, "currency": "USD"}'}]}
        self.assertEqual(normalize_trace(raw), [
            {"action": "create_order", "context": {"amount": 42, "currency": "USD"}}
        ])

    def test_draft_hints_match_name_tokens_not_substrings(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "agent.py").write_text(
                "@tool\ndef target_account():\n    pass\n\n"
                "@tool\ndef budget_report():\n    pass\n\n"
                "@tool\ndef listUsers():\n    pass\n",
                encoding="utf-8",
            )
            contract = draft_contract("token-boundary-agent", discover_python_tools(root))
            decisions = {r["when"][0]["value"]: r["decision"] for r in contract["rules"]}
            self.assertEqual(decisions["target_account"], "REQUIRE_APPROVAL")
            self.assertEqual(decisions["budget_report"], "REQUIRE_APPROVAL")
            self.assertEqual(decisions["listUsers"], "ALLOW")

    def test_package_supply_chain_and_credential_hints_fail_closed(self):
        with tempfile.TemporaryDirectory() as root:
            Path(root, "tools.py").write_text("""
@tool
def upload_package(): pass
@tool
def installPackage(): pass
@tool
def publish_package(): pass
@tool
def get_credentials(): pass
@tool
def upload_avatar(): pass
""")
            contract = draft_contract("registry-agent", discover_python_tools(root))
            decisions = {rule["when"][0]["value"]: rule["decision"] for rule in contract["rules"]}
            self.assertEqual(decisions["upload_package"], "DENY")
            self.assertEqual(decisions["installPackage"], "DENY")
            self.assertEqual(decisions["publish_package"], "DENY")
            self.assertEqual(decisions["get_credentials"], "DENY")
            self.assertEqual(decisions["upload_avatar"], "REQUIRE_APPROVAL")

    def test_normalizes_chat_completions_tool_calls(self):
        raw = {"messages": [{"tool_calls": [{"type": "function", "function": {"name": "search_customer", "arguments": '{"id": "c1"}'}}]}]}
        self.assertEqual(normalize_trace(raw), [
            {"action": "search_customer", "context": {"id": "c1"}}
        ])

    def test_generated_contract_evaluates_normalized_trace(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "agent.py").write_text(
                "@tool\ndef search_customer(customer_id):\n    pass\n\n@tool\ndef delete_customer(customer_id):\n    pass\n",
                encoding="utf-8",
            )
            contract = draft_contract("customer-agent", discover_python_tools(root))
            events = normalize_trace([
                {"tool": "search_customer", "arguments": {"customer_id": "c1"}},
                {"tool": "delete_customer", "arguments": {"customer_id": "c1"}},
            ])
            report = evaluate_trace(contract, events)
            self.assertEqual(report["summary"]["counts"]["ALLOW"], 1)
            self.assertEqual(report["summary"]["counts"]["DENY"], 1)
            self.assertFalse(report["summary"]["ci_pass"])


if __name__ == "__main__":
    unittest.main()
