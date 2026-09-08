from __future__ import annotations

import json
from typing import Any, Iterable
from .validation import text_value, events_value


class TraceNormalizationError(ValueError):
    pass


def _parse_arguments(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise TraceNormalizationError(f"tool arguments are not valid JSON: {value!r}") from exc
        if not isinstance(parsed, dict):
            raise TraceNormalizationError("tool arguments JSON must decode to an object")
        return parsed
    raise TraceNormalizationError(f"unsupported tool arguments type: {type(value).__name__}")


def normalize_event(item: dict[str, Any]) -> dict[str, Any] | None:
    if "action" in item:
        context = item.get("context", {})
        if not isinstance(context, dict):
            raise TraceNormalizationError("context must be an object")
        return {"action": text_value(item["action"], "action"), "context": context}

    if "tool" in item and isinstance(item.get("tool"), str):
        return {"action": item["tool"], "context": _parse_arguments(item.get("arguments", item.get("args")))}

    if item.get("type") in {"function_call", "tool_call"}:
        name = item.get("name") or item.get("tool_name")
        if not name and isinstance(item.get("function"), dict):
            name = item["function"].get("name")
        if not name:
            raise TraceNormalizationError("tool call is missing a name")
        arguments = item.get("arguments", item.get("args"))
        if arguments is None and isinstance(item.get("function"), dict):
            arguments = item["function"].get("arguments")
        return {"action": str(name), "context": _parse_arguments(arguments)}

    if isinstance(item.get("function"), dict) and item["function"].get("name"):
        return {
            "action": str(item["function"]["name"]),
            "context": _parse_arguments(item["function"].get("arguments")),
        }

    # Common exported trace shape: tool_calls: [{"name": "...", "arguments": {...}}]
    if isinstance(item.get("name"), str) and ("arguments" in item or "args" in item):
        return {
            "action": item["name"],
            "context": _parse_arguments(item.get("arguments", item.get("args"))),
        }

    return None


def _walk(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        normalized = normalize_event(value)
        if normalized is not None:
            yield normalized
            return
        for key in ("tool_calls", "output", "items", "events", "messages", "trace"):
            if key in value:
                yield from _walk(value[key])
    elif isinstance(value, list):
        for item in value:
            yield from _walk(item)


def normalize_trace(payload: Any) -> list[dict[str, Any]]:
    events = list(_walk(payload))
    if not events:
        raise TraceNormalizationError("No supported tool calls found in trace")
    return events_value(events)
