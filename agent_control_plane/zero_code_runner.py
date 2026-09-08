from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path


SITECUSTOMIZE = """\
try:\n
    from agent_control_plane.openai_zero_code import install\n
    install()\n
except Exception as exc:\n
    if __import__('os').environ.get('ACP_BOOTSTRAP_STRICT') == '1':\n
        raise\n
"""


def run_zero_code(command: list[str], trace_dir: str = ".acp/traces") -> int:
    if not command:
        raise ValueError("command is required")
    trace_root = Path(trace_dir).resolve()
    if trace_root.exists() and any(trace_root.rglob("*.json")):
        raise ValueError("Trace directory contains previous observations; archive/remove them before a new run")
    with tempfile.TemporaryDirectory(prefix="acp-bootstrap-") as tmp:
        bootstrap = Path(tmp)
        (bootstrap / "sitecustomize.py").write_text(SITECUSTOMIZE, encoding="utf-8")
        env = os.environ.copy()
        env["ACP_TRACE_DIR"] = trace_dir
        current = env.get("PYTHONPATH")
        env["PYTHONPATH"] = str(bootstrap) if not current else str(bootstrap) + os.pathsep + current
        completed = subprocess.run(command, env=env)
        return int(completed.returncode)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] == "--":
        args = args[1:]
    try:
        return run_zero_code(args)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
