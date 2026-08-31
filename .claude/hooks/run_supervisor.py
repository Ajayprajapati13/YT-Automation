#!/usr/bin/env python3
"""Launch supervisor.py with the user-scoped DPAPI secret, if configured."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from secret_store import unprotect


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in {"pretool", "posttool", "stop"}:
        print("Usage: run_supervisor.py {pretool|posttool|stop}", file=sys.stderr)
        return 2

    env = os.environ.copy()
    try:
        secret = unprotect()
    except Exception as exc:
        print(f"supervisor secret-store error: {type(exc).__name__}: {exc}", file=sys.stderr)
        secret = None

    if secret:
        env["OPENAI_API_KEY"] = secret

    supervisor = Path(__file__).with_name("supervisor.py")
    completed = subprocess.run(
        [sys.executable, str(supervisor), sys.argv[1]],
        stdin=sys.stdin,
        stdout=sys.stdout,
        stderr=sys.stderr,
        env=env,
        check=False,
    )

    # Claude Code treats exit code 2 as a hard block for PreToolUse/Stop.
    # Never let an unexpected supervisor failure silently permit a material action.
    if completed.returncode != 0:
        print("Supervisor failed closed: tool/action blocked.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
