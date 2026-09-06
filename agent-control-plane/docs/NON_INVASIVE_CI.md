# Non-invasive CI setup

This is the exact customer setup for the current shipped Level 2 integration. It does not require ACP imports in application code.

## Customer actions

1. Install ACP.
2. From the agent repo root run:

   ```bash
   acp init . --agent <name> --ci --test-command "<existing integration test command>"
   ```

3. Review `.acp/authority.json` and edit the generated draft until it matches real business authority.
4. Run the existing tests once and identify the JSON trace/event artifact they already produce.
5. If ACP's default globs do not find that artifact, edit `.acp/config.json` `trace_globs` only. Do not add ACP instrumentation to app code for this integration level.
6. Run `acp check --config .acp/config.json` locally.
7. Commit `.acp/authority.json`, `.acp/config.json`, and `.github/workflows/acp.yml`.
8. On future PRs, review any ACP authority-gate failure before changing the contract.

## Important distinction

Current Level 2 non-invasive integration assumes normal tests/frameworks already emit a JSON trace/event artifact containing tool calls. ACP locates and normalizes that artifact automatically. If the framework emits no usable observable artifact at all, true Level 1 zero-code capture for that framework is not yet available; ACP must report the gap rather than ask the user to silently modify every tool.
