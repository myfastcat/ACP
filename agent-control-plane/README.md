# Agent Control Plane

**Deterministic authority gates for production AI agents.**

ACP discovers what an agent can do, drafts an authority contract, observes tool calls during tests, and blocks authority regressions in CI with `ALLOW / REQUIRE_APPROVAL / DENY`.

For supported frameworks ACP is non-invasive: no ACP decorators, `agent.run()` wrapper, or hand-written trace per CI run.

## 5-minute install
Requires Python 3.10+.

```bash
python -m pip install "git+https://github.com/myfastcat/VCL.git#subdirectory=agent-control-plane"
cd your-agent-repo
acp init . --agent my-agent --ci --test-command "pytest -q"
```

This generates `.acp/authority.json`, `.acp/config.json`, and `.github/workflows/acp.yml`.

## The only product decision you must make
Review `.acp/authority.json`: what may the agent do alone, what needs approval, and what must never happen? ACP deliberately will not invent your business authority boundary.

A copyable starting point is available at [`examples/authority.template.json`](examples/authority.template.json). Start conservative, then replace the example action patterns with your real tool names.

```text
search_customer  → ALLOW
update_customer  → REQUIRE_APPROVAL
issue_refund     → DENY
```

Then commit the generated files and keep running your existing tests. ACP observes tool calls and turns new `REQUIRE_APPROVAL` / `DENY` behavior into a CI failure instead of requiring changes to application code.

## How the gate works
```text
normal Agent tests → observed tool calls → ACP adapter → reviewed authority contract → ALLOW / REQUIRE_APPROVAL / DENY → CI
```

OpenAI Agents SDK function/tool spans are captured automatically. Other frameworks can point `.acp/config.json` `trace_globs` at JSON artifacts they already produce. Missing required trace events fail explicitly rather than creating a false pass.

## Run locally
```bash
acp check --config .acp/config.json
```

| Exit | Meaning |
|---|---|
| 0 | pass |
| 2 | denied action found |
| 3 | approval required and configured to fail |
| 4 | invalid config/input or missing required trace |

## Scope
Shipped: OpenAI Agents SDK zero-code adapter, existing JSON trace artifacts, deterministic contract evaluation, CI gate. Fallback: explicit instrumentation. Next adapters are driven by real integration evidence rather than framework count.

## Feedback
The most useful response is a real authority boundary. In GitHub Issue #3, paste three lists (redacted is fine):

```text
AUTONOMOUS: search_customer, read_ticket
APPROVAL: update_customer, send_email
FORBIDDEN: delete_customer, transfer_money
FRAMEWORK: OpenAI Agents SDK / MCP / LangGraph / other
```

Issue #3: https://github.com/myfastcat/VCL/issues/3
