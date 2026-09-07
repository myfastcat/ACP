# Agent Incident Replay

Turn an AI-agent incident trace into a portable regression fixture and evidence pack you can keep in CI.

## Why
After an agent does something surprising, screenshots and logs explain the past but do not prove the same class of failure will stay fixed. AIR converts common tool-call traces to a stable `{action, context}` sequence, lets you add explicit incident assertions, replays them deterministically, and emits a hash-addressed evidence pack.

## Quick start
```bash
pip install -e ./agent-incident-replay
air normalize raw-trace.json --incident-id INC-42 --out fixture.json
# edit fixture.json assertions, e.g.
# {"type":"must_not_occur","action":"delete_database"}
air replay fixture.json --evidence evidence.json
```

Supported assertions: `must_not_occur`, `must_occur`, `max_occurrences`. A failing assertion exits 2, so the replay can gate CI.

## End-to-end job
1. Export an incident/tool-call trace from the system you already operate.
2. Normalize it without instrumenting the agent runtime.
3. Add the control invariant that should prevent recurrence.
4. Replay in CI after product/policy changes.
5. Store/share `evidence.json`, which contains the fixture, result, replay command, and deterministic SHA-256 fingerprint.

## Scope
In scope: post-incident normalization, deterministic regression assertions, CI exit semantics, portable evidence. Non-goals: runtime interception, authorization, forensic truth reconstruction, or replacing observability platforms.

## Failure modes
Malformed traces fail closed with exit 4. Unknown assertion types are ignored in v0.1 and should not be relied upon. AIR proves assertions over recorded action names; it does not prove the original trace is complete or authentic.

## Feedback
Real incident shapes are the most useful feedback. Open an issue and, if possible, provide a redacted trace shape plus the invariant you wanted to test:
https://github.com/myfastcat/VCL/issues/new?title=Agent%20Incident%20Replay%20feedback

## Acceptance / release
The MVP is accepted when normalization handles common list/tool_calls shapes, violations produce non-zero exit, evidence contains a fixture fingerprint, automated tests cover pass/fail paths, and GitHub Actions runs the suite.
