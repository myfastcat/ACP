"""Current-run trace collection and the combined authority/incident CI gate."""
from __future__ import annotations

import hashlib
import json
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
    if type(summary.get("events")) is not int or summary["events"] < 1:
        raise ValueError("Evidence pack report.summary.events must be a positive integer")
    if summary["events"] != len(results):
        raise ValueError("Evidence pack report event count does not match results")
    counts = object_value(summary.get("counts"), "Evidence pack report.summary.counts")
    decisions = ("ALLOW", "REQUIRE_APPROVAL", "DENY")
    if any(type(counts.get(name)) is not int or counts[name] < 0 for name in decisions):
        raise ValueError("Evidence pack report counts must be non-negative integers")
    if sum(counts[name] for name in decisions) != summary["events"]:
        raise ValueError("Evidence pack report decision counts do not match events")
    if type(summary.get("ci_pass")) is not bool or type(summary.get("exit_code")) is not int:
        raise ValueError("Evidence pack report must include typed ci_pass and exit_code")
    digest = summary.get("contract_sha256")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("Evidence pack report contract_sha256 must be a lowercase SHA-256 digest")
    text_value(summary.get("acp_version"), "Evidence pack report.summary.acp_version")


def verify_check_evidence_pack(pack: dict) -> dict:
    """Return the report only when a saved evidence pack is structurally intact."""
    if not isinstance(pack, dict):
        raise ValueError("Evidence pack must be a JSON object")
    if pack.get("schema") != "acp-check-evidence/v1":
        raise ValueError("Unsupported evidence schema")
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
