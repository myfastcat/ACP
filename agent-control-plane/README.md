# Agent Control Plane (ACP)

**Keep AI agents inside their authority boundary—and turn incidents into deterministic CI regressions.** ACP combines authority contracts, trace capture/discovery, policy gates, incident replay and evidence in one product.

## Quick start

Python 3.10+ required. From your agent repository:

```bash
python -m pip install "git+https://github.com/myfastcat/VCL.git#subdirectory=agent-control-plane"
acp init . --ci --test-command "pytest -q"
```

Replace `pytest -q` only if your project uses a different test command that exercises the agent. `--ci` generates ACP config and the GitHub Actions gate.

Review the generated `.acp/authority.json`, then:

```bash
acp validate .acp/authority.json
acp check
```

ACP's generated CI runs your tests, captures supported tool calls, discovers traces, validates the authority contract, evaluates observed actions, and passes/fails CI. OpenAI Agents SDK tool spans are captured automatically during the generated CI run.

## Turn an incident into a regression

Given a redacted incident trace:

```bash
acp incident import raw-trace.json --incident-id INC-42
```

This writes `incident.fixture.json`. Add the invariant that must hold from now on:

```json
"assertions": [
  {"type": "must_not_occur", "action": "delete_customer"}
]
```

Then replay it:

```bash
acp incident replay incident.fixture.json --evidence incident.evidence.json
```

Supported assertions are `must_not_occur`, `must_occur`, and `max_occurrences`. The evidence pack includes a deterministic SHA-256 fixture fingerprint and can be retained with CI artifacts.

## Authority decisions

ACP contracts classify actions as `ALLOW`, `REQUIRE_APPROVAL`, or `DENY`. Keep the default at `REQUIRE_APPROVAL` when you have not explicitly decided an action's authority.

## Exit codes

| Code | Meaning |
|---|---|
| `0` | gate/replay passed |
| `2` | denied authority action or incident regression failed |
| `3` | approval-required action configured to fail CI |
| `4` | invalid/missing input, config, contract or required trace |

## Trace support

Default discovery includes `.acp/traces/**/*.json`, `**/*trace*.json`, `**/*tool-call*.json`, and `**/*tool_calls*.json`. No tool-call events fails by default rather than silently passing.

For frameworks not automatically captured, point `.acp/config.json` `trace_globs` at JSON traces your tests already emit.

## Scope

ACP is a deterministic control/regression layer over observed agent actions. It does not invent your business authority policy, prove a source trace is complete/authentic, provide a human approval UI, or replace runtime authorization/observability.

## Feedback

Share a redacted authority boundary or incident trace/invariant in [Issue #3](https://github.com/myfastcat/VCL/issues/3).
