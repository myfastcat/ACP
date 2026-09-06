# Zero-code integration contract

ACP's default integration boundary is the repository/CI environment, not application business code.

## Product promise

For a framework with a supported observable trace/event interface, installing ACP must not require changes to agent source code or individual tool implementations.

A supported adapter must:

1. identify the framework and available trace/event source;
2. consume existing framework-native output produced by normal agent/integration tests;
3. normalize tool calls to ACP `{action, context}` events;
4. preserve enough context for deterministic contract conditions;
5. fail explicitly when the expected trace source is missing or unreadable;
6. never report successful capture when no observable events were collected unless an explicit zero-event test is expected;
7. avoid executing production tools merely to create a trace.

## User-owned inputs

The user owns only the decisions that cannot safely be inferred:

- confirmation/editing of the generated authority boundary;
- business-specific conditions such as monetary thresholds, environment, tenant, data sensitivity, or approval group;
- normal integration tests that exercise the agent's intended workflows;
- optional synthetic security/replay cases for important dangerous paths;
- trace-source configuration only when ACP cannot auto-detect an existing source.

The user does not own ACP normalization adapters or ACP-specific application instrumentation for supported frameworks.

## CI contract

A generated customer workflow should conceptually perform:

```text
install → validate contract → run existing tests → locate native trace → normalize → evaluate → gate
```

The authority contract should be committed. Raw traces may be ephemeral CI artifacts when they contain sensitive workflow context; teams may commit sanitized replay/security fixtures where appropriate.

## Fallback behavior

If no supported zero-code adapter exists, ACP reports `zero_code_capture=unsupported` and explains the available configuration-only/manual fallback. Unsupported capture is not a successful integration.

## Definition of done for a framework adapter

A framework is advertised as zero-code supported only when an example agent can be checked in CI without importing ACP in its application source, and automated tests prove ALLOW, REQUIRE_APPROVAL, DENY, missing-trace, malformed-trace, and zero-event behavior.
