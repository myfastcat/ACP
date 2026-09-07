# Agent Control Plane (ACP)

**ACP is a CI safety gate for AI agents.** You tell ACP what your agent is allowed to do and which past incident must never recur. On every pull request, CI runs the agent tests, ACP observes the tool calls, and the build is blocked when the agent crosses its authority boundary or repeats a known incident.

## What a customer does

### 1. Add ACP to CI once

From the agent repository, run the one-time setup:

```bash
python -m pip install "git+https://github.com/myfastcat/VCL.git#subdirectory=agent-control-plane"
acp init . --ci --test-command "pytest -q"
```

Use your real test command if it is not `pytest -q`. Commit the generated `.acp/` configuration and GitHub Actions workflow.

### 2. Define the business authority boundary

Review `.acp/authority.json` and decide which agent actions are:

- `ALLOW` — the agent may do it automatically.
- `REQUIRE_APPROVAL` — a human/business approval is required.
- `DENY` — the agent must not do it.

This is the main customer decision. ACP should automate the technical enforcement; it should not invent your business permissions.

### 3. Let CI enforce it

After setup, developers keep their normal workflow: change code and open/push a pull request. They do **not** need to run ACP commands for every change.

The generated CI gate automatically:

1. runs the customer's existing agent tests;
2. captures supported agent tool calls (OpenAI Agents SDK spans are captured automatically);
3. discovers the resulting traces;
4. evaluates every observed action against `.acp/authority.json`;
5. loads committed incident regression rules from `.acp/incidents/*.json`;
6. evaluates those incident invariants against the **current CI run's** observed tool calls;
7. fails the build when an action is denied, requires approval under a fail-on-approval policy, or a historical incident behavior returns.

So the normal customer experience is:

```text
Developer opens PR
        ↓
Existing agent tests run in CI
        ↓
ACP automatically observes tool calls
        ↓
Authority boundary + known incident regressions are checked
        ↓
PASS → PR can continue
FAIL → CI shows the safety/regression failure
```

## What happens after a real incident

Suppose production accidentally sends the same customer email twice. The customer exports/redacts that incident trace from its existing logging or observability system and records the business invariant once, for example: `send_email` may occur at most once in this scenario.

That incident rule is committed under `.acp/incidents/`. From then on there is **no new CI wiring and no per-PR incident command**. Every normal CI run automatically checks current agent behavior against all committed incident invariants. If the duplicate-email behavior returns, ACP fails CI even though `send_email` itself is normally an allowed action.

ACP currently automates fixture storage/discovery and CI regression enforcement. Direct connectors that automatically ingest production incidents from observability platforms are not yet built, so exporting the source production trace is still an integration boundary.

## What ACP catches

**Authority violation:** `delete_customer` is `DENY`; a new code change causes the agent to call it. Ordinary application tests may still pass, but ACP blocks the CI run.

**Incident regression:** `send_email` is generally `ALLOW`; a historical incident showed the agent sending it twice. The committed incident invariant says maximum one. A later PR reintroduces the duplicate behavior, so ACP blocks CI even though the action itself is authorized.

## CI result

| Result | Meaning |
|---|---|
| PASS | observed agent actions satisfy the authority contract and all committed incident invariants |
| exit `2` | denied authority action or incident regression |
| exit `3` | approval-required action configured to fail CI |
| exit `4` | invalid/missing config, contract, or required trace |

No tool-call events fails by default rather than silently passing.

## Trace support

Default discovery includes `.acp/traces/**/*.json`, `**/*trace*.json`, `**/*tool-call*.json`, and `**/*tool_calls*.json`. For frameworks not automatically captured, configure `.acp/config.json` `trace_globs` to point at JSON traces the customer's tests already emit.

## Scope

ACP is a deterministic CI control/regression layer over observed agent actions. It does not invent the customer's authority policy, prove that a source trace is complete/authentic, provide a human approval UI, or replace runtime authorization/production observability.

## Feedback

Share a redacted authority boundary or incident trace/invariant in [Issue #3](https://github.com/myfastcat/VCL/issues/3).
