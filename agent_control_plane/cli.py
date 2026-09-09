from __future__ import annotations
import argparse
import json
import sys
import re
from pathlib import Path
from .discovery import discover_python_tools, draft_contract
from .engine import ContractError, evaluate_trace, validate_contract
from .integration import default_config, render_github_actions, run_check, exit_code
from .validation import object_value
from .normalize import TraceNormalizationError, normalize_trace
from .replay import ReplayError, add_assertion, dump as replay_dump, evaluate_fixture, evidence_pack, load as replay_load, normalize_incident


def _load(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write(path: str, value) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _write_text(path: str, value: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(value, encoding="utf-8")


def _detect_test_command(root: Path) -> str | None:
    """Return a conservative existing Python test command when the runner is unambiguous.

    Detection is static only: init never executes the candidate command. Explicit runner
    configuration is preferred; otherwise import evidence in tests is used. Mixed pytest
    and unittest evidence without an explicit pytest configuration is treated as ambiguous.
    """
    pytest_configured = (root / "pytest.ini").is_file()
    for path, marker in ((root / "pyproject.toml", "[tool.pytest.ini_options]"), (root / "setup.cfg", "[tool:pytest]")):
        if path.is_file():
            try:
                if marker in path.read_text(encoding="utf-8"):
                    pytest_configured = True
            except (OSError, UnicodeError):
                pass
    if pytest_configured:
        return "python -m pytest"

    tests = root / "tests"
    if not tests.is_dir():
        return None
    saw_pytest = False
    saw_unittest = False
    for index, path in enumerate(tests.rglob("test*.py")):
        if index >= 200:
            return None
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            return None
        saw_pytest = saw_pytest or bool(re.search(r"(?m)^\s*(?:import\s+pytest\b|from\s+pytest\b)", source))
        saw_unittest = saw_unittest or bool(re.search(r"(?m)^\s*(?:import\s+unittest\b|from\s+unittest\b)", source))
        if saw_pytest and saw_unittest:
            return None
    if saw_pytest:
        return "python -m pytest"
    if saw_unittest:
        return "python -m unittest discover -s tests -v"
    return None


def _print_report(report: dict) -> None:
    s = report["summary"]
    print(f"events={s['events']} allow={s['counts']['ALLOW']} approval={s['counts']['REQUIRE_APPROVAL']} deny={s['counts']['DENY']} incident_regressions={s.get('incident_regressions', 0)} incident_failures={s.get('incident_failures', 0)} avg_risk={s['average_risk']} ci_pass={str(s['ci_pass']).lower()}")
    for source in report.get("sources", []):
        print(f"source={source['path']} events={source['events']}")
    for r in report["results"]:
        print(f"[{r['decision']}] {r['action']} <- {r['rule_id']} (risk={r['risk_score']}) {r['reason']}")
    for incident in report.get("incidents", []):
        print(f"incident={incident['incident_id']} passed={str(incident['passed']).lower()} path={incident['path']} failures={len(incident['failures'])}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="acp", description="Control agent authority and turn incidents into deterministic CI regressions.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    init = sub.add_parser("init", help="Discover agent tools and generate a conservative draft authority contract")
    init.add_argument("path", nargs="?", default=".")
    init.add_argument("--agent", default=None, help="Agent name; defaults to repository/directory name")
    init.add_argument("--out", default=".acp/authority.json")
    init.add_argument("--ci", action="store_true", help="Generate non-invasive ACP config and GitHub Actions gate")
    init.add_argument("--test-command", default=None, help="Existing integration-test command used by generated CI; omit when ACP can safely detect pytest/unittest")

    normalize = sub.add_parser("normalize", help="Normalize common tool-call traces to ACP {action, context} events")
    normalize.add_argument("trace")
    normalize.add_argument("--out", default="acp-trace.json")

    validate = sub.add_parser("validate")
    validate.add_argument("contract")

    evaluate = sub.add_parser("eval")
    evaluate.add_argument("contract")
    evaluate.add_argument("trace")
    evaluate.add_argument("--json", action="store_true")
    evaluate.add_argument("--fail-on-approval", action="store_true")
    evaluate.add_argument("--normalize", action="store_true", help="Normalize a raw framework trace before evaluation")

    check = sub.add_parser("check", help="Run authority and committed incident regression gates")
    check.add_argument("--config", default=".acp/config.json")
    check.add_argument("--json", action="store_true")

    incident = sub.add_parser("incident", help="Convert agent incidents into deterministic regression fixtures")
    incident_sub = incident.add_subparsers(dest="incident_cmd", required=True)
    incident_import = incident_sub.add_parser("import", help="Normalize an incident trace into a CI-discovered ACP fixture")
    incident_import.add_argument("trace")
    incident_import.add_argument("--incident-id", default="incident")
    incident_import.add_argument("--out", default=None, help="Fixture path; defaults to .acp/incidents/<incident-id>.json")

    incident_assert = incident_sub.add_parser("assert", help="Add a business invariant without hand-editing JSON")
    incident_assert.add_argument("fixture")
    assertion_group = incident_assert.add_mutually_exclusive_group(required=True)
    assertion_group.add_argument("--must-not-occur", dest="must_not_occur", metavar="ACTION")
    assertion_group.add_argument("--must-occur", dest="must_occur", metavar="ACTION")
    assertion_group.add_argument("--max-occurrences", dest="max_occurrences", metavar="ACTION")
    incident_assert.add_argument("--max", type=int, default=None, help="Required with --max-occurrences")

    incident_replay = incident_sub.add_parser("replay", help="Replay one incident fixture and optionally write an evidence pack")
    incident_replay.add_argument("fixture")
    incident_replay.add_argument("--json", action="store_true")
    incident_replay.add_argument("--evidence")

    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 4
    try:
        if args.cmd == "init":
            root = Path(args.path).resolve()
            test_command = args.test_command
            test_command_source = "explicit" if test_command else None
            if args.ci and not test_command:
                test_command = _detect_test_command(root)
                test_command_source = "detected" if test_command else None
                if not test_command:
                    raise ValueError("--test-command is required with --ci when ACP cannot safely detect one unambiguous pytest/unittest runner")
            targets = [Path(args.out)]
            if args.ci:
                targets += [Path(".acp/config.json"), Path(".github/workflows/acp.yml")]
            if any(p.exists() for p in targets):
                raise ValueError("Init would overwrite existing configuration; use a fresh directory or edit the reviewed files")
            tools = discover_python_tools(root)
            contract = draft_contract(args.agent or root.name, tools)
            _write(args.out, contract)
            frameworks = sorted({t.framework for t in tools})
            generated = [args.out]
            if args.ci:
                _write(".acp/config.json", default_config(args.out))
                _write_text(".github/workflows/acp.yml", render_github_actions(test_command))
                Path(".acp/incidents").mkdir(parents=True, exist_ok=True)
                generated.extend([".acp/config.json", ".github/workflows/acp.yml", ".acp/incidents/"])
            suffix = f" test_command_source={test_command_source}" if args.ci else ""
            print(f"discovered={len(tools)} frameworks={','.join(frameworks)} review_required=true generated={','.join(generated)}{suffix}")
            return 0

        if args.cmd == "normalize":
            events = normalize_trace(_load(args.trace))
            _write(args.out, events)
            print(f"events={len(events)} trace={args.out}")
            return 0

        if args.cmd == "incident":
            if args.incident_cmd == "import":
                if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", args.incident_id):
                    raise ValueError("incident-id must be a safe filename identifier")
                fixture = normalize_incident(replay_load(args.trace), args.incident_id)
                out = args.out or f".acp/incidents/{args.incident_id}.json"
                if Path(out).exists():
                    raise ValueError("Incident fixture already exists; choose a new output to preserve its invariants")
                replay_dump(out, fixture)
                incident_events = fixture.get("incident_events", fixture.get("events", []))
                print(f"events={len(incident_events)} fixture={out} next=acp incident assert {out} --must-not-occur <ACTION>")
                return 0
            if args.incident_cmd == "assert":
                fixture = replay_load(args.fixture)
                if args.must_not_occur:
                    add_assertion(fixture, "must_not_occur", args.must_not_occur)
                elif args.must_occur:
                    add_assertion(fixture, "must_occur", args.must_occur)
                else:
                    add_assertion(fixture, "max_occurrences", args.max_occurrences, args.max)
                replay_dump(args.fixture, fixture)
                print(f"fixture={args.fixture} assertions={len(fixture.get('assertions', []))} ci_discovery=true")
                return 0
            fixture = replay_load(args.fixture)
            report = evaluate_fixture(fixture)
            if args.evidence:
                replay_dump(args.evidence, evidence_pack(fixture, report))
            print(json.dumps(report, indent=2) if args.json else f"passed={str(report['passed']).lower()} events={report['event_count']} failures={len(report['failures'])}")
            return 0 if report["passed"] else 2

        if args.cmd == "check":
            config_path = Path(args.config).resolve()
            config = object_value(_load(str(config_path)), "config")
            root = config_path.parent.parent if config_path.parent.name == ".acp" else Path.cwd()
            contract_path = Path(config.get("contract", ".acp/authority.json"))
            if not contract_path.is_absolute():
                contract_path = root / contract_path
            contract = _load(str(contract_path))
            validate_contract(contract)
            report = run_check(root, config, contract)
            if args.json:
                print(json.dumps(report, indent=2))
            else:
                _print_report(report)
            return report["summary"]["exit_code"]

        contract = _load(args.contract)
        if args.cmd == "validate":
            validate_contract(contract)
            print("VALID")
            return 0

        raw_events = _load(args.trace)
        events = normalize_trace(raw_events) if args.normalize else raw_events
        if not isinstance(events, list):
            raise ContractError("trace must be a JSON array; use --normalize for framework-native traces")
        report = evaluate_trace(contract, events)
        report["summary"]["exit_code"] = exit_code(report, args.fail_on_approval)
        report["summary"]["ci_pass"] = report["summary"]["exit_code"] == 0
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            _print_report(report)
        if report["summary"]["counts"]["DENY"] > 0:
            return 2
        if args.fail_on_approval and report["summary"]["counts"]["REQUIRE_APPROVAL"] > 0:
            return 3
        return 0
    except (OSError, UnicodeError, ContractError, TraceNormalizationError, ReplayError, ValueError, TypeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
