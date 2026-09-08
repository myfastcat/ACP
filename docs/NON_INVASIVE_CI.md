# Existing tests as ACP inputs

The [README](../README.md) is the canonical operating guide. Run existing tests through `python -m agent_control_plane.zero_code_runner -- <test command>`, then `acp check` in the same working directory.

OpenAI Agents SDK function spans are captured by the bootstrap. Other frameworks must already export current JSON observations and configure `trace_globs`. Do not commit current traces or point globs at archived incident evidence. The bootstrap refuses stale traces; missing/invalid observations return 4. All fixtures' invariants apply to the complete collected current run. This is CI regression evaluation, not production enforcement.
