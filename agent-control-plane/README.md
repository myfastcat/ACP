# Agent Control Plane

**Executable authority contracts for production AI agents with a non-invasive CI integration path.**

ACP turns agent authority boundaries into deterministic, testable policy. The default product direction is **non-invasive**: integrate at the repository/CI boundary instead of requiring ACP decorators, wrappers, or changes to every tool.

## Installation

ACP currently requires **Python 3.10+**. It is not yet published to PyPI, so install it directly from this repository:

```bash
python -m pip install "git+https://github.com/myfastcat/VCL.git#subdirectory=agent-control-plane"
```

Verify the installation:

```bash
acp --help
```

The installed package exposes the `acp` command. If `acp` is not found, make sure the Python environment where you installed ACP is the same environment used by your terminal/CI job.

### Add ACP to an existing Agent repository

Start from the root of your existing Agent project:

```bash
cd my-agent
```

Run one-time setup. Replace the test command with the command your project already uses:

```bash
acp init . \
  --agent my-agent \
  --ci \
  --test-command "pytest -q"
```

For a project that uses `unittest`, for example:

```bash
acp init . \
  --agent my-agent \
  --ci \
  --test-command "python -m unittest discover -s tests -v"
```

ACP generates:

```text
my-agent/
├── .acp/
│   ├── authority.json        # authority contract you review
│   └── config.json           # ACP integration/gate configuration
├── .github/
│   └── workflows/
│       └── acp.yml           # generated GitHub Actions authority gate
└── ... your existing Agent code
```

### The one thing you must review

Open:

```text
.acp/authority.json
```

`acp init` discovers tools and creates a **conservative draft**, not final production authorization. Review the real business boundary for every important action.

For example:

```text
search_customer      → ALLOW
update_customer      → REQUIRE_APPROVAL
issue_refund         → DENY
delete_customer      → DENY
```

Business-specific conditions such as amount thresholds, environment, tenant, data sensitivity, or approval group must reflect your actual policy. For example, your team might decide:

```text
refund < $100          → ALLOW
refund $100–$1000      → REQUIRE_APPROVAL
refund > $1000         → DENY
```

ACP intentionally does not grant final production authority just because a function name looks safe.

### Commit the ACP configuration

After reviewing the authority contract:

```bash
git add .acp .github/workflows/acp.yml
git commit -m "Add ACP authority gate"
git push
```

From then on, keep developing and testing your Agent normally. The generated GitHub Actions workflow runs the authority gate on changes.

### OpenAI Agents SDK: no application-code instrumentation

For **OpenAI Agents SDK**, ACP's generated CI uses the zero-code bootstrap. You do **not** need to:

- add `@acp.trace` or `@acp.tool` decorators;
- wrap `agent.run()` in an ACP context manager;
- modify each tool implementation;
- manually convert tool calls to `{action, context}`;
- hand-write a trace file for every CI run.

Keep your existing Agent tests unchanged. ACP registers an additional SDK trace processor at Python startup, records function/tool spans into `.acp/traces/`, normalizes them, and evaluates them against the reviewed authority contract.

The resulting flow is:

```text
normal Agent tests
      ↓
OpenAI Agents SDK function/tool spans
      ↓
ACP zero-code trace adapter
      ↓
{action, context}
      ↓
.acp/authority.json
      ↓
ALLOW / REQUIRE_APPROVAL / DENY
      ↓
GitHub CI gate
```

For other frameworks, ACP currently falls back to configuration-only integration: point `.acp/config.json` `trace_globs` at JSON trace/event artifacts already emitted by the framework or your existing tests. Explicit application instrumentation is the last-resort fallback, not the default product experience.

### Run the gate locally

After a test run has produced observable trace events, you can run:

```bash
acp check --config .acp/config.json
```

Exit codes:

| Exit code | Meaning |
|---|---|
| 0 | no denied actions and no approval failures |
| 2 | at least one denied action |
| 3 | approval required when `fail_on_approval` is enabled |
| 4 | invalid config / contract / trace input, or required events were not found |

