#!/usr/bin/env python3
"""Local fast path for deterministic, zero-API PreToolUse approvals.

Only exact, bounded read-only checks are handled here. Everything else is
forwarded to run_supervisor.py, so the existing deny/review policy remains the
source of truth for all other operations.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

SAFE_ENV_INSPECTION = re.compile(
    r'^ls\s+-la\s+"\$LOCALAPPDATA/YT-Automation/"\s+2>&1$'
)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception as exc:
        print(f"local_pretool input error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    tool = payload.get("tool_name", "")
    command = ""
    if isinstance(payload.get("tool_input"), dict):
        command = str(payload["tool_input"].get("command", "")).strip()

    # This exact command only lists filenames/metadata in the supervisor's
    # DPAPI directory. It does not read file contents or execute anything.
    # The path is intentionally exact to avoid turning this into an arbitrary
    # filesystem enumeration allowlist.
    if tool == "Bash" and SAFE_ENV_INSPECTION.fullmatch(command):
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "permissionDecisionReason": "Bounded read-only inspection of the supervisor DPAPI directory; no API review required."
            }
        }))
        return 0

    supervisor = Path(__file__).with_name("run_supervisor.py")
    completed = subprocess.run(
        [sys.executable, str(supervisor), "pretool"],
        input=json.dumps(payload),
        text=True,
        stdout=sys.stdout,
        stderr=sys.stderr,
        check=False,
    )
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
