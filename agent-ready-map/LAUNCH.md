# Launch Agent Ready Map

Agent Ready Map is a tiny browser tool for answering a practical agentic-AI question:

> Which steps in this workflow should an agent run autonomously, which should stay in copilot mode, and which need a human gate?

It maps each step using four visible dimensions — judgment, data sensitivity, system access, and reversibility — and exports a shareable operating map.

Everything runs locally in the browser. No account, backend, or API key.

## Short launch post

**I built Agent Ready Map — a tiny local-first tool for finding the safe automation boundary in a workflow.**

Paste a real process, inspect each step's judgment/sensitivity/access/reversibility, and get an Agent-ready / Copilot / Human-gated recommendation plus suggested controls.

I'm specifically looking for cases where the recommendation is *wrong*. If you work with AI agents, try one real workflow and tell me which boundary you would change.

Product: https://github.com/myfastcat/VCL/tree/main/agent-ready-map
Feedback: https://github.com/myfastcat/VCL/issues/2

## Show HN version

**Title:** Show HN: Agent Ready Map – find where AI agents need human gates

I built a small browser-only tool to test a workflow-design question I've been seeing more often: once an AI agent can perform a task, where should we actually let it act autonomously?

Agent Ready Map takes a workflow one step per line. For each step you can adjust judgment, data sensitivity, system access, and reversibility. It then recommends one of three operating modes: Agent-ready, Copilot, or Human-gated, with a control suggestion.

The rules are intentionally simple and visible. This isn't a compliance product; the experiment is whether a lightweight map exposes useful disagreements before a team automates a process.

I'd especially value counterexamples. If you map a real workflow, which classification is wrong, and what variable is missing?

https://github.com/myfastcat/VCL/tree/main/agent-ready-map

## Community post version

Teams are moving from “can AI do this?” to “what authority should AI have here?”

I made a small local-first workflow mapper to make that boundary explicit. It classifies steps as Agent-ready, Copilot, or Human-gated based on judgment, sensitivity, access, and reversibility.

I'm not looking for generic feedback — I'm looking for one real workflow where the model gets the boundary wrong. That failure is the useful data.

https://github.com/myfastcat/VCL/tree/main/agent-ready-map
