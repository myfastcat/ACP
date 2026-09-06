from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from .discovery import discover_python_tools, draft_contract
from .engine import ContractError, evaluate_trace, validate_contract
from .integration import default_config, render_github_actions, run_check
from .normalize import TraceNormalizationError, normalize_trace


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


def _print_report(report: dict) -> None:
    s = report["summary"]
    print(f"events={s['events']} allow={s['counts']['ALLOW']} approval={s['counts']['REQUIRE_APPROVAL']} deny={s['counts']['DENY']} avg_risk={s['average_risk']} ci_pass={str(s['ci_pass']).lower()}")
    for source in report.get("sources", []):
        print(f"source={source['path']} events={source['events']}")
    for r in report["results"]:
        print(f"[{r['decision']}] {r['action']} <- {r['rule_id']} (risk={r['risk_score']}) {r['reason']}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="acp", description="Discover, normalize and enforce AI-agent authority boundaries.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    init = sub.add_parser("init", help="Discover agent tools and generate a conservative draft authority contract")
    init.add_argument("path", nargs="?", default=".")
    init.add_argument("--agent", default=None, help="Agent name; defaults to repository/directory name")
    init.add_argument("--out", default=".acp/authority.json")
    init.add_argument("--ci", action="store_true", help="Generate non-invasive ACP config and GitHub Actions gate")
    init.add_argument("--test-command", default=None, help="Existing integration-test command used by generated CI, e.g. 'pytest -q'")

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

    check = sub.add_parser("check", help="Collect existing trace artifacts and run the authority gate without app instrumentation")
    check.add_argument("--config", default=".acp/config.json")
    check.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)
    try:
        if args.cmd == "init":
            root = Path(args.path).resolve()
            tools = discover_python_tools(root)
            contract = draft_contract(args.agent or root.name, tools)
            _write(args.out, contract)
            frameworks = sorted({t.framework for t in tools})
            generated = [args.out]
            if args.ci:
                if not args.test_command:
                    raise ValueError("--test-command is required with --ci so ACP can run your existing tests unchanged")
                _write(".acp/config.json", default_config(args.out))
                _write_text(".github/workflows/acp.yml", render_github_actions(args.test_command))
                generated.extend([".acp/config.json", ".github/workflows/acp.yml"])
            print(
                f"discovered={len(tools)} frameworks={','.join(frameworks)} "
                f"review_required=true generated={','.join(generated)}"
            )
            return 0

        if args.cmd == "normalize":
            events = normalize_trace(_load(args.trace))
            _write(args.out, events)
            print(f"events={len(events)} trace={args.out}")
            return 0

        if args.cmd == "check":
            config_path = Path(args.config).resolve()
            config = _load(str(config_path))
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
            if report["summary"]["counts"]["DENY"] > 0:
                return 2
            if config.get("fail_on_approval", True) and report["summary"]["counts"]["REQUIRE_APPROVAL"] > 0:
                return 3
            return 0

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
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            _print_report(report)
        if report["summary"]["counts"]["DENY"] > 0:
            return 2
        if args.fail_on_approval and report["summary"]["counts"]["REQUIRE_APPROVAL"] > 0:
            return 3
        return 0
    except (OSError, json.JSONDecodeError, ContractError, TraceNormalizationError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
