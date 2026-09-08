# Agent Control Plane (ACP)

Check your agent's authority boundaries and incident invariants against tool calls from your existing tests before merging a change.

Python 3.10+. ACP is a deterministic **CI gate**: it observes test traces; it does not intercept production actions, execute approval requests, or replay a live agent from an incident.

**Had a duplicate tool call or email?** We are recruiting **3 pilot users** and offering free help turning one sanitized incident into a CI regression check. [Reply with your framework, one problem and when you can try ACP](https://github.com/myfastcat/ACP/issues/3) — no installation needed to start. [See the concrete customer demo](https://github.com/myfastcat/demo/tree/main/agent-control-plane).

## Set the boundary once

From your existing Python agent project (with installable `pyproject.toml` and its test dependencies):

```sh
python -m pip install "git+https://github.com/myfastcat/ACP.git"
acp init . --ci --test-command 'python -m unittest discover -s tests -v'
```

Replace the test command with the one your team already uses. `init` statically discovers Python functions decorated with `@function_tool`, `@tool`, `@mcp.tool()` or `@server.tool()`; it does not execute your source. No tools found → exit 4. Run from the customer project root; the optional path selects source to scan, while outputs are relative to the current directory.

| Customer command/input | Generated artifact | Automatic behavior / result |
| --- | --- | --- |
| `acp init . --ci --test-command '…'` + Python tools | `.acp/authority.json` | Draft read-like tools as ALLOW, mutations as REQUIRE_APPROVAL, destructive tools as DENY; unmatched actions DENY. **Review every rule**: names cannot establish real business authority. |
| Same command + existing test command | `.acp/config.json` | Default current observations `.acp/traces/**/*.json`; committed invariants `.acp/incidents/*.json`; approval blocks enabled. |
| Same command | `.github/workflows/acp.yml` | On push/PR: install customer project + ACP, run the existing tests through the capture bootstrap, then `acp check`. Test failure stops the job. |
| Same command | `.acp/incidents/` directory only | No invented incident or fixture. Empty directory is normal and need not be committed. Exit 0 means generated, **not safety verified**. |

`init` refuses to overwrite existing authority/config/workflow (exit 4). Commit the three generated files after reviewing them. The generated workflow installs dependencies declared by the customer project; if your tests need extra development dependencies, add your normal installation step there.

Example reviewed rule (inside `rules` in `.acp/authority.json`):

```json
{"id":"customer-lookup","decision":"ALLOW","when":[{"field":"action","op":"eq","value":"lookup_customer"}]}
```

Conditions within a rule are ANDed. All matching rules participate; DENY outranks REQUIRE_APPROVAL, which outranks ALLOW. Operators: `eq`, `ne`, `in`, `not_in`, `gt`, `gte`, `lt`, `lte`, `exists`; fields use dot paths such as `context.amount`. The [authority example](examples/procurement-contract.json) demonstrates complete policies.

## Protect every change automatically

The generated workflow executes these exact operations:

```sh
python -m agent_control_plane.zero_code_runner -- sh -c 'python -m unittest discover -s tests -v'
acp check --config .acp/config.json
```

The bootstrap adds an OpenAI Agents SDK tracing processor to Python test processes via `sitecustomize`; supported function spans become `.acp/traces/openai-agents-<pid>.json`. Existing test source remains unchanged. It preserves the test command's exit status. It refuses a non-empty previous trace directory: archive/remove old observations before starting a new run. Fresh GitHub checkouts must not commit `.acp/traces/`.

For other frameworks, keep your existing trace export and set `trace_globs` to its **current-run** JSON files. ACP accepts canonical `[{"action":"lookup_customer","context":{"id":"CUST-42"}}]`, tool/arguments records, and supported function-call containers (`output`, `messages`, `tool_calls`, `events`, `trace`, `items`). It does not auto-capture arbitrary frameworks. Archived inputs and incident fixtures must not be in current trace globs. Missing, empty, or malformed matched trace is exit 4 even if another file is valid; `require_events:false` cannot convert missing evidence into success. `acp check` cannot establish the freshness or completeness of arbitrary externally supplied traces: your test/export workflow must guarantee those.

## Learn from an actual incident

A customer supplies the historical JSON trace and chooses the invariant:

```sh
acp incident import incidents/raw-duplicate-email.json --incident-id INC-DUPLICATE-EMAIL
acp incident assert .acp/incidents/INC-DUPLICATE-EMAIL.json --max-occurrences send_email --max 1
```

| Command → input | Artifact → downstream effect | Output / exit |
| --- | --- | --- |
| `incident import` → customer's raw JSON trace | `.acp/incidents/INC-DUPLICATE-EMAIL.json`: normalized `incident_events`, ID, empty `assertions` | Prints event count, fixture path and next command; 0. Refuses overwrite or invalid/empty input: 4. |
| `incident assert … --max-occurrences send_email --max 1` → fixture + customer's business decision | Appends a deduplicated invariant to that fixture; preserves original incident events | Prints assertion count; 0. Invalid fixture/negative maximum: 4. |
| `incident assert … --must-not-occur delete_customer` or `--must-occur lookup_customer` | Adds a forbidden/required action invariant | Same semantics. |
| `acp check --json` → authority, current test traces, committed fixtures | Runs authority and **all incident invariants against current observed events**, not historical events | JSON summary, source paths/counts, decisions, per-incident failures + fixture SHA-256. No report file unless redirected. 0/2/3/4 below. |
| `acp incident replay .acp/incidents/INC-DUPLICATE-EMAIL.json --json --evidence incident-evidence.json` | Inspects the original incident only; writes fixture + result + hash into `incident-evidence.json` | Original duplicate email fails with 2 even after the product is fixed. This is not a current-code test. |

Commit the fixture after adding invariants. Imported fixtures without invariants fail with exit 4 instead of claiming regression coverage. Invariants count action occurrences across the **entire collected test run**, not per customer/session; scope trace globs to the scenario whose invariant you intend to enforce.

## Understand the CI result

| Exit | Meaning | Customer action |
| --- | --- | --- |
| **0** | Check has nonempty observations and no configured block | Gate passes for the observed behaviors only. |
| **2** | Any DENY or incident invariant failure | Fix the behavior or deliberately review the policy/invariant. Takes precedence over 3. |
| **3** | REQUIRE_APPROVAL and `fail_on_approval:true` | Review the action/policy. ACP does not implement an approval service. |
| **4** | Missing/invalid input, empty traces, invalid config/fixture, or CLI usage error | Repair the input/capture/setup; **no safety verdict**. Error on stderr. |

`summary.ci_pass` and `summary.exit_code` match `acp check`'s exit status. `fail_on_approval:false` deliberately allows approval-classified actions through CI; it does not record actual approval.

Other inspection commands: `acp validate .acp/authority.json` → `VALID`, exit 0 or 4; `acp normalize raw.json --out acp-trace.json` → normalized JSON, exit 0 or 4; `acp eval .acp/authority.json acp-trace.json --fail-on-approval --json` → authority-only report, exit 0/2/3/4. Without `--fail-on-approval`, `eval` permits approval results.

See the [customer CI demo](https://github.com/myfastcat/demo/tree/main/agent-control-plane) for concrete support-agent cases and workflow artifacts. Report installation friction or boundary requirements in [Issues](https://github.com/myfastcat/ACP/issues).

Repository scope: this repository is exclusively ACP; code/package/tests live at its root. The product repository is `myfastcat/ACP`; shared customer demos live in `myfastcat/demo`. Historical commits remain available.
