"""Shared boundary validation: malformed input is an error, never a pass."""
from __future__ import annotations

import math


def object_value(value, label):
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def text_value(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value


def json_value(value, label):
    """Require a value that can be represented by strict JSON."""
    if value is None or type(value) in {str, bool, int}:
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError(f"{label} must not contain NaN or Infinity")
        return value
    if isinstance(value, list):
        for item in value:
            json_value(item, label)
        return value
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError(f"{label} object keys must be strings")
            json_value(item, label)
        return value
    raise ValueError(f"{label} must contain only JSON values")


def events_value(value, label="events"):
    if not isinstance(value, list) or not value:
        raise ValueError(f"{label} must be a non-empty list of tool-call events")
    json_value(value, label)
    for event in value:
        object_value(event, "event")
        text_value(event.get("action"), "event.action")
        object_value(event.get("context", {}), "event.context")
    return value


def patterns_value(value, label):
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list")
    for pattern in value:
        text_value(pattern, label)
        if pattern.startswith("/") or ".." in pattern.split("/"):
            raise ValueError(f"{label} must stay inside the project")
    return value
