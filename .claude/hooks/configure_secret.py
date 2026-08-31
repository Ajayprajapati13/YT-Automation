#!/usr/bin/env python3
"""One-time interactive setup for the supervisor OpenAI API key.

The key is entered with no terminal echo, encrypted with Windows DPAPI under
CurrentUser scope, and written outside the repository under %LOCALAPPDATA%.
"""
from __future__ import annotations

import getpass
import os
import sys

from secret_store import STORE_PATH, protect, unprotect


def main() -> int:
    if os.name != "nt":
        print("ERROR: This setup requires Windows DPAPI.", file=sys.stderr)
        return 1

    key = getpass.getpass("OpenAI API key (input is hidden): ").strip()
    if not key:
        print("ERROR: No key supplied.", file=sys.stderr)
        return 1
    if not key.startswith("sk-"):
        print("ERROR: The value does not look like an OpenAI API key.", file=sys.stderr)
        return 1

    protect(key)
    if unprotect() != key:
        print("ERROR: DPAPI verification failed.", file=sys.stderr)
        return 1

    print(f"Stored encrypted API key: {STORE_PATH}")
    print("Verification: OK (key value was not printed).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
