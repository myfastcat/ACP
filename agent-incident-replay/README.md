# Agent Incident Replay (AIR)

**Turn an AI-agent incident trace into a deterministic regression test you can keep in CI.**

## Quick start

Python 3.10+ required. Export a redacted JSON incident/tool-call trace as `raw-trace.json`, then:

```bash
python -m pip install "git+https://github.com/myfastcat/VCL.git#subdirectory=agent-incident-replay"
air normalize raw-trace.json --incident-id INC-42
air replay fixture.json --evidence evidence.json
```

AIR-specific parameters:
- `raw-trace.json`: your exported incident trace.
- `--incident-id`: optional incident/ticket identifier; default is `incident`.
- `--evidence`: write a portable evidence pack to this path.

`normalize` writes `fixture.json` by default.

## One decision you must make

Open `fixture.json` and add the invariant that should prevent this class of incident from recurring:

```json
"assertions": [
  {"type": "must_not_occur", "action": "delete_customer"}
]
```

Use the real action from your incident.

Supported assertions:

| Assertion | Meaning |
|---|---|
| `must_not_occur` | action must never appear |
| `must_occur` | action must appear |
| `max_occurrences` | action may appear at most `max` times |

Example:

```json
{"type":"max_occurrences","action":"send_email","max":1}
```

## Replay

```bash
air replay fixture.json --evidence evidence.json
```

AIR evaluates the assertions and writes a SHA-256-addressed evidence pack.

| Exit | Meaning |
|---|---|
| `0` | all assertions pass |
| `2` | regression assertion failed |
| `4` | invalid/missing input |

Add `--json` when you want the full machine-readable result:

```bash
air replay fixture.json --json --evidence evidence.json
```

## CI

Use the same command as a CI step:

```bash
air replay tests/incidents/INC-42.fixture.json --evidence artifacts/INC-42.evidence.json
```

Exit `2` fails a normal CI shell step automatically.

AIR currently does **not** run your agent or export the incident trace for you. Your remaining manual job is: export/redact the real trace and decide the regression invariant. Automating more trace acquisition is a product-development priority rather than something users should solve with extra configuration.

## Accepted trace shape

AIR accepts a JSON list or an object containing `events`, `trace`, or `tool_calls`. Events need an action/tool/name and may contain context/arguments/args.

```json
{
  "tool_calls": [
    {"name": "lookup_customer", "arguments": {"customer_id": "REDACTED"}},
    {"name": "delete_customer", "arguments": {"customer_id": "REDACTED"}}
  ]
}
```

Do not commit secrets or unredacted customer data.

## Scope

AIR proves explicit assertions over recorded actions. It does not prove the source trace is complete/authentic, reconstruct incident root cause, or replace runtime authorization/observability.

## Feedback

[Open an AIR feedback issue](https://github.com/myfastcat/VCL/issues/new?title=Agent%20Incident%20Replay%20feedback) with a redacted trace shape and the invariant you wanted to test.
