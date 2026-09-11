from __future__ import annotations

import ast
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable


READ_HINTS = ("get", "list", "read", "search", "find", "lookup", "fetch", "inspect", "query")
HIGH_RISK_HINTS = ("delete", "remove", "destroy", "drop", "payment", "pay", "transfer", "wire", "refund", "revoke", "disable")
MUTATION_HINTS = ("create", "update", "write", "send", "publish", "post", "issue", "approve", "cancel", "execute", "modify", "set")
SUPPORTED_DECORATORS = {"function_tool", "tool", "mcp.tool", "server.tool"}


@dataclass(frozen=True)
class DiscoveredTool:
    name: str
    source: str
    line: int
    framework: str


def _decorator_name(node: ast.expr) -> str:
    if isinstance(node, ast.Call):
        node = node.func
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def _framework(decorator: str) -> str:
    if decorator == "function_tool":
        return "openai-agents"
    if decorator in {"mcp.tool", "server.tool"}:
        return "mcp"
    return "generic-python"


def discover_python_tools(root: str | Path) -> list[DiscoveredTool]:
    base = Path(root).resolve()
    tools: list[DiscoveredTool] = []
    for path in sorted(base.rglob("*.py")):
        if any(part.startswith(".") or part in {"venv", ".venv", "site-packages", "node_modules"} for part in path.relative_to(base).parts):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, UnicodeDecodeError, SyntaxError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator_node in node.decorator_list:
                decorator = _decorator_name(decorator_node)
                if decorator not in SUPPORTED_DECORATORS:
                    continue
                tools.append(DiscoveredTool(
                    name=node.name,
                    source=str(path.relative_to(base)),
                    line=node.lineno,
                    framework=_framework(decorator),
                ))
                break
    deduped: dict[str, DiscoveredTool] = {}
    for tool in tools:
        deduped.setdefault(tool.name, tool)
    return list(deduped.values())


def _name_tokens(name: str) -> set[str]:
    """Split snake/kebab/camel tool names without matching hints inside words."""
    words = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", name)
    return {part.lower() for part in re.findall(r"[A-Za-z0-9]+", words)}


def _draft_decision(name: str) -> tuple[str, int, str, bool, str]:
    tokens = _name_tokens(name)
    if tokens.intersection(HIGH_RISK_HINTS):
        return "DENY", 40, "external", True, "Conservative draft: high-impact or irreversible action. Review before enabling."
    if tokens.intersection(MUTATION_HINTS):
        return "REQUIRE_APPROVAL", 25, "customer", False, "Conservative draft: state-changing action requires review."
    if tokens.intersection(READ_HINTS):
        return "ALLOW", 5, "single_record", False, "Drafted as read-only from tool name. Verify semantics."
    return "REQUIRE_APPROVAL", 20, "team", False, "Unknown tool semantics; require approval until reviewed."


def draft_contract(agent_name: str, tools: Iterable[DiscoveredTool]) -> dict:
    rules = []
    inventory = []
    for tool in tools:
        decision, risk, blast, irreversible, reason = _draft_decision(tool.name)
        rules.append({
            "id": f"tool-{tool.name.replace('_', '-')}",
            "decision": decision,
            "when": [{"field": "action", "op": "eq", "value": tool.name}],
            "risk": risk,
            "blast_radius": blast,
            "irreversible": irreversible,
            "reason": reason,
        })
        inventory.append(asdict(tool))
    if not rules:
        raise ValueError("No supported tools discovered. Supported Python decorators: function_tool, tool, mcp.tool, server.tool")
    return {
        "schema_version": "1",
        "agent": {"name": agent_name},
        "default": {"decision": "DENY", "reason": "Undiscovered action; fail closed."},
        "rules": rules,
        "acp_generated": {
            "review_required": True,
            "warning": "This contract is a conservative draft generated from static tool discovery. Review every rule before production use.",
            "tool_inventory": inventory,
        },
    }
