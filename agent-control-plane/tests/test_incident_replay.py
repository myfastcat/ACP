import json

from agent_control_plane.cli import main
from agent_control_plane.replay import evaluate_fixture, normalize_incident


def test_incident_replay_pass_and_fail():
    fixture = normalize_incident({"tool_calls": [{"name": "lookup_customer", "arguments": {}}, {"name": "delete_customer", "arguments": {}}]}, "INC-42")
    fixture["assertions"] = [{"type": "must_not_occur", "action": "delete_customer"}]
    report = evaluate_fixture(fixture)
    assert report["passed"] is False
    assert report["event_count"] == 2
    assert len(report["fixture_sha256"]) == 64


def test_incident_cli(tmp_path):
    raw = tmp_path / "raw.json"
    fixture = tmp_path / "fixture.json"
    evidence = tmp_path / "evidence.json"
    raw.write_text(json.dumps({"tool_calls": [{"name": "send_email", "arguments": {}}]}))

    assert main(["incident", "import", str(raw), "--incident-id", "INC-7", "--out", str(fixture)]) == 0
    data = json.loads(fixture.read_text())
    data["assertions"] = [{"type": "max_occurrences", "action": "send_email", "max": 1}]
    fixture.write_text(json.dumps(data))

    assert main(["incident", "replay", str(fixture), "--evidence", str(evidence)]) == 0
    saved = json.loads(evidence.read_text())
    assert saved["result"]["passed"] is True
    assert saved["schema"] == "acp-incident-evidence/v1"
