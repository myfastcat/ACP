# Agent Control Plane

**Executable authority contracts for production AI agents.**

ACP turns agent authority boundaries into deterministic, testable policy. It can now reduce the integration tax by discovering common Python agent tools, generating a conservative draft contract, normalizing common tool-call traces, and evaluating them in CI.

## Quick start: from agent repo to authority check

Requires Python 3.10+ and has no runtime dependencies.

```bash
# From the root of an agent repository
acp init . --agent support-agent --out authority.json

# Review the generated authority.json. Generated contracts are drafts and fail closed.

# Normalize a framework-native trace
acp normalize raw-trace.json --out acp-trace.json

# Evaluate it
acp eval authority.json acp-trace.json
```

You can also evaluate a raw supported trace directly:

```bash
acp eval authority.json raw-trace.json --normalize
```

## What `acp init` does

ACP statically scans Python files and currently recognizes common decorated tools:

- OpenAI Agents SDK style `@function_tool`
- MCP style `@mcp.tool()` / `@server.tool()`
- generic `@tool`

For every discovered tool ACP generates a draft rule and a source inventory. The heuristic is deliberately conservative:

- read/search/list/get style tools → `ALLOW`
- obvious state-changing tools → `REQUIRE_APPROVAL`
- destructive or money-moving tools → `DENY`
- unknown semantics → `REQUIRE_APPROVAL`
- undiscovered actions → default `DENY`

Every generated contract is marked `review_required: true`. ACP does **not** pretend static naming heuristics are sufficient for production authorization; the user reviews the proposed boundary instead of authoring it from scratch.

## Trace normalization

ACP accepts its native event format:

```json
{"action": "issue_refund", "context": {"amount": 42}}
```

It also normalizes common shapes such as:

```json
{"tool": "issue_refund", "arguments": {"amount": 42}}
```

and OpenAI-style function calls:

```json
{"type": "function_call", "name": "issue_refund", "arguments": "{\"amount\": 42}"}
```

Nested `tool_calls`, `output`, `messages`, `events`, `items`, and `trace` containers are walked automatically.

## Contract model

An **Agent Authority Contract** answers, action by action:

- **ALLOW** — the agent owns this action.
- **REQUIRE_APPROVAL** — the agent may propose it, but a human must approve.
- **DENY** — the action is outside delegated authority.

Example:

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

The intended flow is now:

```text
agent repo → acp init → review contract → capture raw tool trace → acp normalize/eval → CI gate
```

## Design principles

ACP is deliberately **not an LLM judge**. The final authority decision is deterministic, inspectable, versionable and testable. Automation reduces setup effort, but generated contracts stay explicit and reviewable.

The current risk score combines rule risk, declared blast radius, irreversibility, and transaction amount. The score is advisory; `ALLOW / REQUIRE_APPROVAL / DENY` is the enforcement primitive.

## Current scope

This version focuses on reducing setup friction for pre-deployment/CI enforcement. It is not yet a runtime gateway, identity system, secrets manager, centralized approval service, or general policy-as-code replacement.

The next production step is a runtime enforcement SDK/middleware that evaluates every proposed tool execution before the tool is actually called.

## Feedback wanted

Would you connect an agent repository and review an automatically generated authority contract before deployment? Please use GitHub Issue #3 and share the framework you use, the tools ACP should discover automatically, and which actions are hardest to classify safely.
