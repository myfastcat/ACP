# Changelog

## Unreleased

- Added non-invasive CI integration with `acp init --ci`.
- Added generated `.acp/config.json` and `.github/workflows/acp.yml`.
- Added `acp check` to collect existing JSON trace artifacts and evaluate them against the reviewed authority contract.
- Added explicit failure when required tool-call events are missing.
- Kept application source code free of ACP decorators/wrappers for the shipped Level 2 integration.
