"""Shared boundary validation: malformed input is an error, never a pass."""
from __future__ import annotations


def object_value(value, label):
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def text_value(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value


def events_value(value, label="events"):
    if not isinstance(value, list) or not value:
        raise ValueError(f"{label} must be a non-empty list of tool-call events")
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
