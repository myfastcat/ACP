# Agent Ready Map

**Find the safe automation boundary in a real workflow.**

Agent Ready Map helps teams decide where an AI agent can act autonomously, where AI should remain a copilot, and where a human approval gate belongs.

## Why this exists

Agent capability is moving faster than workflow redesign. The hard question is no longer only “can an agent do this?” but “what authority should it have at each step, and where should a human intervene?”

Agent Ready Map turns that question into a small, inspectable workflow exercise.

## What it does

1. Paste a workflow, one step per line.
2. Review each step's **judgment**, **data sensitivity**, **system access**, and **reversibility**.
3. Get one of three recommendations: **Agent-ready**, **Copilot**, or **Human-gated**.
4. See a control recommendation for every step.
5. Copy the complete operating map as Markdown and share it with the workflow owner.

## Try it in 60 seconds

Use a real process, for example:

```text
Receive inbound lead
Check company fit
Research account
Draft outreach
Approve message
Send email
Update CRM
```

Open `index.html` locally or serve this directory with any static web server. No setup, API key, account, or backend is required.

## How recommendations work

- **Agent-ready** — bounded, low-judgment, low-sensitivity, reversible work.
- **Copilot** — AI prepares or recommends, while a human owns interpretation or the final decision.
- **Human-gated** — high-impact, sensitive, write-capable, or hard-to-reverse work that should stop for explicit approval.

The initial rules are deliberately simple and visible. The point of the MVP is to learn where this model fails on real workflows rather than hide judgment behind an opaque score.

## Privacy

Everything runs locally in your browser. The MVP has no backend and does not send your workflow anywhere.

## Good workflows to map

- sales lead qualification;
- customer support escalation;
- invoice processing;
- recruiting coordination;
- software release workflows;
- internal research and reporting.

## Feedback experiment

Map **one real workflow**, then reply in [GitHub Issue #2](https://github.com/myfastcat/VCL/issues/2) with:

1. the workflow you mapped;
2. the classification that surprised you;
3. whether the map changed a human approval boundary;
4. a risk/control dimension that is missing;
5. whether you would use it on a second workflow.

Negative results are useful. If a spreadsheet or existing checklist is plainly better, say so.

## Important

This is a workflow-design aid, not a security, legal, risk, or compliance certification.
