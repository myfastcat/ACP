# Agent Control Plane (ACP)

**ACP turns your existing agent tests into an automatic CI safety gate.** You define the business boundaries once. From then on, every pull request is checked for new authority violations and recurrence of known incidents without maintaining a second ACP-specific test suite.

This README is written from the customer's point of view: **what you run, what ACP creates, what you must provide, and what happens afterward.**

## 1. Install and initialize ACP once

From the root of your agent repository, install ACP and initialize the CI integration using the test command you already trust:

```bash
python -m pip install "git+https://github.com/myfastcat/VCL.git#subdirectory=agent-control-plane"
acp init . --ci --test-command "pytest -q"
```

Replace `pytest -q` with the existing agent/integration-test command for your repository.

### What `acp init` actually produces

`acp init . --ci ...` discovers Python agent tools, drafts a conservative authority contract, and creates:

| Output | Purpose |
|---|---|
| `.acp/authority.json` | draft business authority boundary for the discovered agent actions |
| `.acp/config.json` | ACP CI configuration: authority contract, trace discovery, incident discovery and failure policy |
| `.github/workflows/acp.yml` | GitHub Actions gate that runs your existing tests and then ACP |
| `.acp/incidents/` | an empty directory reserved for incident-regression fixtures you may create later |

Important: **`acp init` does not create an incident fixture and does not invent an incident for you.** Incident regression starts only after you provide a real incident trace and run the separate `acp incident import` command described below.

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

Commit `.acp/authority.json`, `.acp/config.json`, and `.github/workflows/acp.yml` with the rest of your repository. The empty `.acp/incidents/` directory created by `init` does not need to be committed; Git will begin tracking incident files there once you actually create one.

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

## 4. When a real incident happens: you provide the incident, ACP turns it into a CI guard

Incident regression is a separate workflow from initialization.

ACP needs a **real incident trace supplied by you**. Today that trace normally comes from your existing production logging or observability system. Export and redact the relevant trace into a JSON file first, for example:

```text
incidents/raw-duplicate-email.json
```

Suppose that trace shows production sent the same customer email twice. `send_email` is valid in general, so the right rule is not necessarily to ban the tool. Instead, you want this specific bad pattern never to recur.

### Step 4A — import the customer-provided incident trace

Run:

```bash
acp incident import incidents/raw-duplicate-email.json --incident-id INC-DUPLICATE-EMAIL
```

This command reads the trace **you provided** and normalizes it into a durable ACP fixture:

```text
.acp/incidents/INC-DUPLICATE-EMAIL.json
```

It does not come from `acp init`. The fixture is created only by this `acp incident import` command (unless you explicitly choose another output path).

The command prints the number of normalized events, the fixture path, and a suggested next assertion command.

### Step 4B — tell ACP what invariant this incident should enforce

The imported fixture contains the historical incident evidence, but ACP should not guess the business lesson. Add the invariant once:

```bash
acp incident assert .acp/incidents/INC-DUPLICATE-EMAIL.json \
  --max-occurrences send_email \
  --max 1
```

This updates the same fixture with an assertion similar to:

```json
{
  "type": "max_occurrences",
  "action": "send_email",
  "max": 1
}
```

The command reports that the fixture is discoverable by CI. Commit the resulting `.acp/incidents/INC-DUPLICATE-EMAIL.json`.

### What happens afterward

No new CI wiring is required. On every later PR, the normal CI command:

```bash
acp check --config .acp/config.json
```

automatically discovers committed `.acp/incidents/*.json` fixtures and evaluates their assertions against the **current CI run's observed tool calls**.

The historical incident remains evidence. Fixed current behavior passes. If the same bad behavior returns, ACP blocks the PR.

Current integration boundary: ACP does not yet pull production incidents directly from observability platforms. **Preparing/exporting the source incident trace is currently the customer's responsibility.**

## 5. Command → input → output summary

| Customer action | Required input | ACP output / effect |
|---|---|---|
| `acp init . --ci --test-command "..."` | repository + existing test command | `.acp/authority.json`, `.acp/config.json`, `.github/workflows/acp.yml`, empty `.acp/incidents/` directory |
| `acp validate .acp/authority.json` | reviewed authority contract | prints `VALID` or exits with invalid-input status |
| normal PR / generated CI | existing agent tests + ACP config | current trace evidence + `acp check` PASS/BLOCK result |
| `acp incident import <customer-trace> --incident-id <id>` | **customer-provided real incident JSON trace** | `.acp/incidents/<id>.json` normalized incident fixture |
| `acp incident assert .acp/incidents/<id>.json ...` | imported fixture + customer-chosen invariant | updates that fixture with the durable regression assertion |
| later normal CI | current agent-test behavior + committed incident fixtures | automatically checks authority + all incident regressions |

## 6. Files you maintain after setup

| File | Where it comes from | When you touch it |
|---|---|---|
| `.acp/authority.json` | generated by `acp init` | when your business authority boundary changes |
| `.acp/config.json` | generated by `acp init --ci` | when trace/incident discovery or failure policy needs to change |
| `.github/workflows/acp.yml` | generated by `acp init --ci` | normally generated once; edit only if your CI environment needs customization |
| `.acp/incidents/<id>.json` | generated by `acp incident import` from a customer-provided incident trace, then updated by `acp incident assert` | when a real incident teaches a new durable regression invariant |

Your existing application tests remain your tests. ACP adds a separate CI safety judgment over the behavior those tests exercise.

## 7. Where ACP fits

ACP strengthens systems you already have rather than replacing them:

- **Existing tests:** reused to exercise agent behavior.
- **Existing CI:** ACP becomes a gate in the same pull-request workflow.
- **Existing observability:** you currently export incident traces from it; ACP imports those traces into durable CI regression fixtures.
- **Existing runtime controls:** ACP complements them; it is not a replacement for runtime authorization or production observability.

## Demo

The customer-shaped demo shows the exact files, CI commands and concrete pass/block cases used in practice. See the matching `agent-control-plane` demo in `myfastcat/VCL-demo` when you have access.

## Feedback

Share a redacted authority boundary or incident trace/invariant in [Issue #3](https://github.com/myfastcat/VCL/issues/3).
