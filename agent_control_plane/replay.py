"""Incident evidence is immutable context; invariants check current observations."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from .normalize import normalize_trace
from .validation import events_value, object_value, text_value, patterns_value

class ReplayError(ValueError):
    pass


def build_fixture(events, incident_id="incident"):
    events_value(events)
    text_value(incident_id, "incident_id")
    return {"schema": "acp-incident/v1", "incident_id": incident_id,
            "incident_events": events, "assertions": []}


def normalize_incident(raw, incident_id="incident"):
    return build_fixture(normalize_trace(raw), incident_id)


def _assertion(value):
    object_value(value, "assertion")
    kind = value.get("type")
    if kind not in {"must_not_occur", "must_occur", "max_occurrences"}:
        raise ReplayError(f"unsupported assertion type: {kind}")
    text_value(value.get("action"), "assertion.action")
    if kind == "max_occurrences":
        maximum = value.get("max")
        if type(maximum) is not int or maximum < 0:
            raise ReplayError("max_occurrences requires --max >= 0 (integer)")
    return value


def validate_fixture(fixture, require_assertions=False):
    object_value(fixture, "fixture")
    if fixture.get("schema") != "acp-incident/v1":
        raise ReplayError("fixture schema must be acp-incident/v1")
    text_value(fixture.get("incident_id"), "incident_id")
    events_value(fixture.get("incident_events", fixture.get("events")), "incident_events")
    assertions = fixture.get("assertions")
    if not isinstance(assertions, list):
        raise ReplayError("fixture assertions must be a list")
    if require_assertions and not assertions:
        raise ReplayError("Incident has no invariants; use acp incident assert before checking")
    for assertion in assertions:
        _assertion(assertion)


def add_assertion(fixture, kind, action, maximum=None):
    validate_fixture(fixture)
    assertion = {"type": kind, "action": action}
    if kind == "max_occurrences":
        assertion["max"] = maximum
    _assertion(assertion)
    if assertion not in fixture["assertions"]:
        fixture["assertions"].append(assertion)
    return fixture


def evaluate_fixture(fixture, observed_events=None):
    validate_fixture(fixture, require_assertions=True)
    original = fixture.get("incident_events", fixture.get("events"))
    events = original if observed_events is None else events_value(observed_events)
    failures = []
    for assertion in fixture["assertions"]:
        kind, action = assertion["type"], assertion["action"]
        count = sum(e["action"] == action for e in events)
        if kind == "must_not_occur" and count:
            failures.append(f"{action} occurred {count} time(s)")
        elif kind == "must_occur" and not count:
            failures.append(f"{action} did not occur")
        elif kind == "max_occurrences" and count > assertion["max"]:
            failures.append(f"{action} occurred {count} > {assertion['max']}")
    canonical = json.dumps(fixture, sort_keys=True, separators=(",", ":"))
    return {"incident_id": fixture["incident_id"], "passed": not failures,
            "failures": failures, "event_count": len(events),
            "incident_event_count": len(original),
            "mode": "incident_evidence" if observed_events is None else "current_observed_events",
            "fixture_sha256": hashlib.sha256(canonical.encode()).hexdigest()}


def evaluate_incident_files(root, patterns, observed_events=None):
    base = Path(root).resolve()
    paths = set()
    for pattern in patterns_value(patterns, "incident_globs"):
        for p in base.glob(pattern):
            if p.is_file():
                if not p.resolve().is_relative_to(base):
                    raise ReplayError("Incident path escapes project")
                paths.add(p.resolve())
    reports = []
    for path in sorted(paths):
        report = evaluate_fixture(load(path), observed_events)
        report["path"] = str(path.relative_to(base))
        reports.append(report)
    return reports


def evidence_pack(fixture, report):
    return {"schema": "acp-incident-evidence/v1", "fixture": fixture, "result": report,
            "replay_command": "acp incident replay fixture.json --json"}


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def dump(path, value):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
