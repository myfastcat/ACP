# Agent Control Plane (ACP)

**ACP turns your existing agent tests into an automatic CI safety gate.** You define the business boundaries once. From then on, every pull request is checked for new authority violations and recurrence of known incidents without maintaining a second ACP-specific test suite.

This README is written from the customer's point of view: **what you run, what ACP creates, and what happens afterward.**

## 1. Install and initialize ACP once

From the root of your agent repository, install ACP and initialize the CI integration using the test command you already trust:

```bash
python -m pip install "git+https://github.com/myfastcat/VCL.git#subdirectory=agent-control-plane"
acp init . --ci --test-command "pytest -q"
```

Replace `pytest -q` with the existing agent/integration-test command for your repository.

### What this command produces

`acp init . --ci ...` discovers Python agent tools, drafts a conservative authority contract, and creates:

| Output | Purpose |
|---|---|
| `.acp/authority.json` | draft business authority boundary for the discovered agent actions |
| `.acp/config.json` | ACP CI configuration: authority contract, trace discovery, incident discovery and failure policy |
| `.github/workflows/acp.yml` | GitHub Actions gate that runs your existing tests and then ACP |
| `.acp/incidents/` | durable home for incident-regression rules learned later |

ACP also prints a one-line initialization result similar to:

```text
discovered=<N> frameworks=<...> review_required=true generated=.acp/authority.json,.acp/config.json,.github/workflows/acp.yml,.acp/incidents/
```

`review_required=true` is intentional: ACP can discover technical actions, but it should not invent your business permissions.

## 2. Review the authority boundary once

Open `.acp/authority.json` and decide how each action should be treated:

- `ALLOW` — the agent may perform the action automatically.
- `REQUIRE_APPROVAL` — the action requires human/business approval.
- `DENY` — the agent must not perform the action.

You can validate the file before committing it:

```bash
acp validate .acp/authority.json
```

Expected output:

```text
VALID
```

At this point, commit `.acp/authority.json`, `.acp/config.json`, `.github/workflows/acp.yml`, and `.acp/incidents/` with the rest of your repository.

You do **not** create a second ACP-specific test suite. ACP reuses the behavior already exercised by your existing agent/integration tests.

## 3. What CI runs on every PR

After the one-time setup, developers keep their normal workflow: change code, push, open a PR. They do not run ACP manually for each change.

The generated `.github/workflows/acp.yml` performs two ACP-related steps.

First, it runs your existing test command through ACP's zero-code bootstrap:

```bash
python -m agent_control_plane.zero_code_runner -- sh -lc 'pytest -q'
```

For supported OpenAI Agents SDK flows, ACP captures function/tool spans automatically. For other frameworks, `.acp/config.json` can point `trace_globs` at JSON trace artifacts your existing tests already produce.

The observable behavior is stored/discovered as trace input, normally under paths such as:

```text
.acp/traces/**/*.json
```

Second, CI runs the actual safety gate:

```bash
acp check --config .acp/config.json
```

### What `acp check` produces

ACP prints a summary of the current CI run, followed by the matched authority decisions and any incident-regression results. The first line has this shape:

```text
events=<N> allow=<N> approval=<N> deny=<N> incident_regressions=<N> incident_failures=<N> avg_risk=<...> ci_pass=<true|false>
```

It then reports the trace sources it consumed, each observed action and matched rule, and each committed incident rule it evaluated.

The process exit code becomes the CI result:

| Result | Meaning |
|---|---|
| exit `0` | current behavior satisfies the authority contract and all committed incident rules |
| exit `2` | a denied action occurred or a known incident behavior returned |
| exit `3` | an approval-required action occurred while `fail_on_approval` is enabled |
| exit `4` | ACP could not validly evaluate the run because required config, contract, trace, or input evidence is missing/invalid |

A missing trace does not silently pass when `require_events` is enabled. If ACP cannot observe the behavior it is supposed to protect, CI fails instead of claiming safety without evidence.

## 4. Turn a real incident into a permanent CI guard

Suppose production sent the same customer email twice. `send_email` is valid in general, so the right rule is not necessarily to ban the tool. Instead, you want this specific bad pattern never to recur.

Export/redact the incident trace from your existing logging or observability system, then import it once:

```bash
acp incident import incidents/raw-duplicate-email.json --incident-id INC-DUPLICATE-EMAIL
```

### What this command produces

ACP normalizes the incident into:

```text
.acp/incidents/INC-DUPLICATE-EMAIL.json
```

The command prints the number of normalized events, the fixture path, and the suggested next assertion command.

Now add the business invariant once:

```bash
acp incident assert .acp/incidents/INC-DUPLICATE-EMAIL.json \
  --max-occurrences send_email \
  --max 1
```

### What this command changes

It updates the same incident fixture with a durable assertion similar to:

```json
{
  "type": "max_occurrences",
  "action": "send_email",
  "max": 1
}
```

The command reports that the fixture is now discoverable by CI. Commit the updated `.acp/incidents/INC-DUPLICATE-EMAIL.json`.

From then on, no new CI wiring is required. Every normal `acp check` automatically discovers committed incident fixtures and evaluates their assertions against the **current CI run's observed tool calls**. Fixed behavior passes; recurrence blocks the PR.

Current integration boundary: ACP does not yet pull production incidents directly from observability platforms. The source incident trace still comes from your existing logging/observability system.

## 5. Files you maintain after setup

The normal customer-owned ACP surface is intentionally small:

| File | When you touch it |
|---|---|
| `.acp/authority.json` | when your business authority boundary changes |
| `.acp/config.json` | when trace/incident discovery or failure policy needs to change |
| `.github/workflows/acp.yml` | normally generated once; edit only if your CI environment needs customization |
| `.acp/incidents/*.json` | when a real incident teaches a new durable regression invariant |

Your existing application tests remain your tests. ACP adds a separate CI safety judgment over the behavior those tests exercise.

## 6. Where ACP fits

ACP strengthens systems you already have rather than replacing them:

- **Existing tests:** reused to exercise agent behavior.
- **Existing CI:** ACP becomes a gate in the same pull-request workflow.
- **Existing observability:** incident traces can be exported from it and converted into durable CI knowledge.
- **Existing runtime controls:** ACP complements them; it is not a replacement for runtime authorization or production observability.

## Demo

The customer-shaped demo shows the exact files, CI commands and concrete pass/block cases used in practice. See the matching `agent-control-plane` demo in `myfastcat/VCL-demo` when you have access.

## Feedback

Share a redacted authority boundary or incident trace/invariant in [Issue #3](https://github.com/myfastcat/VCL/issues/3).
