# OpenAI Agents SDK capture

The bootstrap registers `OpenAIAgentsTraceCollector` through the SDK tracing processor interface using a temporary `sitecustomize.py` on `PYTHONPATH`. It records function span names and inputs to `.acp/traces/openai-agents-<pid>.json` at flush/shutdown, without modifying customer test source. Python processes that disable site initialization or do not load that environment are outside this capture path. Disabled/unavailable SDK tracing cannot produce evidence; `acp check` returns 4 if no observations exist.

The product CI includes a real installed SDK subprocess integration test. Unit mocks alone do not establish SDK compatibility. See the [README](../README.md) for setup, artifact paths and exit semantics.
