import unittest
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

    def test_deny_has_high_risk(self):
        self.assertGreaterEqual(evaluate(CONTRACT, {"action": "delete"}).risk_score, 60)

    def test_trace_ci_fails_on_deny(self):
        self.assertFalse(evaluate_trace(CONTRACT, [{"action": "read"}, {"action": "delete"}])["summary"]["ci_pass"])

    def test_invalid_contract(self):
        with self.assertRaises(ContractError):
            evaluate({"schema_version": "1", "agent": {}, "rules": []}, {"action": "x"})


if __name__ == "__main__":
    unittest.main()
