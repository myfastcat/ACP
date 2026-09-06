from __future__ import annotations

import json
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .engine import evaluate_trace
from .normalize import TraceNormalizationError, normalize_trace

DEFAULT_TRACE_GLOBS = [
    ".acp/traces/**/*.json",
    "**/*trace*.json",
    "**/*tool-call*.json",
    "**/*tool_calls*.json",
]
DEFAULT_ACP_INSTALL = "git+https://github.com/myfastcat/VCL.git#subdirectory=agent-control-plane"


@dataclass(frozen=True)
class CollectedTrace:
    path: str
    events: tuple[dict, ...]


def default_config(contract: str = ".acp/authority.json") -> dict:
    return {
        "schema_version": "1",
        "contract": contract,
        "trace_globs": list(DEFAULT_TRACE_GLOBS),
        "fail_on_approval": True,
        "require_events": True,
        "zero_code_adapters": ["openai-agents"],
        "notes": "Non-invasive mode: ACP can auto-capture OpenAI Agents SDK function spans; other frameworks may point trace_globs at artifacts already emitted by normal tests.",
    }


def _is_ignored(path: Path) -> bool:
    ignored = {".git", ".venv", "venv", "site-packages", "node_modules"}
    return any(part in ignored for part in path.parts)


def collect_trace_files(root: str | Path, globs: Iterable[str]) -> list[CollectedTrace]:
    base = Path(root).resolve()
    candidates: dict[Path, None] = {}
    for pattern in globs:
        for path in base.glob(pattern):
            if path.is_file() and not _is_ignored(path):
                candidates[path.resolve()] = None
    collected: list[CollectedTrace] = []
    failures: list[str] = []
    for path in sorted(candidates):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            events = normalize_trace(raw)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, TraceNormalizationError, ValueError) as exc:
            failures.append(f"{path.relative_to(base)}: {exc}")
            continue
        if events:
            collected.append(CollectedTrace(str(path.relative_to(base)), tuple(events)))
    if candidates and not collected:
        detail = "; ".join(failures[:5])
        raise ValueError(f"Trace files matched but none contained supported tool-call events. {detail}".strip())
    return collected


def run_check(root: str | Path, config: dict, contract: dict) -> dict:
    traces = collect_trace_files(root, config.get("trace_globs", DEFAULT_TRACE_GLOBS))
    events: list[dict] = []
    sources: list[dict] = []
    for trace in traces:
        start = len(events)
        events.extend(trace.events)
        sources.append({"path": trace.path, "events": len(trace.events), "start_index": start})
    if config.get("require_events", True) and not events:
        raise ValueError(
            "No tool-call events found. For OpenAI Agents SDK, run tests through the generated ACP zero-code bootstrap; "
            "for other frameworks configure .acp/config.json trace_globs to point at existing JSON trace/event artifacts."
        )
    report = evaluate_trace(contract, events)
    report["sources"] = sources
    return report


def render_github_actions(test_command: str, python_version: str = "3.12", acp_install: str = DEFAULT_ACP_INSTALL) -> str:
    if not test_command.strip():
        raise ValueError("test_command is required to generate CI")
    wrapped_test = "python -m agent_control_plane.zero_code_runner -- sh -lc " + shlex.quote(test_command)
    return f'''name: ACP Authority Gate

on:
  pull_request:
  push:

jobs:
  authority:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "{python_version}"
      - name: Install project and ACP
        run: |
          python -m pip install --upgrade pip
          python -m pip install .
          python -m pip install "{acp_install}"
      - name: Run existing agent/integration tests with ACP zero-code bootstrap
        run: {wrapped_test}
      - name: Validate authority contract
        run: acp validate .acp/authority.json
      - name: ACP authority gate
        run: acp check --config .acp/config.json
'''
