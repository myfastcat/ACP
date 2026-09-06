# Agent Ready Map — Worked Examples

These examples make it easy to test the product against realistic workflows instead of toy prompts.

## Example 1 — Inbound sales lead

Paste:

```text
Receive inbound lead
Check company fit
Research account
Draft outreach
Approve message
Send email
Update CRM
```

Questions to challenge the map with:

- Should account research be Agent-ready or Copilot if it uses only public data?
- Should sending email always be Human-gated, or can bounded templates execute autonomously?
- What changes if CRM write access is reversible and fully audited?

## Example 2 — Customer refund

Paste:

```text
Receive refund request
Read order history
Check refund policy
Assess exception request
Draft response
Approve refund
Issue refund
Notify customer
```

Questions to challenge the map with:

- Does a monetary threshold matter more than the generic write-access rule?
- Should policy-compliant refunds under a fixed amount be autonomous?
- Where should an exception force escalation?

## Example 3 — Software release

Paste:

```text
Collect merged changes
Generate release notes
Run automated tests
Review failed tests
Approve production release
Deploy to production
Monitor error rate
Rollback if error budget is exceeded
```

Questions to challenge the map with:

- Can deployment be Agent-ready when rollback is automatic and blast radius is bounded?
- Does production write access alone justify a human gate?
- Should the tool model confidence, blast radius, and monitoring quality separately?

## What useful feedback looks like

A useful test does not need to agree with the recommendation. The strongest feedback identifies a specific workflow step, the operating mode the tool proposed, the mode the workflow owner would actually choose, and why.

Share that evidence in [Issue #2](https://github.com/myfastcat/VCL/issues/2).