## What the user does

For the normal non-invasive path, the complete responsibility is:

1. Install ACP in the repo/CI environment.
2. Run `acp init ... --ci --test-command "..."` once.
3. Review `.acp/authority.json` and confirm the real business authority boundary.
4. Commit `.acp/authority.json`, `.acp/config.json`, and `.github/workflows/acp.yml`.
5. Continue running the project's normal Agent/integration tests.
6. Review a PR when ACP reports a new `REQUIRE_APPROVAL` or `DENY` result.

That is the intended setup. For a supported zero-code framework, ACP-specific changes to Agent business code are not part of normal installation.

## Tool discovery

`acp init` currently recognizes common Python decorated tools:

- OpenAI Agents SDK style `@function_tool`
- MCP style `@mcp.tool()` / `@server.tool()`
- generic `@tool`

For every discovered tool ACP generates a draft rule and source inventory. The heuristic is deliberately conservative:

- read/search/list/get style tools → `ALLOW`
- obvious state-changing tools → `REQUIRE_APPROVAL`
- destructive or money-moving tools → `DENY`
- unknown semantics → `REQUIRE_APPROVAL`
- undiscovered actions → default `DENY`

Every generated contract is marked `review_required: true`.

## Where authority comes from

```text
repo/tool discovery + ACP conservative draft
                    +
       human-reviewed business authority
                    ↓
            .acp/authority.json
```

Static discovery reduces setup work; it does not grant production authority. The reviewed contract is the version-controlled source of truth.

## Where traces come from

ACP distinguishes two sources:

1. **Observed traces/events** — for OpenAI Agents SDK, ACP can auto-capture function spans during normal test execution using the SDK's tracing processor extension point; for other frameworks ACP can collect existing JSON trace artifacts.
2. **Synthetic/replay security traces** — optional fixtures deliberately constructed to exercise dangerous or boundary actions.

The collector searches configurable JSON globs, including `.acp/traces/**/*.json`, `**/*trace*.json`, `**/*tool-call*.json`, and `**/*tool_calls*.json`. It normalizes common shapes such as generic `{tool, arguments}`, OpenAI-style `function_call`, and nested `tool_calls`, `output`, `messages`, `events`, `items`, and `trace` containers.

Normalized events look like:

```json
{"action": "issue_refund", "context": {"amount": 42}}
```

If required tool-call events are not found, `acp check` fails explicitly instead of pretending capture succeeded.

## Integration hierarchy

```text
Level 1 — Zero-code framework adapter
OpenAI Agents SDK (shipped): SDK tracing processor → ACP automatically

Level 2 — Configuration-only adapter (shipped)
existing framework trace artifacts → .acp/config.json → ACP

Level 3 — Explicit instrumentation fallback
only when the framework exposes no usable observable output
```

## Design principles

ACP is deliberately **not an LLM judge**. The final authority decision is deterministic, inspectable, versionable and testable. Automation reduces setup effort, but generated contracts remain explicit and reviewable.

The risk score is advisory; `ALLOW / REQUIRE_APPROVAL / DENY` is the enforcement primitive.

## Current scope

Shipped today:

- static tool discovery;
- conservative contract drafting;
- common trace normalization;
- deterministic authority evaluation;
- non-invasive trace-artifact collection;
- `acp check` authority gate;
- `acp init --ci` generation of config and GitHub Actions CI;
- OpenAI Agents SDK zero-code function-span capture during CI test execution.

Next: add more Level 1 framework adapters, starting with MCP/LangGraph where there is a stable non-invasive event boundary. Runtime enforcement remains a later layer because it sits directly in the production execution path and has different reliability/security requirements.

## Feedback wanted

Would you install ACP if integration meant `acp init --ci` + review the generated authority contract + normal CI, with no changes to your agent business code? Please use GitHub Issue #3 and tell us which agent framework your team uses.
