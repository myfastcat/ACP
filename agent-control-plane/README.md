# Agent Control Plane (ACP)

**Keep AI agents inside their authority boundary—and turn incidents into deterministic CI regressions.** ACP combines authority contracts, trace capture/discovery, policy gates, incident replay and evidence in one product.

## Quick start

Python 3.10+ required. From your agent repository:

```bash
python -m pip install "git+https://github.com/myfastcat/VCL.git#subdirectory=agent-control-plane"
acp init . --ci --test-command "pytest -q"
```

Replace `pytest -q` only if your project uses a different test command that exercises the agent. `--ci` generates ACP config, `.acp/incidents/`, and the GitHub Actions gate.

Review the generated `.acp/authority.json`, then:

```bash
acp validate .acp/authority.json
acp check
```

ACP's generated CI runs your tests, captures supported tool calls, discovers traces, evaluates the authority contract, auto-discovers committed incident regressions, and fails CI if either an authority rule or an incident invariant fails. OpenAI Agents SDK tool spans are captured automatically during the generated CI run.

## Turn an incident into a permanent CI regression

A production incident starts from a redacted tool-call trace exported from your existing logs or observability system. Import it:

```bash
acp incident import raw-trace.json --incident-id INC-42
```

ACP stores it at `.acp/incidents/INC-42.json`, where later CI runs discover it automatically. You make only the business decision about what must never happen again; ACP updates the fixture for you:

```bash
acp incident assert .acp/incidents/INC-42.json --must-not-occur delete_customer
```

Other supported decisions:

```bash
acp incident assert .acp/incidents/INC-42.json --must-occur approval_check
acp incident assert .acp/incidents/INC-42.json --max-occurrences send_email --max 1
```

Commit `.acp/incidents/INC-42.json`. From then on, the normal generated `acp check` CI gate replays every fixture matching `.acp/incidents/*.json`; any failed incident invariant exits `2` and blocks CI. You do not add a separate workflow step for each incident.

To inspect one incident locally or create an evidence pack:

```bash
acp incident replay .acp/incidents/INC-42.json --evidence incident.evidence.json
```

## Authority decisions

ACP contracts classify actions as `ALLOW`, `REQUIRE_APPROVAL`, or `DENY`. Keep the default at `REQUIRE_APPROVAL` when you have not explicitly decided an action's authority.

## Exit codes

| Code | Meaning |
|---|---|
| `0` | authority + incident regression gate passed |
| `2` | denied authority action or incident regression failed |
| `3` | approval-required action configured to fail CI |
| `4` | invalid/missing input, config, contract or required trace |

## Trace support

Default discovery includes `.acp/traces/**/*.json`, `**/*trace*.json`, `**/*tool-call*.json`, and `**/*tool_calls*.json`. No tool-call events fails by default rather than silently passing.

For frameworks not automatically captured, point `.acp/config.json` `trace_globs` at JSON traces your tests already emit.

## What ACP automates vs. what you decide

ACP automates trace normalization, fixture creation, fixture storage convention, CI discovery, replay, exit codes and evidence. You decide the actual authority boundary and incident invariant because those are business/security decisions. For production incidents, ACP currently expects a trace exported from your existing logging or observability system; direct production-observability connectors are not yet built in.

## Scope

ACP is a deterministic control/regression layer over observed agent actions. It does not invent your business authority policy, prove a source trace is complete/authentic, provide a human approval UI, or replace runtime authorization/observability.

## Feedback

Share a redacted authority boundary or incident trace/invariant in [Issue #3](https://github.com/myfastcat/VCL/issues/3).
