from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .normalize import normalize_trace


class ReplayError(ValueError):
    pass


def build_fixture(events, incident_id="incident"):
    return {"schema": "acp-incident/v1", "incident_id": incident_id, "events": events, "assertions": []}


def normalize_incident(raw, incident_id="incident"):
    """Normalize a framework/native trace and wrap it as an ACP incident fixture."""
    return build_fixture(normalize_trace(raw), incident_id)


def evaluate_fixture(fixture):
    failures = []
    events = fixture.get("events", [])
    if not isinstance(events, list):
        raise ReplayError("fixture events must be a list")

    for assertion in fixture.get("assertions", []):
        if not isinstance(assertion, dict):
            raise ReplayError("each assertion must be an object")
        kind = assertion.get("type")
        action = assertion.get("action")
        if not action:
            raise ReplayError("assertion action is required")
        matches = [event for event in events if event.get("action") == action]
        if kind == "must_not_occur":
            if matches:
                failures.append(f"{action} occurred {len(matches)} time(s)")
        elif kind == "must_occur":
            if not matches:
                failures.append(f"{action} did not occur")
        elif kind == "max_occurrences":
            maximum = int(assertion.get("max", 0))
            if len(matches) > maximum:
                failures.append(f"{action} occurred {len(matches)} > {maximum}")
        else:
            raise ReplayError(f"unsupported assertion type: {kind}")

    canonical = json.dumps(fixture, sort_keys=True, separators=(",", ":"))
    return {
        "incident_id": fixture.get("incident_id"),
        "passed": not failures,
        "failures": failures,
        "event_count": len(events),
        "fixture_sha256": hashlib.sha256(canonical.encode()).hexdigest(),
    }


def evidence_pack(fixture, report):
    return {
        "schema": "acp-incident-evidence/v1",
        "fixture": fixture,
        "result": report,
        "replay_command": "acp incident replay fixture.json --json",
    }


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def dump(path, value):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
