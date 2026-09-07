# Agent Control Plane (ACP)

**Catch AI-agent authority regressions automatically in CI.** ACP discovers tools, captures supported agent traces, and checks them against your `ALLOW / REQUIRE_APPROVAL / DENY` policy.

## Quick start

Python 3.10+ required. From your agent repository:

```bash
python -m pip install "git+https://github.com/myfastcat/VCL.git#subdirectory=agent-control-plane"
acp init . --ci --test-command "pytest -q"
```

Replace `pytest -q` only if your project uses a different test command that exercises the agent.

`acp init` is ACP-specific:
- `.`: scan the current repository.
- `--ci`: generate ACP config + GitHub Actions gate.
- `--test-command`: command ACP should run in CI to exercise your agent.

It generates:

```text
.acp/authority.json
.acp/config.json
.github/workflows/acp.yml
```

## One decision you must make

Review `.acp/authority.json` and classify what your agent may do:

```json
{
  "agent": "customer-support-agent",
  "default": "REQUIRE_APPROVAL",
  "rules": [
    {"id": "read", "action": "read_*", "decision": "ALLOW", "reason": "read only"},
    {"id": "write", "action": "send_*", "decision": "REQUIRE_APPROVAL", "reason": "external side effect"},
    {"id": "delete", "action": "delete_*", "decision": "DENY", "reason": "destructive"}
  ]
}
```

Use your real tool/action names. `default` applies when no rule matches; keeping it `REQUIRE_APPROVAL` is the conservative starting point.

Then:

```bash
acp validate .acp/authority.json
acp check
```

## What happens automatically in CI

Push the generated files. The workflow automatically:

```text
run your tests
→ capture supported tool calls
→ find traces
→ validate .acp/authority.json
→ evaluate every observed action
→ pass/fail CI
```

For **OpenAI Agents SDK**, ACP automatically captures function/tool spans during the generated CI run—no ACP decorator or `agent.run()` wrapper required.

For other frameworks, point `.acp/config.json` `trace_globs` at JSON traces your tests already produce. ACP then discovers and normalizes them automatically.

Default trace search includes:

```text
.acp/traces/**/*.json
**/*trace*.json
**/*tool-call*.json
**/*tool_calls*.json
```

No tool-call events = failure by default, not a false pass.

## Exit codes

| Code | Meaning |
|---|---|
| `0` | pass |
| `2` | `DENY` action observed |
| `3` | approval-required action observed and configured to fail |
| `4` | invalid config/input or required trace missing |

## Advanced commands

```bash
acp normalize raw-trace.json --out acp-trace.json
acp eval .acp/authority.json acp-trace.json --fail-on-approval
```

`normalize` converts a raw/framework trace into ACP events. `eval` checks a specific trace against a contract. `--fail-on-approval` makes `REQUIRE_APPROVAL` return exit `3`.

## Scope

ACP is a deterministic CI authority gate over observed actions. It does not invent your business authority policy, provide a human approval UI, or replace runtime authorization.

## Feedback

Share a redacted real authority boundary in [Issue #3](https://github.com/myfastcat/VCL/issues/3):

```text
AUTONOMOUS: search_customer, read_ticket
APPROVAL: update_customer, send_email
FORBIDDEN: delete_customer, transfer_money
FRAMEWORK: OpenAI Agents SDK / MCP / LangGraph / other
```
