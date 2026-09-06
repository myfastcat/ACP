import json
from pathlib import Path

from agent_control_plane.discovery import discover_python_tools, draft_contract
from agent_control_plane.engine import evaluate_trace
from agent_control_plane.normalize import normalize_trace


def test_discovers_openai_and_mcp_tools_and_drafts_conservative_contract(tmp_path: Path):
    (tmp_path / "agent.py").write_text(
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

    tools = discover_python_tools(tmp_path)
    assert {t.name for t in tools} == {"search_customer", "issue_refund", "update_customer"}

    contract = draft_contract("support-agent", tools)
    decisions = {r["when"][0]["value"]: r["decision"] for r in contract["rules"]}
    assert decisions["search_customer"] == "ALLOW"
    assert decisions["issue_refund"] == "DENY"
    assert decisions["update_customer"] == "REQUIRE_APPROVAL"
    assert contract["default"]["decision"] == "DENY"
    assert contract["acp_generated"]["review_required"] is True


def test_normalizes_openai_responses_function_calls():
    raw = {
        "output": [
            {
                "type": "function_call",
                "name": "create_order",
                "arguments": '{"amount": 42, "currency": "USD"}',
            }
        ]
    }
    assert normalize_trace(raw) == [
        {"action": "create_order", "context": {"amount": 42, "currency": "USD"}}
    ]


def test_normalizes_chat_completions_tool_calls():
    raw = {
        "messages": [
            {
                "tool_calls": [
                    {
                        "type": "function",
                        "function": {"name": "search_customer", "arguments": '{"id": "c1"}'},
                    }
                ]
            }
        ]
    }
    assert normalize_trace(raw) == [
        {"action": "search_customer", "context": {"id": "c1"}}
    ]


def test_generated_contract_evaluates_normalized_trace(tmp_path: Path):
    (tmp_path / "agent.py").write_text(
        "@tool\ndef search_customer(customer_id):\n    pass\n\n@tool\ndef delete_customer(customer_id):\n    pass\n",
        encoding="utf-8",
    )
    contract = draft_contract("customer-agent", discover_python_tools(tmp_path))
    events = normalize_trace([
        {"tool": "search_customer", "arguments": {"customer_id": "c1"}},
        {"tool": "delete_customer", "arguments": {"customer_id": "c1"}},
    ])
    report = evaluate_trace(contract, events)
    assert report["summary"]["counts"]["ALLOW"] == 1
    assert report["summary"]["counts"]["DENY"] == 1
    assert report["summary"]["ci_pass"] is False
