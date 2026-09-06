# Implementation status

## Shipped in this increment

- `acp init --ci --test-command ...`
- generation of `.acp/authority.json`
- generation of `.acp/config.json`
- generation of `.github/workflows/acp.yml`
- non-invasive JSON trace-artifact discovery via configurable globs
- `acp check --config ...`
- explicit failure when required tool-call events are absent
- CI exit behavior for DENY / REQUIRE_APPROVAL
- unittest coverage for collection, CI generation, CLI init and gate behavior

## Not yet shipped

- framework-specific Level 1 adapters that pull native trace/event data automatically when no file artifact is already produced
- runtime production enforcement middleware
- centralized approval service

ACP must not advertise those capabilities as complete until there is inspectable code and automated evidence.
