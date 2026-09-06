from __future__ import annotations
import argparse
import json
import sys
from .engine import ContractError, evaluate_trace, validate_contract


def _load(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="acp", description="Evaluate AI-agent action traces against an Agent Authority Contract.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    validate = sub.add_parser("validate")
    validate.add_argument("contract")
    evaluate = sub.add_parser("eval")
    evaluate.add_argument("contract")
    evaluate.add_argument("trace")
    evaluate.add_argument("--json", action="store_true")
    evaluate.add_argument("--fail-on-approval", action="store_true")
    args = parser.parse_args(argv)
    try:
        contract = _load(args.contract)
        if args.cmd == "validate":
            validate_contract(contract)
            print("VALID")
            return 0
        events = _load(args.trace)
        if not isinstance(events, list):
            raise ContractError("trace must be a JSON array")
        report = evaluate_trace(contract, events)
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            s = report["summary"]
            print(f"events={s['events']} allow={s['counts']['ALLOW']} approval={s['counts']['REQUIRE_APPROVAL']} deny={s['counts']['DENY']} avg_risk={s['average_risk']} ci_pass={str(s['ci_pass']).lower()}")
            for r in report["results"]:
                print(f"[{r['decision']}] {r['action']} <- {r['rule_id']} (risk={r['risk_score']}) {r['reason']}")
        if report["summary"]["counts"]["DENY"] > 0:
            return 2
        if args.fail_on_approval and report["summary"]["counts"]["REQUIRE_APPROVAL"] > 0:
            return 3
        return 0
    except (OSError, json.JSONDecodeError, ContractError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
