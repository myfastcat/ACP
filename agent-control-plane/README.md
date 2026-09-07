# Agent Control Plane (ACP)

**ACP turns your existing agent tests into an automatic CI safety gate.** You define the business boundaries once. From then on, every pull request is checked for both new authority violations and recurrence of known incidents—without maintaining a second ACP-specific test suite.

## The customer journey

ACP is designed around four moments in the life of an agent system: deciding what the agent may do, protecting every code change, learning from incidents, and understanding why something was blocked.

### 1. Set the boundary — decide what the agent may do

You already know the business rules better than ACP does. ACP's job is to make those rules executable.

One-time setup from the agent repository:

```bash
python -m pip install "git+https://github.com/myfastcat/VCL.git#subdirectory=agent-control-plane"
acp init . --ci --test-command "pytest -q"
```

Use the test command that already exercises your agent. ACP generates the CI wiring and a draft `.acp/authority.json` for review.

You make the business decision once:

- `ALLOW` — the agent may perform the action automatically.
- `REQUIRE_APPROVAL` — the action needs human/business approval.
- `DENY` — the agent must not perform the action.

You do **not** write a parallel ACP test suite. ACP reuses the behavior already exercised by your existing agent/integration tests.

### 2. Protect every change — CI does the repetitive work

After setup, developers keep the workflow they already have: change code, push, open a PR.

The generated CI gate automatically:

```text
Existing agent tests
        ↓
ACP observes/discovers tool calls
        ↓
Authority rules are evaluated
        +
Known incident regressions are evaluated
        ↓
PASS → normal CI continues
BLOCK → unsafe/regressed behavior is shown in CI
```

ACP captures supported OpenAI Agents SDK tool spans automatically. For other frameworks, it can consume JSON trace artifacts your tests already emit.

A missing trace does not silently pass. If ACP cannot observe the agent behavior that is supposed to be protected, the gate fails rather than claiming safety without evidence.

### 3. Learn from incidents — make yesterday's failure protect tomorrow's PR

Not every bad behavior is simply "forbidden." An action can be valid in general but wrong in a specific repeated pattern.

Example: `send_email` is allowed, but production once sent the same retention email twice. That incident teaches a more specific invariant: in this regression scenario, `send_email` may occur at most once.

The customer exports/redacts the relevant incident trace from existing logging or observability and records that invariant once. ACP stores the durable incident rule under `.acp/incidents/`.

From then on, there is no new CI wiring and no per-PR replay step. Every normal CI run automatically evaluates all committed incident invariants against the **current run's observed tool calls**.

So fixed code passes. If the historical behavior returns in a later PR, ACP blocks it even though the underlying action may still be authorized.

Current integration boundary: ACP does not yet pull production incidents directly from observability platforms; the source incident trace still comes from the customer's existing logging/observability system.

### 4. Understand and prove — know why the build was blocked

A safety gate is only useful if the team can act on it.

When ACP blocks CI, the result distinguishes the important failure classes:

| CI result | What it means |
|---|---|
| PASS | current behavior satisfies the authority contract and committed incident invariants |
| exit `2` | a denied action occurred or a known incident behavior returned |
| exit `3` | an approval-required action is configured to block CI |
| exit `4` | ACP could not validly evaluate the run because required config/contract/trace evidence is missing or invalid |

ACP reports the observed actions and matched authority rules, and incident checks retain the historical fixture/evidence needed to understand what regression rule was applied.

## What ACP fits into instead of replacing

ACP is meant to strengthen the systems you already have:

- **Existing tests:** reused as the behavior exercise; no separate ACP test suite is required.
- **Existing CI:** ACP becomes another gate in the same pull-request workflow.
- **Existing observability:** production incident traces can be exported from it and converted into durable regression knowledge.
- **Existing runtime controls:** ACP complements them; it is not a replacement for runtime authorization or production observability.

## Trace support

Default discovery includes `.acp/traces/**/*.json`, `**/*trace*.json`, `**/*tool-call*.json`, and `**/*tool_calls*.json`. For frameworks not automatically captured, configure `.acp/config.json` `trace_globs` to point at JSON traces the existing tests already emit.

## Scope

ACP is a deterministic CI control/regression layer over observed agent actions. It does not invent the customer's authority policy, prove that a source trace is complete/authentic, provide a human approval UI, or replace runtime authorization/production observability.

## Feedback

Share a redacted authority boundary or incident trace/invariant in [Issue #3](https://github.com/myfastcat/VCL/issues/3).
