# Agent Control Plane (ACP)

**Deterministic authority gates for production AI agents.** ACP discovers agent tools, creates a draft authority contract, observes tool calls during tests, and makes CI fail when an agent crosses a reviewed `ALLOW / REQUIRE_APPROVAL / DENY` boundary.

## What ACP automates vs. what you must decide

ACP automates tool discovery, draft-file generation, trace collection for supported integrations, authority evaluation, exit codes, and GitHub Actions gate generation. **You must manually decide the business authority boundary.** ACP cannot safely decide which real-world actions your agent may take autonomously.

## Complete workflow

### 1. Prerequisites — manual

You need Python 3.10+, Git, a Python agent repository, and an existing test command that exercises the agent/tool calls you want governed. Run the commands below in a terminal.

Check Python:

```bash
python --version
```

Expected: Python 3.10 or newer.

### 2. Install ACP — manual

From any directory:

```bash
python -m pip install "git+https://github.com/myfastcat/VCL.git#subdirectory=agent-control-plane"
```

`python -m pip install` installs into the environment belonging to that Python interpreter. `git+https://...` tells pip to install from GitHub. `#subdirectory=agent-control-plane` selects ACP inside the VCL repository.

Verify:

```bash
acp --help
```

Expected: help containing `init`, `normalize`, `validate`, `eval`, and `check`. If `acp` is not found, activate the same virtual environment in which you installed it.

### 3. Initialize ACP in your agent repository — manual command, automatic discovery/generation

```bash
cd /path/to/your-agent-repo
acp init . --agent customer-support-agent --ci --test-command "pytest -q"
```

Replace `/path/to/your-agent-repo` with your repository. Arguments:

- `.` — path ACP scans for Python agent/tool definitions; `.` means the current directory.
- `--agent customer-support-agent` — name stored in the authority contract. Optional; without it ACP uses the directory/repository name.
- `--ci` — generate `.acp/config.json` and `.github/workflows/acp.yml` in addition to the authority contract.
- `--test-command "pytest -q"` — your **existing** integration-test command. Required when `--ci` is used. Replace it with the command that actually exercises your agent, e.g. `python -m pytest tests/integration -q`.
- `--out PATH` — optional alternative authority-contract path; default is `.acp/authority.json`.

Expected output includes `discovered=<number>`, `review_required=true`, and generated file names. With `--ci`, ACP generates `.acp/authority.json`, `.acp/config.json`, and `.github/workflows/acp.yml`.

If `discovered=0`, do not assume you are protected. Confirm your framework is supported or use existing JSON trace artifacts through `.acp/config.json`.

### 4. Review the authority boundary — **required manual decision**

Open `.acp/authority.json`. You must decide what the agent may do alone, what requires human approval, and what it must never do. A starting structure is:

```json
{
  "agent": "customer-support-agent",
  "default": "REQUIRE_APPROVAL",
  "rules": [
    {"id": "safe-read", "action": "read_*", "decision": "ALLOW", "reason": "read-only operations"},
    {"id": "external-write", "action": "send_*", "decision": "REQUIRE_APPROVAL", "reason": "external side effect"},
    {"id": "destructive", "action": "delete_*", "decision": "DENY", "reason": "destructive operation"}
  ]
}
```

Fields you edit:

- `agent` — human-readable agent name.
- `default` — decision used when no rule matches. Start conservatively with `REQUIRE_APPROVAL`.
- `rules` — ordered authority rules.
- `id` — unique readable identifier for the rule.
- `action` — tool/action pattern, such as `read_*`, `send_email`, or `delete_*`.
- `decision` — `ALLOW`, `REQUIRE_APPROVAL`, or `DENY`.
- `reason` — why this boundary exists; write something a reviewer can understand later.

Example business decision:

```text
search_customer  → ALLOW
update_customer  → REQUIRE_APPROVAL
issue_refund     → DENY
```

A copyable template is in `examples/authority.template.json`. Replace its example action names/patterns with your real tool names.

### 5. Validate your contract — manual

```bash
acp validate .acp/authority.json
```

Expected: `VALID`. Exit code `4` means invalid input/configuration; fix the reported error before continuing.

### 6. Run your normal agent tests — manual

Run the same command supplied to `--test-command`:

```bash
pytest -q
```

For OpenAI Agents SDK, ACP's supported adapter can capture function/tool spans without ACP decorators or wrapping `agent.run()`. For other frameworks, configure `.acp/config.json` `trace_globs` to point at JSON trace artifacts your tests already produce. The trace must contain the tool calls you want ACP to evaluate; missing required trace evidence must not be treated as a pass.

### 7. Run the authority gate locally — manual

```bash
acp check --config .acp/config.json
```

`--config` selects the generated ACP configuration; default is `.acp/config.json`, so `acp check` is equivalent when run from the expected repository layout. Add `--json` for machine-readable output:

```bash
acp check --config .acp/config.json --json
```

Interpret exit codes:

| Exit | Meaning | What you do |
|---|---|---|
| `0` | Gate passed | Continue/commit. |
| `2` | A `DENY` action occurred | Fix the agent/tool path or intentionally revise the reviewed contract. |
| `3` | `REQUIRE_APPROVAL` occurred and config fails on approval | Add the intended approval path or revise the boundary only if the business policy changed. |
| `4` | Invalid config/input or required trace missing | Fix configuration/trace collection; do not treat this as a governance pass. |

### 8. Commit ACP to Git — manual

After reviewing the contract and verifying the local gate:

```bash
git add .acp/authority.json .acp/config.json .github/workflows/acp.yml
git commit -m "add ACP authority gate"
git push
```

Review `.acp/authority.json` before committing it. The generated GitHub Actions workflow will run your existing test command and ACP gate in CI.

### 9. Confirm GitHub Actions — manual verification

Open your repository's **Actions** tab after pushing. Find the ACP workflow and confirm it passes. If it fails, open the job log and use the exit-code table above. Do not merge a governance-sensitive change merely because the application tests pass if ACP is failing.

### 10. Ongoing use

Keep running normal tests and `acp check` locally. When a PR adds/renames tools or changes what the agent is allowed to do, manually review `.acp/authority.json`; authority changes are business/security decisions, not something ACP should silently approve.

Useful lower-level commands:

```bash
acp normalize raw-trace.json --out acp-trace.json
acp eval .acp/authority.json acp-trace.json --fail-on-approval
```

`normalize` converts a framework-native/raw trace into ACP `{action, context}` events. `raw-trace.json` is your source trace; `--out` chooses the generated file (default `acp-trace.json`). `eval CONTRACT TRACE` evaluates an explicit contract and event list; `--fail-on-approval` makes approval-required events return exit `3`; `--normalize` can normalize a raw trace before evaluation; `--json` prints JSON.

## What ACP does not do

ACP does not invent your business authority policy, provide the human approval UI itself, prove a trace is complete when your instrumentation omitted events, or replace runtime authorization. It is a deterministic regression/CI authority gate over observed actions.

## Feedback

Real authority boundaries are the most useful feedback. In Issue #3, paste redacted lists like:

```text
AUTONOMOUS: search_customer, read_ticket
APPROVAL: update_customer, send_email
FORBIDDEN: delete_customer, transfer_money
FRAMEWORK: OpenAI Agents SDK / MCP / LangGraph / other
```

https://github.com/myfastcat/VCL/issues/3
