from __future__ import annotations
import hashlib
import json
import math
import re
from typing import Any
from . import __version__
from .model import Decision, Evaluation
from .validation import object_value, text_value, events_value

DECISION_ORDER = {Decision.ALLOW: 0, Decision.REQUIRE_APPROVAL: 1, Decision.DENY: 2}
BLAST_RISK = {"none": 0, "single_record": 5, "team": 12, "customer": 18, "organization": 25, "external": 30}


class ContractError(ValueError):
    pass


def _get(event: dict[str, Any], path: str) -> Any:
    cur: Any = event
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def _lookup(event: dict[str, Any], path: str) -> tuple[bool, Any]:
    """Distinguish an absent path from a present field whose value is null."""
    cur: Any = event
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return False, None
        cur = cur[part]
    return True, cur


def _json_equal(left: Any, right: Any) -> bool:
    """Compare JSON values without Python's bool/int equality leak."""
    if isinstance(left, bool) or isinstance(right, bool):
        return type(left) is bool and type(right) is bool and left == right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return left == right
    if type(left) is not type(right):
        return False
    if isinstance(left, list):
        return len(left) == len(right) and all(_json_equal(a, b) for a, b in zip(left, right))
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(_json_equal(left[key], right[key]) for key in left)
    return left == right


def _json_number(value: Any) -> bool:
    """Accept only finite JSON numbers; booleans are a distinct JSON type."""
    return type(value) in {int, float} and math.isfinite(value)


def _match_condition(event: dict[str, Any], cond: dict[str, Any]) -> bool:
    present, value = _lookup(event, cond["field"])
    op = cond.get("op", "eq")
    target = cond.get("value")
    if op == "exists": return present is bool(target)
    # An omitted value is unknown, not evidence that a comparison succeeds.
    # This especially prevents `ne` and `not_in` allow rules from matching
    # incomplete observations. Use `exists:false` to match absence explicitly.
    if not present: return False
    if op == "eq": return _json_equal(value, target)
    if op == "ne": return not _json_equal(value, target)
    if op == "in": return any(_json_equal(value, item) for item in target)
    if op == "not_in": return not any(_json_equal(value, item) for item in target)
    if op in {"gt", "gte", "lt", "lte"}:
        if not (_json_number(value) and _json_number(target)):
            return False
        if op == "gt": return value > target
        if op == "gte": return value >= target
        if op == "lt": return value < target
        return value <= target
    raise ContractError(f"Unsupported operator: {op}")


def _conditions_match(event: dict[str, Any], conditions: list[dict[str, Any]]) -> bool:
    return all(_match_condition(event, c) for c in conditions)


