# Agent Incident Replay (AIR) — merged into ACP

AIR is no longer a separate active VCL product. Its incident normalization, invariant replay and evidence-pack workflow has been merged into **Agent Control Plane (ACP)** so users need one product, one trace pipeline and one CI surface.

Use ACP instead:

```bash
python -m pip install "git+https://github.com/myfastcat/VCL.git#subdirectory=agent-control-plane"
acp incident import raw-trace.json --incident-id INC-42
acp incident replay incident.fixture.json --evidence incident.evidence.json
```

Existing AIR source remains temporarily for historical/compatibility reference, but new development and feedback belong to ACP.

See `../agent-control-plane/README.md` for the unified workflow.
