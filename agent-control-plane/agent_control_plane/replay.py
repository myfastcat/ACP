from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .normalize import normalize_trace


class ReplayError(ValueError):
    pass


def build_fixture(events, incident_id="incident"):
    return {
        "schema": "acp-incident/v1",
        "incident_id": incident_id,
        "incident_events": events,
        "assertions": [],
    }


def normalize_incident(raw, incident_id="incident"):
    """Normalize a framework/native incident trace into a durable regression fixture."""
    return build_fixture(normalize_trace(raw), incident_id)


def add_assertion(fixture, kind: str, action: str, maximum: int | None = None):
    if kind not in {"must_not_occur", "must_occur", "max_occurrences"}:
        raise ReplayError(f"unsupported assertion type: {kind}")
    if not action:
        raise ReplayError("assertion action is required")
    assertion = {"type": kind, "action": action}
    if kind == "max_occurrences":
        if maximum is None or maximum < 0:
            raise ReplayError("max_occurrences requires --max >= 0")
        assertion["max"] = maximum
    assertions = fixture.setdefault("assertions", [])
    if not isinstance(assertions, list):
        raise ReplayError("fixture assertions must be a list")
    if assertion not in assertions:
        assertions.append(assertion)
    return fixture


def _fixture_incident_events(fixture):
    # Backward compatibility with early acp-incident/v1 fixtures that used `events`.
    events = fixture.get("incident_events", fixture.get("events", []))
    if not isinstance(events, list):
        raise ReplayError("fixture incident_events must be a list")
    return events


def evaluate_fixture(fixture, observed_events=None):
    """Evaluate incident invariants.

    When observed_events is supplied (the CI path), assertions are evaluated against
    the current run's tool-call events. The original incident trace remains in the
    fixture as evidence/context only. Without observed_events, replay evaluates the
    original incident events for inspection/backward-compatible CLI behavior.
    """
    failures = []
    incident_events = _fixture_incident_events(fixture)
    events = incident_events if observed_events is None else observed_events
    if not isinstance(events, list):
        raise ReplayError("observed events must be a list")

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
        "incident_event_count": len(incident_events),
        "mode": "current_observed_events" if observed_events is not None else "incident_evidence",
        "fixture_sha256": hashlib.sha256(canonical.encode()).hexdigest(),
    }


def evaluate_incident_files(root: str | Path, patterns, observed_events=None) -> list[dict]:
    base = Path(root).resolve()
    paths: dict[Path, None] = {}
    for pattern in patterns:
        for path in base.glob(pattern):
            if path.is_file():
                paths[path.resolve()] = None
    results = []
    for path in sorted(paths):
        fixture = load(path)
        report = evaluate_fixture(fixture, observed_events=observed_events)
        report["path"] = str(path.relative_to(base))
        results.append(report)
    return results


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
