# Agent Control Plane

**Executable authority contracts for production AI agents.**

Most agent-governance documents describe what an agent *should* do. Agent Control Plane (ACP) turns that boundary into a deterministic contract that can run before deployment and in CI.

An **Agent Authority Contract** answers, action by action:

- **ALLOW** — the agent owns this action.
- **REQUIRE_APPROVAL** — the agent may propose it, but a named human group must approve.
- **DENY** — the action is outside delegated authority.

ACP also reports risk score, blast radius, irreversible actions, approval load, and a CI pass/fail decision.

## 60-second demo

Requires Python 3.10+ and has no runtime dependencies.

```bash
python -m agent_control_plane.cli validate examples/procurement-contract.json
python -m agent_control_plane.cli eval examples/procurement-contract.json examples/procurement-trace.json
```

The sample procurement agent can read vendors and create small requests, needs approval for medium purchases, and is prohibited from moving money or deleting vendor master data.

Because the sample trace attempts `payment.execute`, ACP exits with code `2`. This makes the authority boundary enforceable in CI rather than merely documented.

## Contract model

```json
{
  "schema_version": "1",
  "agent": {"name": "procurement-agent"},
  "default": {"decision": "DENY"},
  "rules": [{
    "id": "payment-deny",
    "decision": "DENY",
    "when": [{"field": "action", "op": "eq", "value": "payment.execute"}],
    "blast_radius": "external",
    "irreversible": true,
    "reason": "Agent may never move money."
  }]
}
```

Supported condition operators: `eq`, `ne`, `in`, `not_in`, `gt`, `gte`, `lt`, `lte`, `exists`.

If no rule matches, ACP **fails closed** by default.

## CI behavior

```bash
acp eval authority.json replay-trace.json
```

| Exit code | Meaning |
|---|---|
| 0 | no denied actions |
| 2 | at least one denied action |
| 3 | approval required and `--fail-on-approval` was used |
| 4 | invalid contract / input |

A practical flow is: record an agent's proposed or replayed tool calls → normalize them to `{action, context}` events → evaluate them against the authority contract → block deployment when the trace crosses the boundary.

## Design principles

ACP is deliberately **not an LLM judge**. The final authority boundary is deterministic, inspectable, versionable and testable. LLMs can help draft contracts or normalize traces, but the actual permission decision should not depend on another probabilistic model.

The current risk score combines rule risk, declared blast radius, irreversibility, and transaction amount. The score is advisory; ALLOW / REQUIRE_APPROVAL / DENY is the enforcement primitive.

## Feedback wanted

The first validation question is intentionally narrow:

> **Would you put an executable authority contract in CI before deploying an autonomous agent?**

Please use GitHub Issue #3 and share the kind of agent you run, its highest-risk action, and whether ALLOW / REQUIRE_APPROVAL / DENY is expressive enough for your workflow.

## Status

v0.1 is an MVP for design-partner validation. It is not yet a runtime gateway, identity system, secrets manager, or general policy-as-code replacement.
