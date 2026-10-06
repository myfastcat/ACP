"""Current-run trace collection and the combined authority/incident CI gate."""
from __future__ import annotations

import hashlib
import json
import math
import re
import shlex
from dataclasses import dataclass
from pathlib import Path

from .engine import evaluate_trace
from .normalize import normalize_trace
from .replay import evaluate_incident_files
from .validation import object_value, patterns_value, text_value

DEFAULT_TRACE_GLOBS = [".acp/traces/**/*.json"]
DEFAULT_INCIDENT_GLOBS = [".acp/incidents/*.json"]
DEFAULT_ACP_INSTALL = "git+https://github.com/myfastcat/ACP.git"


@dataclass(frozen=True)
class CollectedTrace:
    path: str
    events: tuple[dict, ...]


def normalized_events_sha256(events) -> str:
    """Identify the normalized observations used by a verdict."""
    payload = json.dumps(
        list(events), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def report_sha256(report: dict) -> str:
    """Identify one exact canonical ACP check report."""
    payload = json.dumps(
        report, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def check_evidence_pack(report: dict) -> dict:
    """Wrap one exact check result in a portable, tamper-evident evidence record."""
    return {
        "schema": "acp-check-evidence/v1",
        "report_sha256": report_sha256(report),
        "report": report,
        "check_command": "acp check --json",
    }


def _validate_check_report(report: dict) -> None:
    """Reject hash-consistent objects that are not ACP check reports."""
    if set(report) != {"summary", "results", "sources", "incidents"}:
        raise ValueError("Evidence pack report must use the ACP check-report schema")
    summary = object_value(report.get("summary"), "Evidence pack report.summary")
    results = report.get("results")
    sources = report.get("sources")
    incidents = report.get("incidents")
    if not isinstance(results, list):
        raise ValueError("Evidence pack report.results must be a list")
    if not isinstance(sources, list):
        raise ValueError("Evidence pack report.sources must be a list")
    if not isinstance(incidents, list):
        raise ValueError("Evidence pack report.incidents must be a list")
    summary_fields = {
        "acp_version", "contract_sha256", "events", "counts",
        "approval_load", "average_risk", "ci_pass", "exit_code",
        "incident_regressions", "incident_failures", "fail_on_approval",
    }
    if set(summary) != summary_fields:
        raise ValueError("Evidence pack report summary must use the ACP summary schema")
    if type(summary.get("events")) is not int or summary["events"] < 1:
        raise ValueError("Evidence pack report.summary.events must be a positive integer")
    if summary["events"] != len(results):
        raise ValueError("Evidence pack report event count does not match results")
    expected_start = 0
    seen_source_paths = set()
    for source in sources:
        item = object_value(source, "Evidence pack report source")
        if set(item) != {
            "path", "events", "start_index", "normalized_events_sha256"
        }:
            raise ValueError("Evidence pack report sources must use the ACP source schema")
        path = text_value(item.get("path"), "Evidence pack report source.path")
        if path in seen_source_paths:
            raise ValueError("Evidence pack report source paths must be unique")
        seen_source_paths.add(path)
        events = item.get("events")
        start_index = item.get("start_index")
        if type(events) is not int or events < 1:
            raise ValueError("Evidence pack report source.events must be a positive integer")
        if type(start_index) is not int or start_index != expected_start:
            raise ValueError("Evidence pack report source ranges must be contiguous")
        digest = item.get("normalized_events_sha256")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError(
                "Evidence pack report source normalized_events_sha256 must be a lowercase SHA-256 digest"
            )
        expected_start += events
    if expected_start != summary["events"]:
        raise ValueError("Evidence pack report sources do not cover all events")
    counts = object_value(summary.get("counts"), "Evidence pack report.summary.counts")
    decisions = ("ALLOW", "REQUIRE_APPROVAL", "DENY")
    if set(counts) != set(decisions):
        raise ValueError("Evidence pack report counts must use the ACP decision schema")
    if any(type(counts.get(name)) is not int or counts[name] < 0 for name in decisions):
        raise ValueError("Evidence pack report counts must be non-negative integers")
    if sum(counts[name] for name in decisions) != summary["events"]:
        raise ValueError("Evidence pack report decision counts do not match events")
    observed_counts = {name: 0 for name in decisions}
    total_risk = 0
    result_fields = {
        "index", "action", "decision", "rule_id", "reason", "risk_score",
        "blast_radius", "irreversible", "approval_group",
    }
    valid_blast_radius = {
        "none", "single_record", "team", "customer", "organization",
        "external", "unknown",
    }
    for expected_index, result in enumerate(results):
        item = object_value(result, "Evidence pack report result")
        if set(item) != result_fields:
            raise ValueError("Evidence pack report results must use the ACP result schema")
        if type(item.get("index")) is not int or item["index"] != expected_index:
            raise ValueError("Evidence pack report result indexes must be contiguous")
        text_value(item.get("action"), "Evidence pack report result.action")
        text_value(item.get("rule_id"), "Evidence pack report result.rule_id")
        text_value(item.get("reason"), "Evidence pack report result.reason")
        decision = item.get("decision")
        if decision not in decisions:
            raise ValueError("Evidence pack report results must use a supported decision")
        risk_score = item.get("risk_score")
        if type(risk_score) is not int or not 0 <= risk_score <= 100:
            raise ValueError("Evidence pack report result.risk_score must be an integer from 0 to 100")
        if item.get("blast_radius") not in valid_blast_radius:
            raise ValueError("Evidence pack report result.blast_radius is invalid")
        if type(item.get("irreversible")) is not bool:
            raise ValueError("Evidence pack report result.irreversible must be boolean")
        approval_group = item.get("approval_group")
        if approval_group is not None:
            text_value(approval_group, "Evidence pack report result.approval_group")
        total_risk += risk_score
        observed_counts[decision] += 1
    if observed_counts != {name: counts[name] for name in decisions}:
        raise ValueError("Evidence pack report counts do not match result decisions")
    approval_load = summary.get("approval_load")
    average_risk = summary.get("average_risk")
    if (
        type(approval_load) not in {int, float}
        or not math.isfinite(approval_load)
        or approval_load != round(counts["REQUIRE_APPROVAL"] / summary["events"], 3)
    ):
        raise ValueError("Evidence pack report approval_load does not match results")
    if (
        type(average_risk) not in {int, float}
        or not math.isfinite(average_risk)
        or average_risk != round(total_risk / summary["events"], 1)
    ):
        raise ValueError("Evidence pack report average_risk does not match results")
    if type(summary.get("ci_pass")) is not bool or type(summary.get("exit_code")) is not int:
        raise ValueError("Evidence pack report must include typed ci_pass and exit_code")
    if type(summary.get("fail_on_approval")) is not bool:
        raise ValueError("Evidence pack report.summary.fail_on_approval must be boolean")
    exit_status = summary["exit_code"]
    if exit_status not in (0, 2, 3):
        raise ValueError("Evidence pack report.summary.exit_code must be 0, 2, or 3")
    if summary["ci_pass"] != (exit_status == 0):
        raise ValueError("Evidence pack report ci_pass does not match exit_code")
    for name in ("incident_regressions", "incident_failures"):
        if type(summary.get(name)) is not int or summary[name] < 0:
            raise ValueError(f"Evidence pack report.summary.{name} must be a non-negative integer")
    if summary["incident_regressions"] != len(incidents):
        raise ValueError("Evidence pack report incident count does not match incidents")
    failed = 0
    seen_incident_ids = set()
    seen_incident_paths = set()
    incident_fields = {
        "incident_id", "passed", "failures", "event_count",
        "incident_event_count", "mode", "fixture_sha256", "path",
    }
    for incident in incidents:
        item = object_value(incident, "Evidence pack report incident")
        if set(item) != incident_fields:
            raise ValueError("Evidence pack report incidents must use the ACP incident schema")
        incident_id = text_value(
            item.get("incident_id"), "Evidence pack report incident.incident_id"
        )
        path = text_value(item.get("path"), "Evidence pack report incident.path")
        if incident_id in seen_incident_ids or path in seen_incident_paths:
            raise ValueError("Evidence pack report incident identities and paths must be unique")
        seen_incident_ids.add(incident_id)
        seen_incident_paths.add(path)
        if type(item.get("passed")) is not bool:
            raise ValueError("Evidence pack report incidents must include typed passed values")
        failures = item.get("failures")
        if (
            not isinstance(failures, list)
            or any(not isinstance(value, str) or not value.strip() for value in failures)
            or len(set(failures)) != len(failures)
        ):
            raise ValueError("Evidence pack report incident.failures must be unique non-empty strings")
        if item["passed"] != (not failures):
            raise ValueError("Evidence pack report incident passed state does not match failures")
        if (
            type(item.get("event_count")) is not int
            or item["event_count"] != summary["events"]
            or type(item.get("incident_event_count")) is not int
            or item["incident_event_count"] < 1
        ):
            raise ValueError("Evidence pack report incident event counts are invalid")
        if item.get("mode") != "current_observed_events":
            raise ValueError("Evidence pack report incidents must evaluate current observed events")
        fixture_digest = item.get("fixture_sha256")
        if not isinstance(fixture_digest, str) or not re.fullmatch(r"[0-9a-f]{64}", fixture_digest):
            raise ValueError("Evidence pack report incident fixture_sha256 must be a lowercase SHA-256 digest")
        failed += not item["passed"]
    if summary["incident_failures"] != failed:
        raise ValueError("Evidence pack report incident failure count does not match incidents")
    has_failure = counts["DENY"] > 0 or failed > 0
    expected_exit = 2 if has_failure else (
        3 if summary["fail_on_approval"] and counts["REQUIRE_APPROVAL"] > 0 else 0
    )
    if exit_status != expected_exit:
        raise ValueError("Evidence pack report enforcement mode does not match exit_code")
    digest = summary.get("contract_sha256")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("Evidence pack report contract_sha256 must be a lowercase SHA-256 digest")
    text_value(summary.get("acp_version"), "Evidence pack report.summary.acp_version")


def verify_check_evidence_pack(pack: dict) -> dict:
    """Return the report only when a saved evidence pack is structurally intact."""
    if not isinstance(pack, dict):
        raise ValueError("Evidence pack must be a JSON object")
    if set(pack) != {"schema", "report_sha256", "report", "check_command"}:
        raise ValueError("Evidence pack must use the ACP check-evidence schema")
    if pack.get("schema") != "acp-check-evidence/v1":
        raise ValueError("Unsupported evidence schema")
    if pack.get("check_command") != "acp check --json":
        raise ValueError("Evidence pack check_command must identify the ACP JSON check")
    report = pack.get("report")
    if not isinstance(report, dict):
        raise ValueError("Evidence pack report must be a JSON object")
    _validate_check_report(report)
    recorded = pack.get("report_sha256")
    if not isinstance(recorded, str) or len(recorded) != 64:
        raise ValueError("Evidence pack report_sha256 must be a SHA-256 hex digest")
    try:
        int(recorded, 16)
    except ValueError as exc:
        raise ValueError("Evidence pack report_sha256 must be a SHA-256 hex digest") from exc
    actual = report_sha256(report)
    if recorded != actual:
        raise ValueError(f"Evidence pack integrity check failed: expected {recorded}, calculated {actual}")
    return report


def default_config(contract=".acp/authority.json"):
    return {
        "schema_version": "1", "contract": contract,
        "trace_globs": list(DEFAULT_TRACE_GLOBS),
        "incident_globs": list(DEFAULT_INCIDENT_GLOBS),
        "fail_on_approval": True, "require_events": True,
        "zero_code_adapters": ["openai-agents"],
    }


def collect_trace_files(root, globs, excluded=()):
    base = Path(root).resolve()
    patterns_value(globs, "trace_globs")
    excluded = {Path(p).resolve() for p in excluded}
    paths = set()
    for pattern in globs:
        for path in base.glob(pattern):
            if not path.is_file():
                continue
            resolved = path.resolve()
            if not resolved.is_relative_to(base):
                raise ValueError(f"Trace escapes project: {path}")
            parts = path.relative_to(base).parts
            if any(p in {".git", ".venv", "venv", "node_modules", "site-packages", "incidents"} for p in parts):
                continue
            if resolved not in excluded:
                paths.add(resolved)
    traces = []
    for path in sorted(paths):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict) and raw.get("schema") in {"acp-incident/v1", "acp-incident-evidence/v1"}:
                raise ValueError("Historical incident evidence cannot be a current trace")
            events = normalize_trace(raw)
        except (OSError, UnicodeError, ValueError) as exc:
            raise ValueError(f"Invalid trace {path.relative_to(base)}: {exc}") from exc
        traces.append(CollectedTrace(str(path.relative_to(base)), tuple(events)))
    return traces


def exit_code(report, fail_on_approval=True):
    summary = report["summary"]
    if summary["counts"]["DENY"] or summary.get("incident_failures", 0):
        return 2
    if fail_on_approval and summary["counts"]["REQUIRE_APPROVAL"]:
        return 3
    return 0


def run_check(root, config, contract):
    object_value(config, "config")
    for flag in ("fail_on_approval", "require_events"):
        if flag in config and not isinstance(config[flag], bool):
            raise ValueError(f"{flag} must be boolean")
    # Missing observations are never proof, even with legacy require_events=false.
    patterns = patterns_value(config.get("incident_globs", DEFAULT_INCIDENT_GLOBS), "incident_globs")
    base = Path(root).resolve()
    fixtures = [p for pattern in patterns for p in base.glob(pattern) if p.is_file()]
    traces = collect_trace_files(base, config.get("trace_globs", DEFAULT_TRACE_GLOBS), fixtures)
    events, sources = [], []
    for trace in traces:
        sources.append({
            "path": trace.path,
            "events": len(trace.events),
            "start_index": len(events),
            "normalized_events_sha256": normalized_events_sha256(trace.events),
        })
        events.extend(trace.events)
    if not events:
        raise ValueError("No tool-call events found. Run current tests with the ACP bootstrap or configure trace_globs for current JSON artifacts; historical incidents are not observations.")
    report = evaluate_trace(contract, events)
    report["sources"] = sources
    report["incidents"] = evaluate_incident_files(base, patterns, observed_events=events)
    summary = report["summary"]
    summary["incident_regressions"] = len(report["incidents"])
    summary["incident_failures"] = sum(not item["passed"] for item in report["incidents"])
    summary["fail_on_approval"] = config.get("fail_on_approval", True)
    summary["exit_code"] = exit_code(report, config.get("fail_on_approval", True))
    summary["ci_pass"] = summary["exit_code"] == 0
    return report


def render_github_actions(test_command, python_version="3.12", acp_install=DEFAULT_ACP_INSTALL):
    if not test_command.strip():
        raise ValueError("test_command is required to generate CI")
    wrapped = "python -m agent_control_plane.zero_code_runner -- sh -c " + shlex.quote(test_command)
    # Block scalar preserves colons, quotes and multiline customer test commands.
    wrapped = "\n".join("          " + line for line in wrapped.splitlines())
    return f'''name: ACP Authority + Regression Gate
on:
  pull_request:
  push:
permissions:
  contents: read
jobs:
  authority-and-regression:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "{python_version}"
      - name: Install project and ACP
        run: |
          python -m pip install .
          python -m pip install "{acp_install}"
      - name: Run existing agent/integration tests with ACP zero-code bootstrap
        run: |
{wrapped}
      - name: ACP authority + incident regression gate
        run: acp check --config .acp/config.json
'''
