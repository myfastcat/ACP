import unittest
import json
from agent_control_plane import __version__
from agent_control_plane.engine import ContractError, evaluate, evaluate_trace
from agent_control_plane.model import Decision

CONTRACT = {
    "schema_version": "1",
    "agent": {"name": "a"},
    "default": {"decision": "DENY"},
    "rules": [
        {"id": "read", "decision": "ALLOW", "when": [{"field": "action", "value": "read"}]},
        {"id": "approve", "decision": "REQUIRE_APPROVAL", "when": [{"field": "action", "value": "write"}, {"field": "context.amount", "op": "gt", "value": 10}]},
        {"id": "deny-delete", "decision": "DENY", "when": [{"field": "action", "value": "delete"}], "irreversible": True, "blast_radius": "organization"},
    ],
}


class EngineTest(unittest.TestCase):
    def test_allow(self):
        self.assertEqual(evaluate(CONTRACT, {"action": "read"}).decision, Decision.ALLOW)

    def test_approval(self):
        self.assertEqual(evaluate(CONTRACT, {"action": "write", "context": {"amount": 20}}).decision, Decision.REQUIRE_APPROVAL)

    def test_default_fail_closed(self):
        self.assertEqual(evaluate(CONTRACT, {"action": "unknown"}).decision, Decision.DENY)

    def test_empty_or_missing_conditions_are_rejected(self):
        for rule in (
            {"id": "allow-all-by-accident", "decision": "ALLOW"},
            {"id": "allow-all-by-accident", "decision": "ALLOW", "when": []},
        ):
            with self.subTest(rule=rule):
                with self.assertRaisesRegex(ContractError, "rule.when must be a non-empty list"):
                    evaluate({**CONTRACT, "rules": [rule]}, {"action": "delete_customer"})

    def test_required_event_fields_fail_closed_before_allow_rule(self):
        scoped = {**CONTRACT, "required_event_fields": ["context.environment", "context.target"]}
        missing = evaluate(scoped, {"action": "read", "context": {"environment": "test"}})
        self.assertEqual(missing.decision, Decision.DENY)
        self.assertEqual(missing.rule_id, "__required_event_fields__")
        self.assertIn("context.target", missing.reason)

        allowed = evaluate(scoped, {
            "action": "read",
            "context": {"environment": "test", "target": "fixture-company"},
        })
        self.assertEqual(allowed.decision, Decision.ALLOW)

    def test_missing_condition_fields_do_not_match_comparisons(self):
        for op, target in (("eq", None), ("ne", "prod"), ("not_in", ["prod"])):
            with self.subTest(op=op):
                contract = {
                    **CONTRACT,
                    "rules": [{
                        "id": f"allow-{op}",
                        "decision": "ALLOW",
                        "when": [{"field": "context.environment", "op": op, "value": target}],
                    }],
                }
                result = evaluate(contract, {"action": "read", "context": {}})
                self.assertEqual(result.decision, Decision.DENY)
                self.assertEqual(result.rule_id, "__default__")

    def test_exists_is_the_explicit_missing_field_operator(self):
        missing_contract = {
            **CONTRACT,
            "rules": [{
                "id": "allow-missing",
                "decision": "ALLOW",
                "when": [{"field": "context.environment", "op": "exists", "value": False}],
            }],
        }
        self.assertEqual(
            evaluate(missing_contract, {"action": "read", "context": {}}).decision,
            Decision.ALLOW,
        )

        present_contract = {
            **CONTRACT,
            "rules": [{
                "id": "allow-present",
                "decision": "ALLOW",
                "when": [{"field": "context.environment", "op": "exists", "value": True}],
            }],
        }
        self.assertEqual(
            evaluate(present_contract, {"action": "read", "context": {"environment": None}}).decision,
            Decision.ALLOW,
        )

    def test_deny_has_high_risk(self):
        self.assertGreaterEqual(evaluate(CONTRACT, {"action": "delete"}).risk_score, 60)

    def test_trace_ci_fails_on_deny(self):
        self.assertFalse(evaluate_trace(CONTRACT, [{"action": "read"}, {"action": "delete"}])["summary"]["ci_pass"])

    def test_report_identifies_product_version_and_contract(self):
        report = evaluate_trace(CONTRACT, [{"action": "read"}])
        self.assertEqual(report["summary"]["acp_version"], __version__)
        self.assertRegex(report["summary"]["contract_sha256"], r"^[0-9a-f]{64}$")

        reordered = json.loads(json.dumps(CONTRACT))
        reordered["agent"] = {"name": reordered["agent"]["name"]}
        reordered = {key: reordered[key] for key in reversed(reordered)}
        other = evaluate_trace(reordered, [{"action": "read"}])
        self.assertEqual(report["summary"]["contract_sha256"], other["summary"]["contract_sha256"])

    def test_invalid_contract(self):
        with self.assertRaises(ContractError):
            evaluate({"schema_version": "1", "agent": {}, "rules": []}, {"action": "x"})
        for required in ("context.environment", ["context.environment", "context.environment"], ["environment"]):
            with self.assertRaises(ContractError):
                evaluate({**CONTRACT, "required_event_fields": required}, {"action": "read"})


if __name__ == "__main__":
    unittest.main()
