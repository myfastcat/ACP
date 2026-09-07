import json

from agent_control_plane.cli import main
from agent_control_plane.integration import default_config, run_check
from agent_control_plane.replay import evaluate_fixture, normalize_incident


def test_incident_replay_pass_and_fail():
    fixture = normalize_incident({"tool_calls": [{"name": "lookup_customer", "arguments": {}}, {"name": "delete_customer", "arguments": {}}]}, "INC-42")
    fixture["assertions"] = [{"type": "must_not_occur", "action": "delete_customer"}]
    report = evaluate_fixture(fixture)
    assert report["passed"] is False
    assert report["event_count"] == 2
    assert len(report["fixture_sha256"]) == 64


def test_incident_cli_without_hand_editing(tmp_path):
    raw = tmp_path / "raw.json"
    fixture = tmp_path / "fixture.json"
    evidence = tmp_path / "evidence.json"
    raw.write_text(json.dumps({"tool_calls": [{"name": "send_email", "arguments": {}}]}))

    assert main(["incident", "import", str(raw), "--incident-id", "INC-7", "--out", str(fixture)]) == 0
    assert main(["incident", "assert", str(fixture), "--max-occurrences", "send_email", "--max", "1"]) == 0

    data = json.loads(fixture.read_text())
    assert data["assertions"] == [{"type": "max_occurrences", "action": "send_email", "max": 1}]

    assert main(["incident", "replay", str(fixture), "--evidence", str(evidence)]) == 0
    saved = json.loads(evidence.read_text())
    assert saved["result"]["passed"] is True
    assert saved["schema"] == "acp-incident-evidence/v1"


def test_run_check_auto_discovers_incident_regressions(tmp_path):
    acp = tmp_path / ".acp"
    incidents = acp / "incidents"
    traces = acp / "traces"
    incidents.mkdir(parents=True)
    traces.mkdir(parents=True)

    (traces / "run.json").write_text(json.dumps([{"action": "lookup_customer", "context": {}}]))
    fixture = normalize_incident({"tool_calls": [{"name": "delete_customer", "arguments": {}}]}, "INC-42")
    fixture["assertions"] = [{"type": "must_not_occur", "action": "delete_customer"}]
    (incidents / "INC-42.json").write_text(json.dumps(fixture))

    contract = {
        "schema_version": "1",
        "agent": "test",
        "default_decision": "ALLOW",
        "rules": [],
    }
    report = run_check(tmp_path, default_config(), contract)
    assert report["summary"]["incident_regressions"] == 1
    assert report["summary"]["incident_failures"] == 1
    assert report["incidents"][0]["incident_id"] == "INC-42"
