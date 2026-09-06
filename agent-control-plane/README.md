# Agent Control Plane

**Executable authority contracts for production AI agents with a non-invasive CI integration path.**

ACP turns agent authority boundaries into deterministic, testable policy. The default product direction is **non-invasive**: integrate at the repository/CI boundary instead of requiring ACP decorators, wrappers, or changes to every tool.

## What the user does

For the non-invasive path, the user only needs to:

1. Install ACP in the repo/CI environment.
2. Run `acp init` to discover tools and generate a conservative authority contract draft.
3. Review the generated authority contract and confirm real business rules such as `ALLOW`, `REQUIRE_APPROVAL`, `DENY`, amount thresholds, environments, tenants, and approval groups.
4. Keep running the repository's existing agent/integration tests unchanged.
5. Commit `.acp/authority.json`, `.acp/config.json`, and the generated GitHub Actions workflow.
6. Treat new CI authority failures as explicit authority changes that must be reviewed.

For **OpenAI Agents SDK**, the generated CI now uses ACP's zero-code bootstrap. The application source does not import ACP and does not need to emit a separate trace file itself. ACP registers an additional SDK trace processor at Python startup and records function spans into `.acp/traces/` for the authority gate. The Agents SDK tracing system supports additional processors and records function/tool-call spans by default. 

For other frameworks, the current fallback remains configuration-only: point `.acp/config.json` `trace_globs` at JSON trace/event artifacts already emitted by existing tests.

The user should **not** need to add `@acp.trace`, wrap `agent.run()`, modify every tool, manually convert calls to `{action, context}`, or hand-author a trace for every CI run.

## Quick start

```bash
acp init . \
  --agent support-agent \
  --ci \
  --test-command "python -m unittest discover -s tests -v"
```

ACP generates:

```text
.acp/authority.json        # reviewed source of truth for agent authority
.acp/config.json           # ACP integration/gate configuration
.github/workflows/acp.yml  # CI authority gate
```

The generated CI performs:

```text
checkout
  → install project + ACP
  → run existing tests through ACP zero-code bootstrap
  → OpenAI Agents function spans automatically become trace artifacts
     OR collect existing configured trace artifacts for other frameworks
  → validate .acp/authority.json
  → normalize tool calls to {action, context}
  → deterministic authority evaluation
  → CI PASS / REQUIRE_APPROVAL / DENY
```

The gate can also be run locally after traces exist:

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

1. **Observed traces/events** — for OpenAI Agents SDK, ACP can now auto-capture function spans during normal test execution using the SDK's tracing processor extension point; for other frameworks ACP can collect existing JSON trace artifacts.
2. **Synthetic/replay security traces** — optional fixtures deliberately constructed to exercise dangerous or boundary actions.

The collector searches configurable JSON globs, including `.acp/traces/**/*.json`, `**/*trace*.json`, `**/*tool-call*.json`, and `**/*tool_calls*.json`. It normalizes common shapes such as generic `{tool, arguments}`, OpenAI-style `function_call`, and nested `tool_calls`, `output`, `messages`, `events`, `items`, and `trace` containers.

Normalized events look like:

```json
{"action": "issue_refund", "context": {"amount": 42}}
```

If required tool-call events are not found, `acp check` fails explicitly instead of pretending capture succeeded.

## CI behavior

`acp check --config .acp/config.json` exits with:

| Exit code | Meaning |
|---|---|
| 0 | no denied actions and no approval failures |
| 2 | at least one denied action |
| 3 | approval required when `fail_on_approval` is enabled |
| 4 | invalid config / contract / trace input, or required events were not found |

## Integration hierarchy

```text
Level 1 — Zero-code framework adapter
OpenAI Agents SDK (shipped): SDK tracing processor → ACP automatically

Level 2 — Configuration-only adapter (shipped)
existing framework trace artifacts → .acp/config.json → ACP

Level 3 — Explicit instrumentation fallback
only when the framework exposes no usable observable output
```

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
- `acp init --ci` generation of config and GitHub Actions CI;
- OpenAI Agents SDK zero-code function-span capture during CI test execution.

Next: add more Level 1 framework adapters, starting with MCP/LangGraph where there is a stable non-invasive event boundary. Runtime enforcement remains a later layer because it sits directly in the production execution path and has different reliability/security requirements.

## Feedback wanted

Would you install ACP if integration meant `acp init --ci` + review the generated authority contract + normal CI, with no changes to your agent business code? Please use GitHub Issue #3 and tell us which agent framework your team uses.
