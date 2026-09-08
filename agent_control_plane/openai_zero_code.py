from __future__ import annotations

import atexit
import json
import os
from pathlib import Path
from typing import Any


class OpenAIAgentsTraceCollector:
    """Collect OpenAI Agents SDK function spans without application-code changes.

    This object is registered through the SDK tracing processor API by ACP's
    bootstrap layer. It stores only function/tool-call input needed by ACP.
    """

    def __init__(self, trace_dir: str | Path = ".acp/traces") -> None:
        self.trace_dir = Path(trace_dir)
        self.events: list[dict[str, Any]] = []

    def on_trace_start(self, trace) -> None:
        return None

    def on_trace_end(self, trace) -> None:
        return None

    def on_span_start(self, span) -> None:
        return None

    def on_span_end(self, span) -> None:
        data = getattr(span, "span_data", None)
        if data is None or getattr(data, "type", None) != "function":
            return
        exported = data.export()
        name = exported.get("name")
        if not name:
            return
        raw_input = exported.get("input")
        arguments: Any = {}
        if isinstance(raw_input, str):
            try:
                arguments = json.loads(raw_input)
            except json.JSONDecodeError:
                arguments = {"value": raw_input}
        elif raw_input is not None:
            arguments = raw_input
        if not isinstance(arguments, dict):
            arguments = {"value": arguments}
        self.events.append({"tool": name, "arguments": arguments})

    def shutdown(self) -> None:
        self.flush()

    def force_flush(self) -> None:
        self.flush()

    def flush(self) -> None:
        if not self.events:
            return
        self.trace_dir.mkdir(parents=True, exist_ok=True)
        target = self.trace_dir / f"openai-agents-{os.getpid()}.json"
        tmp = target.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self.events, indent=2) + "\n", encoding="utf-8")
        tmp.replace(target)


def install(trace_dir: str | Path | None = None) -> bool:
    """Install the collector if the OpenAI Agents SDK is importable.

    Returns False when the SDK is unavailable. Application code is never
    imported or modified by this function.
    """
    try:
        from agents.tracing import add_trace_processor
    except ImportError:
        return False

    collector = OpenAIAgentsTraceCollector(trace_dir or os.environ.get("ACP_TRACE_DIR", ".acp/traces"))
    add_trace_processor(collector)
    atexit.register(collector.flush)
    return True
