# Agent Ready Map — Example

This example shows how to use Agent Ready Map on a realistic software release workflow.

## Workflow

1. Review release notes
2. Run automated tests
3. Inspect failed tests
4. Approve production deployment
5. Deploy to production
6. Verify production health
7. Roll back if health checks fail

## Example operating map

### 1. Review release notes
- Suggested mode: **Copilot**
- Why: judgment is useful, but no external write action is required.
- Control: require a human to accept the final interpretation.

### 2. Run automated tests
- Suggested mode: **Agent-ready**
- Why: bounded, repeatable, reversible, and low judgment.
- Control: define timeout and failure handling.

### 3. Inspect failed tests
- Suggested mode: **Copilot**
- Why: diagnosis can require interpretation.
- Control: show evidence and keep a human responsible for deciding what to do next.

### 4. Approve production deployment
- Suggested mode: **Human-gated**
- Why: high impact and hard to reverse.
- Control: explicit approval and an audit trail.

### 5. Deploy to production
- Suggested mode: **Human-gated**
- Why: write access plus high-impact external change.
- Control: preview the action, record who approved it, and preserve rollback capability.

### 6. Verify production health
- Suggested mode: **Agent-ready**
- Why: read-only verification with clear success criteria.
- Control: define what counts as healthy and how long to observe.

### 7. Roll back if health checks fail
- Suggested mode: **Human-gated**
- Why: consequential write action.
- Control: require approval unless a narrowly defined emergency rollback policy has already been authorized.

## What to look for

A useful map should change at least one decision about where autonomy starts or stops. If every classification feels obvious, the product may not be adding enough value — that is useful feedback too.

Feedback: https://github.com/myfastcat/VCL/issues/2
