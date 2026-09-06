# Agent Control Plane

**Deterministic authority gates for production AI agents.**

ACP discovers what an agent can do, drafts an authority contract, observes tool calls during tests, and blocks authority regressions in CI with `ALLOW / REQUIRE_APPROVAL / DENY`.

For supported frameworks, ACP is **non-invasive**: no ACP decorators, no `agent.run()` wrapper, no per-tool changes, and no hand-written trace for every CI run.

## Install

Requires **Python 3.10+**. ACP is not yet on PyPI, so install it from this repository:

```bash
python -m pip install "git+https://github.com/myfastcat/VCL.git#subdirectory=agent-control-plane"
acp --help
```

## Add ACP to your Agent

From the root of your existing Agent repository, run one-time setup with your normal test command:

```bash
acp init . \
  --agent my-agent \
  --ci \
  --test-command "pytest -q"
```

ACP generates:

```text
.acp/authority.json        # authority contract — review this
.acp/config.json           # integration/gate configuration
.github/workflows/acp.yml  # GitHub Actions authority gate
```

### 1. Review the authority contract

`acp init` discovers tools and creates a **conservative draft**. You must confirm the real business authority boundary.

```text
search_customer      → ALLOW
update_customer      → REQUIRE_APPROVAL
issue_refund         → DENY
delete_customer      → DENY
```

Business-specific rules belong here too, for example:

```text
refund < $100          → ALLOW
refund $100–$1000      → REQUIRE_APPROVAL
refund > $1000         → DENY
```

ACP does not infer final production authorization solely from function names.

### 2. Commit the generated configuration

```bash
git add .acp .github/workflows/acp.yml
git commit -m "Add ACP authority gate"
git push
```

### 3. Keep developing normally

For **OpenAI Agents SDK**, ACP uses the SDK tracing processor at Python startup to capture function/tool spans during your existing tests. Your Agent application code does not import ACP.

```text
normal Agent tests
      ↓
function/tool calls
      ↓
ACP zero-code adapter
      ↓
authority.json
      ↓
ALLOW / REQUIRE_APPROVAL / DENY
      ↓
CI gate
```

For other frameworks, ACP currently uses a configuration-only fallback: point `.acp/config.json` `trace_globs` at JSON trace/event artifacts your framework or tests already produce.

## What you need to do

1. Install ACP.
2. Run `acp init ... --ci --test-command "..."` once.
3. Review `.acp/authority.json`.
4. Commit the generated ACP files.
5. Continue normal development and tests.
6. Review any new `REQUIRE_APPROVAL` or `DENY` result in CI.

For supported zero-code frameworks, you do **not** add ACP tracing code to your Agent.

## Run locally

After a test run has produced trace events:

```bash
acp check --config .acp/config.json
```

| Exit | Meaning |
|---|---|
| `0` | pass |
| `2` | denied action found |
| `3` | approval required when `fail_on_approval` is enabled |
| `4` | invalid input/config or required trace events missing |

## How it works

### Authority

```text
tool discovery + conservative ACP draft + human-reviewed business policy
                              ↓
                    .acp/authority.json
```

The reviewed contract is the source of truth.

### Trace

ACP evaluates observed tool calls, not model prose. OpenAI Agents SDK function spans are captured automatically; configured JSON traces are supported as the fallback. ACP normalizes them to:

```json
{"action": "issue_refund", "context": {"amount": 42}}
```

If required tool-call events are missing, ACP fails explicitly rather than reporting a false success.

### Tool discovery

`acp init` currently recognizes common Python tool decorators including:

- OpenAI Agents SDK `@function_tool`
- MCP `@mcp.tool()` / `@server.tool()`
- generic `@tool`

Draft policy is intentionally conservative: read/search operations tend toward `ALLOW`, state changes toward `REQUIRE_APPROVAL`, destructive or money-moving actions toward `DENY`, and unknown actions default to `DENY` or review.

## Integration support

| Level | Integration | Status |
|---|---|---|
| 1 | OpenAI Agents SDK zero-code trace adapter | Shipped |
| 2 | Existing JSON trace artifacts via `.acp/config.json` | Shipped |
| 3 | Explicit application instrumentation | Fallback only |

ACP's final authority decision is deterministic and testable; it is **not an LLM judge**.

Next: additional zero-code adapters such as MCP/LangGraph, followed later by runtime enforcement.

## Feedback

Try ACP and report your framework, integration experience, and authority use case in GitHub Issue #3.
