# Agent Control Plane

**Executable authority contracts for production AI agents — with a zero-code integration target.**

ACP turns agent authority boundaries into deterministic, testable policy. The default product experience is **non-invasive**: ACP should observe framework-native traces/events and integrate at the repository/CI boundary rather than requiring users to add ACP decorators, wrappers, or `with acp.trace(...)` calls to agent business code.

## User experience

The target flow is:

```text
agent repo
  → acp init
  → ACP detects supported framework/tools
  → ACP generates a conservative authority contract draft
  → user reviews/approves the authority boundary
  → existing agent/integration tests run unchanged
  → ACP adapter consumes framework-native trace/event output
  → normalize to {action, context}
  → deterministic authority evaluation
  → CI PASS / REQUIRE_APPROVAL / DENY
```

### What the user needs to do

1. **Install ACP in the repository/CI environment.** No ACP imports are required in agent business code for a supported zero-code adapter.
2. **Run `acp init` from the agent repository root.** ACP discovers supported Python tools and drafts the authority contract.
3. **Review the generated authority contract.** The user confirms the real business boundary: which actions are `ALLOW`, `REQUIRE_APPROVAL`, or `DENY`, including amount/environment/tenant constraints where relevant. ACP must not infer final production authorization solely from function names.
4. **Tell ACP where existing framework-native traces/events come from when auto-detection cannot determine it.** This is configuration, not application-code instrumentation. Supported adapters should prefer existing framework tracing, callbacks, logs, test artifacts, or event streams.
5. **Keep normal agent/integration tests running.** Users should not write ACP-specific traces by hand for the normal path. Existing test executions are the source of observed tool calls. Teams may additionally keep synthetic security/replay traces for important boundary cases.
6. **Commit the reviewed authority contract and ACP CI configuration.** Pull requests then run the authority gate automatically.
7. **Review CI failures when authority changes.** A new denied or approval-required action is treated as an authority regression/change requiring an explicit decision.

For a supported framework, users should **not** need to:

- add `@acp.trace` / `@acp.tool` decorators;
- wrap `agent.run()` in ACP code;
- modify every tool implementation;
- manually convert tool calls to `{action, context}`;
- hand-author a trace for every CI run.

If ACP cannot observe a framework without application instrumentation, it must report that zero-code capture is unsupported and fall back explicitly to a configured trace file/source. It must not silently claim capture succeeded.

## Quick start

Requires Python 3.10+ and has no runtime dependencies.

```bash
# From the root of an agent repository
acp init . --agent support-agent --out .acp/authority.json

# Review .acp/authority.json before using it as a production authority boundary.

# Current generic fallback when a framework-native trace file already exists:
acp eval .acp/authority.json raw-trace.json --normalize --fail-on-approval
```

`acp init` currently discovers common Python decorated tools:

- OpenAI Agents SDK style `@function_tool`
- MCP style `@mcp.tool()` / `@server.tool()`
- generic `@tool`

For every discovered tool ACP generates a draft rule and source inventory. The heuristic is deliberately conservative:

- read/search/list/get style tools → `ALLOW`
- obvious state-changing tools → `REQUIRE_APPROVAL`
- destructive or money-moving tools → `DENY`
- unknown semantics → `REQUIRE_APPROVAL`
- undiscovered actions → default `DENY`

Every generated contract is marked `review_required: true`.

## Where authority comes from

Authority has two inputs:

```text
repo/tool discovery + ACP conservative draft
                    +
       human-reviewed business authority
                    ↓
            .acp/authority.json
```

Static discovery reduces setup work; it does not grant production authority. The reviewed contract is the version-controlled source of truth.

## Where traces come from

ACP distinguishes two trace sources:

1. **Observed framework-native traces/events** — emitted by normal development/staging/integration-test agent execution. Zero-code adapters should consume these without modifying application code.
2. **Synthetic/replay security traces** — optional, deliberately constructed boundary cases used to prove that dangerous actions remain denied or approval-gated.

ACP normalizes supported shapes to:

```json
{"action": "issue_refund", "context": {"amount": 42}}
```

Common input shapes already accepted by the normalizer include generic `{tool, arguments}`, OpenAI-style `function_call`, and nested `tool_calls`, `output`, `messages`, `events`, `items`, and `trace` containers.

## CI integration

The desired customer CI gate is:

```text
checkout
  → install ACP
  → validate reviewed authority contract
  → run the repository's existing agent/integration tests
  → collect/locate supported framework-native trace output
  → ACP normalize + evaluate
  → fail CI on DENY (and optionally REQUIRE_APPROVAL)
```

The current generic evaluation command is:

```bash
acp eval .acp/authority.json raw-trace.json --normalize --fail-on-approval
```

Exit codes:

| Exit code | Meaning |
|---|---|
| 0 | no denied actions |
| 2 | at least one denied action |
| 3 | approval required and `--fail-on-approval` was used |
| 4 | invalid contract / input |

ACP's own repository CI tests the evaluator and deny path. Customer zero-code framework adapters and automatic customer-CI generation are the next implementation layer; this README intentionally distinguishes that target experience from capabilities already shipped.

## Integration hierarchy

ACP uses this priority order:

```text
Level 1 — Zero-code adapter
framework-native trace/event/log/test artifact → ACP

Level 2 — Configuration-only adapter
user points ACP at an existing trace/event source → ACP

Level 3 — Explicit instrumentation fallback
only when the framework exposes no observable interface
```

ACP must not make Level 3 the default product experience.

## Design principles

ACP is deliberately **not an LLM judge**. The final authority decision is deterministic, inspectable, versionable and testable. Automation reduces setup effort, but generated contracts stay explicit and reviewable.

The risk score is advisory; `ALLOW / REQUIRE_APPROVAL / DENY` is the enforcement primitive.

## Current scope

Shipped today: static tool discovery, conservative contract drafting, trace normalization, deterministic evaluation, and ACP's own CI checks.

Next: framework-specific zero-code trace adapters and generated customer CI configuration. Runtime enforcement remains a later layer because it sits directly in the production execution path and has different reliability/security requirements.

## Feedback wanted

Would you install ACP if integration meant `acp init` + review the generated authority contract + normal CI, with no changes to your agent business code? Please use GitHub Issue #3 and tell us which agent framework and tracing/event mechanism your team uses.