def _risk(rule: dict[str, Any], event: dict[str, Any]) -> tuple[int, str, bool]:
    blast = rule.get("blast_radius", "single_record")
    irreversible = bool(rule.get("irreversible", False))
    score = int(rule.get("risk", 10)) + BLAST_RISK.get(blast, 10)
    if irreversible:
        score += 25
    amount = _get(event, "context.amount")
    if _json_number(amount):
        # Amount can increase risk, but malformed, boolean, non-finite or
        # negative observations must never crash evaluation or reduce risk.
        score += max(0, min(20, int(amount // 1000)))
    return min(score, 100), blast, irreversible


def validate_contract(contract: dict[str, Any]) -> None:
    try:
        object_value(contract, "contract")
        if contract.get("schema_version") != "1":
            raise ValueError("schema_version must be '1'")
        text_value(object_value(contract.get("agent"), "agent").get("name"), "agent.name")
        default = object_value(contract.get("default", {"decision": "DENY"}), "default")
        if default.get("decision", "DENY") not in {d.value for d in Decision}:
            raise ValueError("invalid default decision")
        required_event_fields = contract.get("required_event_fields", [])
        if not isinstance(required_event_fields, list):
            raise ValueError("required_event_fields must be a list")
        for field in required_event_fields:
            text_value(field, "required_event_fields entry")
            if field == "action" or not re.fullmatch(r"[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)+", field):
                raise ValueError("required_event_fields entries must be dotted event paths such as context.environment")
        if len(set(required_event_fields)) != len(required_event_fields):
            raise ValueError("required_event_fields must not contain duplicates")
        rules = contract.get("rules")
        if not isinstance(rules, list) or not rules:
            raise ValueError("rules must be a non-empty list")
        seen = set()
        for rule in rules:
            object_value(rule, "rule")
            rid = text_value(rule.get("id"), "rule.id")
            if rid in seen:
                raise ValueError("each rule.id must be unique")
            seen.add(rid)
            if rule.get("decision") not in {d.value for d in Decision}:
                raise ValueError(f"invalid decision in rule {rid}")
            if type(rule.get("risk", 10)) is not int or not 0 <= rule.get("risk", 10) <= 100:
                raise ValueError("risk must be an integer from 0 to 100")
            if rule.get("blast_radius", "single_record") not in BLAST_RISK:
                raise ValueError("invalid blast_radius")
            if type(rule.get("irreversible", False)) is not bool:
                raise ValueError("irreversible must be boolean")
            conditions = rule.get("when")
            if not isinstance(conditions, list) or not conditions:
                raise ValueError("rule.when must be a non-empty list; use default for fallback behavior")
            for cond in conditions:
                object_value(cond, "condition")
                text_value(cond.get("field"), "condition.field")
                op = cond.get("op", "eq")
                if op not in {"eq", "ne", "in", "not_in", "gt", "gte", "lt", "lte", "exists"}:
                    raise ValueError(f"Unsupported operator: {op}")
                if op in {"in", "not_in"} and not isinstance(cond.get("value"), list):
                    raise ValueError("membership condition value must be a list")
                if op == "exists" and type(cond.get("value")) is not bool:
                    raise ValueError("exists value must be boolean")
                if op in {"gt", "gte", "lt", "lte"} and not _json_number(cond.get("value")):
                    raise ValueError("ordering condition value must be a finite JSON number")
    except ValueError as exc:
        raise ContractError(str(exc)) from exc


def evaluate(contract: dict[str, Any], event: dict[str, Any]) -> Evaluation:
    validate_contract(contract)
    events_value([event])
    missing = [field for field in contract.get("required_event_fields", []) if _get(event, field) is None]
    if missing:
        return Evaluation(
            decision=Decision.DENY,
            rule_id="__required_event_fields__",
            reason=f"Missing required event field(s): {', '.join(missing)}; fail closed.",
            risk_score=80,
            blast_radius="external",
            irreversible=False,
            matched_conditions=(),
        )
    matched = []
    for rule in contract["rules"]:
        if _conditions_match(event, rule.get("when", [])):
            decision = Decision(rule["decision"])
            risk, blast, irreversible = _risk(rule, event)
            matched.append(Evaluation(
                decision=decision,
                rule_id=rule["id"],
                reason=rule.get("reason", "matched contract rule"),
                risk_score=risk,
                blast_radius=blast,
                irreversible=irreversible,
                approval_group=rule.get("approval_group"),
                matched_conditions=tuple(c["field"] for c in rule.get("when", [])),
            ))
    if not matched:
        default = contract.get("default", {"decision": "DENY"})
        d = Decision(default.get("decision", "DENY"))
        return Evaluation(d, "__default__", default.get("reason", "No rule matched; fail closed."), 50, "unknown", False)
    return max(matched, key=lambda e: (DECISION_ORDER[e.decision], e.risk_score))


def evaluate_trace(contract: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, Any]:
    validate_contract(contract)
    events_value(events)
    contract_sha256 = hashlib.sha256(
        json.dumps(contract, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    results = []
    counts = {d.value: 0 for d in Decision}
    total_risk = 0
    for i, event in enumerate(events):
        ev = evaluate(contract, event)
        counts[ev.decision.value] += 1
        total_risk += ev.risk_score
        results.append({
            "index": i,
            "action": event.get("action"),
            "decision": ev.decision.value,
            "rule_id": ev.rule_id,
            "reason": ev.reason,
            "risk_score": ev.risk_score,
            "blast_radius": ev.blast_radius,
            "irreversible": ev.irreversible,
            "approval_group": ev.approval_group,
        })
    n = max(len(events), 1)
    return {
        "summary": {
            "acp_version": __version__,
            "contract_sha256": contract_sha256,
            "events": len(events),
            "counts": counts,
            "approval_load": round(counts["REQUIRE_APPROVAL"] / n, 3),
            "average_risk": round(total_risk / n, 1),
            "ci_pass": counts["DENY"] == 0,
        },
        "results": results,
    }
