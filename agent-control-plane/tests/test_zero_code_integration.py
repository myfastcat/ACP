import json
from pathlib import Path

import pytest

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


def test_collects_existing_framework_native_json_without_app_instrumentation(tmp_path: Path):
    traces = tmp_path / "test-results"
    traces.mkdir()
    (traces / "agent-trace.json").write_text(json.dumps({
        "output": [{"type": "function_call", "name": "search_customer", "arguments": '{"id":"c1"}'}]
    }), encoding="utf-8")

    collected = collect_trace_files(tmp_path, ["**/*trace*.json"])
    assert len(collected) == 1
    assert collected[0].events == ({"action": "search_customer", "context": {"id": "c1"}},)


def test_check_gates_denied_action_from_existing_test_artifact(tmp_path: Path):
    traces = tmp_path / ".acp" / "traces"
    traces.mkdir(parents=True)
    (traces / "run.json").write_text(json.dumps([
        {"tool": "search_customer", "arguments": {"id": "c1"}},
        {"tool": "issue_refund", "arguments": {"amount": 500}},
    ]), encoding="utf-8")

    report = run_check(tmp_path, default_config(), CONTRACT)
    assert report["summary"]["counts"]["ALLOW"] == 1
    assert report["summary"]["counts"]["DENY"] == 1
    assert report["summary"]["ci_pass"] is False
    assert report["sources"][0]["events"] == 2


def test_missing_events_fails_explicitly(tmp_path: Path):
    with pytest.raises(ValueError, match="No tool-call events found"):
        run_check(tmp_path, default_config(), CONTRACT)


def test_ci_runs_existing_tests_before_acp_gate():
    workflow = render_github_actions("pytest -q")
    assert "Run existing agent/integration tests unchanged" in workflow
    assert "run: pytest -q" in workflow
    assert "acp check --config .acp/config.json" in workflow
    assert "@acp" not in workflow
