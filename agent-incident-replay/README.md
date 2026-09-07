# Agent Incident Replay (AIR)

Turn an AI-agent incident/tool-call trace into a portable deterministic regression fixture and evidence pack you can keep in CI.

## What AIR automates vs. what you must do

AIR automates trace normalization, deterministic assertion evaluation, CI-friendly exit codes, and evidence-pack generation. **You must manually export a real incident trace and decide the invariant that represents “this class of failure must not recur.”** AIR cannot infer the correct business/safety invariant from an incident by itself.

## Complete workflow

### 1. Prerequisites — manual

You need Python 3.10+, Git, and a JSON incident/tool-call trace exported from the agent system you operate. The trace must contain the actions/tool calls relevant to the incident. Redact secrets and personal/customer data before storing the trace in a repository.

### 2. Install AIR — manual

From any directory:

```bash
python -m pip install "git+https://github.com/myfastcat/VCL.git#subdirectory=agent-incident-replay"
```

`python -m pip install` installs into the environment for that Python interpreter. `git+https://...` installs from GitHub. `#subdirectory=agent-incident-replay` selects AIR inside the VCL repository.

Verify:

```bash
air --help
```

Expected: help containing `normalize` and `replay`. If `air` is not found, activate the environment where you installed it.

### 3. Export the incident trace — **required manual step**

Export a JSON trace from your existing agent/observability system and save it, for example, as `raw-trace.json`. AIR v0.1 accepts a JSON list or an object containing `events`, `trace`, or `tool_calls`. Each event needs an action/tool/name and may include context/arguments/args.

Example input:

```json
{
  "tool_calls": [
    {"name": "lookup_customer", "arguments": {"customer_id": "REDACTED"}},
    {"name": "delete_customer", "arguments": {"customer_id": "REDACTED"}}
  ]
}
```

AIR does not prove your exported trace is complete or authentic. If the dangerous action is absent because your tracing omitted it, AIR cannot reconstruct it.

### 4. Normalize the incident — manual command, automatic conversion

Run from the directory containing the trace:

```bash
air normalize raw-trace.json --incident-id INC-42 --out fixture.json
```

Arguments:

- `raw-trace.json` — required source trace path.
- `--incident-id INC-42` — optional human-readable incident identifier; default is `incident`. Replace `INC-42` with your ticket/incident ID.
- `--out fixture.json` — output fixture path; default is `fixture.json`.

Expected output resembles:

```text
events=2 fixture=fixture.json
```

AIR creates a normalized `air/v1` fixture containing stable `{seq, action, context}` events and an initially empty `assertions` list. Malformed/unsupported input exits `4`; inspect the reported event and fix/export the trace shape.

### 5. Define the regression invariant — **required manual decision**

Open `fixture.json` and edit its `assertions` array. This is the most important human step: state what must be true so the same class of failure is caught.

Example:

```json
{
  "schema": "air/v1",
  "incident_id": "INC-42",
  "events": [
    {"seq": 0, "action": "lookup_customer", "context": {"customer_id": "REDACTED"}},
    {"seq": 1, "action": "delete_customer", "context": {"customer_id": "REDACTED"}}
  ],
  "assertions": [
    {"type": "must_not_occur", "action": "delete_customer"}
  ]
}
```

Supported assertions:

- `must_not_occur` — fails when the named action appears. Use for actions that must not recur in this replay.
- `must_occur` — fails when the named action is absent. Use when a required recovery/control action must happen.
- `max_occurrences` — fails when an action appears more than `max` times, e.g. `{"type":"max_occurrences","action":"send_email","max":1}`.

Choose the invariant from the actual incident/control requirement; do not simply copy `delete_customer` from the example.

### 6. Replay locally — manual

```bash
air replay fixture.json --json
```

`fixture.json` is the normalized fixture you edited. `--json` is optional and prints the full machine-readable result. Without it AIR prints a compact summary.

Exit codes:

| Exit | Meaning | What you do |
|---|---|---|
| `0` | All assertions pass | The fixture currently satisfies the invariant. |
| `2` | One or more assertions fail | The regression is present in this fixture; inspect `failures`. |
| `4` | Invalid/missing JSON/input | Fix the fixture/path/input before treating the run as evidence. |

With the example incident above, `must_not_occur: delete_customer` intentionally returns `2` because the recorded incident contains that action. After the agent/policy change, generate/use the post-fix replay trace/fixture so the assertion can demonstrate the corrected behavior.

### 7. Generate a portable evidence pack — manual command, automatic output

```bash
air replay fixture.json --json --evidence evidence.json
```

`--evidence evidence.json` writes a portable evidence file containing the fixture, replay result, replay command, and deterministic SHA-256 fixture fingerprint. Choose another path if your CI stores artifacts elsewhere.

Expected: `evidence.json` exists and the result contains `passed`, `failures`, `event_count`, and `fixture_sha256`.

### 8. Put the regression in CI — manual repository integration

Commit a **redacted** fixture with your tests, then invoke AIR from your CI job after your system generates/updates the trace or fixture that represents the behavior under test. A minimal shell gate is:

```bash
air replay tests/incidents/INC-42.fixture.json --evidence artifacts/INC-42.evidence.json
```

Because AIR returns exit `2` on assertion failure, a normal CI shell step fails automatically. The exact workflow for regenerating a fixture depends on your agent/test harness; AIR v0.1 does not automatically execute your agent or export its trace.

Before committing:

```bash
git add tests/incidents/INC-42.fixture.json
git commit -m "add INC-42 agent incident regression"
git push
```

Do not commit secrets or unredacted customer data. If evidence artifacts contain sensitive context, store them in an appropriate protected CI artifact system instead of Git.

### 9. Interpret failures

A failing AIR replay means the recorded fixture violates one of your explicit assertions. It does **not** by itself prove why the agent behaved that way, that the original trace is forensically authentic, or that production runtime authorization is safe. Use the `failures` list and incident context to fix the agent/policy, then replay the corrected behavior.

### 10. Ongoing use

For each meaningful incident: export/redact trace → normalize → define invariant → reproduce failure → fix agent/policy → capture corrected behavior → replay until passing → keep the fixture/evidence in CI. Update assertions only when the intended control requirement actually changes; do not weaken an assertion merely to make CI green.

## Scope and known limitations

In scope: post-incident normalization, deterministic regression assertions, CI exit semantics, portable evidence. Non-goals: runtime interception/authorization, automatic incident root-cause analysis, forensic truth reconstruction, or replacing observability platforms. Unknown assertion types should not be relied on in v0.1.

## Feedback

Real incident shapes are the most useful feedback. Open an issue and provide, when possible, a redacted trace shape plus the invariant you wanted to test:

https://github.com/myfastcat/VCL/issues/new?title=Agent%20Incident%20Replay%20feedback
