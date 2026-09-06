# Agent Control Plane

**Executable authority contracts for production AI agents with a non-invasive CI integration path.**

ACP turns agent authority boundaries into deterministic, testable policy. The default product direction is **non-invasive**: integrate at the repository/CI boundary and consume trace artifacts already produced by normal agent/integration tests instead of requiring ACP decorators, wrappers, or changes to every tool.

## What the user does

For the non-invasive path, the user only needs to:

1. Install ACP in the repo/CI environment.
2. Run `acp init` to discover tools and generate a conservative authority contract draft.
3. Review the generated authority contract and confirm real business rules such as `ALLOW`, `REQUIRE_APPROVAL`, `DENY`, amount thresholds, environments, tenants, and approval groups.
4. Keep running the repository's existing agent/integration tests unchanged.
5. Ensure those tests/frameworks already emit JSON tool-call / trace artifacts, or edit `.acp/config.json` so `trace_globs` points at those existing artifacts.
6. Commit `.acp/authority.json`, `.acp/config.json`, and the generated GitHub Actions workflow.
7. Treat new CI authority failures as explicit authority changes that must be reviewed.

The user should **not** need to add `@acp.trace`, wrap `agent.run()`, modify every tool, manually convert calls to `{action, context}`, or hand-author a trace for every CI run.

## Quick start: generate the CI gate

```bash
# From the root of the user's agent repository
acp init . \
  --agent support-agent \
  --ci \
  --test-command "python -m unittest discover -s tests -v"
```

ACP generates:

```text
.acp/authority.json        # reviewed source of truth for agent authority
.acp/config.json           # where ACP looks for existing trace artifacts
.github/workflows/acp.yml  # CI authority gate
```

Then the user reviews `.acp/authority.json` and, if necessary, adjusts `.acp/config.json` to match the trace files already produced by normal tests.

The generated CI performs:

```text
checkout
  → install the user's project + ACP
  → run the user's existing tests unchanged
  → validate .acp/authority.json
  → locate existing JSON trace artifacts
  → normalize tool calls to {action, context}
  → deterministic authority evaluation
  → CI PASS / REQUIRE_APPROVAL / DENY
```

The gate can also be run locally:

```bash
acp check --config .acp/config.json
```

## Tool discovery

`acp init` currently recognizes common Python decorated tools:

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

ACP distinguishes two sources:

1. **Observed traces/events** — JSON artifacts already emitted by normal development, staging, or integration-test agent runs.
2. **Synthetic/replay security traces** — optional fixtures deliberately constructed to exercise dangerous or boundary actions.

The current non-invasive collector searches configurable JSON globs, including `.acp/traces/**/*.json`, `**/*trace*.json`, `**/*tool-call*.json`, and `**/*tool_calls*.json`. It then uses ACP's normalizer to consume common shapes such as generic `{tool, arguments}`, OpenAI-style `function_call`, and nested `tool_calls`, `output`, `messages`, `events`, `items`, and `trace` containers.

Normalized events look like:

```json
{"action": "issue_refund", "context": {"amount": 42}}
```

If no supported tool-call events are found, `acp check` fails explicitly instead of pretending capture succeeded.

## CI behavior

`acp check --config .acp/config.json` exits with:

| Exit code | Meaning |
|---|---|
| 0 | no denied actions and no approval failures |
| 2 | at least one denied action |
| 3 | approval required when `fail_on_approval` is enabled |
| 4 | invalid config / contract / trace input, or required events were not found |

The generated config enables `fail_on_approval` and `require_events` by default.

## Integration hierarchy

ACP uses this priority order:

```text
Level 1 — Zero-code framework adapter
framework-native trace/event/log/test artifact → ACP automatically

Level 2 — Configuration-only adapter (shipped)
user points .acp/config.json at existing trace artifacts → ACP

Level 3 — Explicit instrumentation fallback
only when the framework exposes no usable observable output
```

The newly shipped `acp init --ci` + `acp check` path implements Level 2 without changing application code. Framework-specific Level 1 adapters are still future work and should only be advertised once automated tests prove they work without ACP imports in application source.

## Design principles

ACP is deliberately **not an LLM judge**. The final authority decision is deterministic, inspectable, versionable and testable. Automation reduces setup effort, but generated contracts remain explicit and reviewable.

The risk score is advisory; `ALLOW / REQUIRE_APPROVAL / DENY` is the enforcement primitive.

## Current scope

Shipped today:

- static tool discovery;
- conservative contract drafting;
- common trace normalization;
- deterministic authority evaluation;
- non-invasive trace-artifact collection;
- `acp check` authority gate;
- `acp init --ci` generation of `.acp/config.json` and GitHub Actions CI.

Next: framework-specific Level 1 zero-code adapters that auto-detect existing native tracing/event mechanisms. Runtime enforcement remains a later layer because it sits directly in the production execution path and has different reliability/security requirements.

## Feedback wanted

Would you install ACP if integration meant `acp init --ci` + review the generated authority contract + normal CI, with no changes to your agent business code? Please use GitHub Issue #3 and tell us which agent framework and trace/event artifact your team already produces.
