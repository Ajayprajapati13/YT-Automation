#!/usr/bin/env python3
"""Local task handoff worker.

Watches SUPERVISOR/NEXT_TASK.md for a READY task and launches the bundled
Claude Code CLI (the same native binary the VS Code extension uses) in
headless print mode to execute it, exactly once per Task ID.

Design constraints (see SUPERVISOR/NEXT_TASK.md Task 0002):
  - Never pass --dangerously-skip-permissions, --permission-mode
    bypassPermissions, --restricted, --bare, or --safe-mode: all of these
    either bypass the permission system or disable project .claude/settings.json
    hooks. The whole point of this worker is that the spawned session is
    governed by the same supervisor hooks as any interactive session.
  - This worker never writes "DONE" into NEXT_TASK.md itself - that field is
    owned by the ChatGPT supervisor / repository owner. The worker only marks
    its own lifecycle as far as WAITING_REVIEW once the Claude session exits;
    a human/ChatGPT confirms completion out of band.
  - No secrets are read, logged, or transmitted. Auth is whatever the bundled
    CLI already uses for the logged-in user; this script never touches it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKER_DIR = Path(__file__).resolve().parent
SELF_PATH = Path(__file__).resolve()
NEXT_TASK_PATH = REPO_ROOT / "SUPERVISOR" / "NEXT_TASK.md"
GITHUB_TASK_REL_PATH = "SUPERVISOR/NEXT_TASK.md"  # path form git plumbing needs, relative to repo root
STATUS_PATH = REPO_ROOT / "SUPERVISOR" / "STATUS.md"
STATE_PATH = WORKER_DIR / "state.json"
INTEGRITY_PATH = WORKER_DIR / "integrity.json"
AUTHORIZED_AUTHORS_PATH = WORKER_DIR / "authorized_authors.json"
LOG_PATH = REPO_ROOT / "logs" / "task_worker.log"

DEFAULT_POLL_SECONDS = 60
DEFAULT_MIN_SECONDS_BETWEEN_LAUNCHES = 300
DEFAULT_MIN_SYNC_SECONDS = 300
GIT_TIMEOUT_SECONDS = 30
CLAUDE_LAUNCH_TIMEOUT_SECONDS = 4 * 60 * 60

WORKER_PROMPT = (
    "Read SUPERVISOR/NEXT_TASK.md and execute the READY task. "
    "Follow the task exactly. Work autonomously on the implementation and "
    "validation. Do not ask the user to copy/paste additional instructions "
    "unless a genuine human approval is required. Do not bypass or weaken "
    "the existing supervisor security controls."
)

# Flags that would bypass the permission system or disable project hooks.
# The worker must never add these to the launch command.
FORBIDDEN_FLAGS = {
    "--dangerously-skip-permissions",
    "--allow-dangerously-skip-permissions",
    "--restricted",
    "--bare",
    "--safe-mode",
}


class MalformedTaskError(Exception):
    """Raised when NEXT_TASK.md cannot be parsed for Status/Task ID."""


class TaskInfo:
    __slots__ = ("status", "task_id")

    def __init__(self, status: str, task_id: str) -> None:
        self.status = status
        self.task_id = task_id


def parse_task(text: str) -> TaskInfo:
    status_match = re.search(r"^\*\*Status:\*\*\s*(\S+)", text, re.MULTILINE)
    id_match = re.search(r"^\*\*Task ID:\*\*\s*(\S+)", text, re.MULTILINE)
    if not status_match or not id_match:
        raise MalformedTaskError("missing **Status:** or **Task ID:** field")
    return TaskInfo(status=status_match.group(1).strip(), task_id=id_match.group(1).strip())


def read_task(path: Path = NEXT_TASK_PATH) -> TaskInfo:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise MalformedTaskError(f"cannot read {path}: {exc}") from exc
    return parse_task(text)


def load_state(path: Path = STATE_PATH) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_state(state: dict, path: Path = STATE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    tmp.replace(path)


def write_status(task_id: str, state: str, detail: str, path: Path = STATUS_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y-%m-%dT%H:%M:%S")
    body = (
        "# Supervisor Worker Status\n\n"
        f"- Task ID: {task_id}\n"
        f"- State: {state}\n"
        f"- Updated: {timestamp}\n"
        f"- Detail: {detail}\n"
    )
    path.write_text(body, encoding="utf-8")


def log(message: str, path: Path = LOG_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y-%m-%dT%H:%M:%S")
    with path.open("a", encoding="utf-8") as fh:
        fh.write(f"{timestamp} {message}\n")


def compute_file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_integrity(self_path: Path = SELF_PATH, integrity_path: Path = INTEGRITY_PATH) -> tuple[bool, str]:
    """Refuse to run on-disk code that doesn't match the last reviewed/committed hash.

    This only guards against this file (task_worker.py) being modified out from
    under the worker - most plausibly by a Claude session the worker itself
    launched. It is tamper-evidence, not tamper-proofing: whoever can write
    task_worker.py can generally also write integrity.json next to it, since
    neither is protected by .claude/settings.json's permission deny-list the
    way SUPERVISOR/NEXT_TASK.md and .claude/hooks/** are. The durable fix is
    adding SUPERVISOR/worker/** to that deny-list; only a human/repository
    owner can make that change (Claude's own Edit/Write on .claude/settings.json
    is itself denied). This check still catches accidental/incidental drift,
    which is the more likely failure mode day to day.
    """
    if not integrity_path.exists():
        return False, f"{integrity_path.name} missing; run --update-integrity after reviewing {self_path.name}"
    try:
        recorded = json.loads(integrity_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return False, f"cannot read {integrity_path.name}: {type(exc).__name__}: {exc}"
    expected = recorded.get("sha256")
    try:
        actual = compute_file_hash(self_path)
    except OSError as exc:
        return False, f"cannot hash {self_path.name}: {exc}"
    if expected != actual:
        return False, (
            f"{self_path.name} does not match {integrity_path.name}; it has changed since "
            "the hash was last recorded. Refusing to run until a human reviews the change "
            "and re-runs --update-integrity."
        )
    return True, "ok"


def verify_hooks_configured(repo_root: Path = REPO_ROOT) -> tuple[bool, str]:
    """Refuse to launch Claude unless this repo's .claude/settings.json exists,
    parses as JSON, and actually declares PreToolUse/Stop hooks.

    The entire reason it's safe for this worker to launch a Claude session
    unattended is that the same supervisor hooks that govern this session
    also govern the launched one. This checks that precondition holds right
    before every launch, rather than assuming it.
    """
    settings_path = repo_root / ".claude" / "settings.json"
    if not settings_path.is_file():
        return False, f"{settings_path} not found; cannot verify supervisor hooks are configured"
    try:
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return False, f"cannot parse {settings_path.name}: {type(exc).__name__}: {exc}"
    hooks = settings.get("hooks", {})
    if not isinstance(hooks, dict):
        return False, f"{settings_path.name} has no valid 'hooks' object"
    required = {"PreToolUse", "Stop"}
    missing = required - set(hooks.keys())
    if missing:
        return False, f"{settings_path.name} is missing required hook(s): {', '.join(sorted(missing))}"
    return True, "ok"


# --- GitHub synchronization and commit-provenance authorization ---------
#
# A READY task in the local working tree is never, on its own, sufficient
# authorization to launch Claude - see run_once(). In GitHub-sync mode
# (github_remote set), the worker instead treats <remote>/<branch> as the
# source of truth, read via local git plumbing only (git show/git log
# against an already-fetched remote-tracking ref) - never a working-tree
# checkout, merge, or reset, so uncommitted local changes are never at risk.
# A task is auto-launch-authorized only if the commit that most recently
# touched NEXT_TASK.md on that ref was authored by an email present in
# authorized_authors.json - an explicit, human-maintained allowlist that
# ships empty. --approve-launch remains available as a manual override
# alongside this, for tasks that aren't (yet) commit-authorized.

def run_git(args: list, repo_root: Path, timeout: int = GIT_TIMEOUT_SECONDS) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=str(repo_root), capture_output=True, text=True, timeout=timeout, check=False,
    )


def sync_remote_ref(
    repo_root: Path,
    remote: str,
    branch: str,
    min_sync_interval: int,
    state: dict,
    now_fn: Callable[[], float] = time.time,
    task_rel_path: str = GITHUB_TASK_REL_PATH,
    run_git_fn: Callable[..., subprocess.CompletedProcess] = run_git,
) -> tuple[bool, dict, str]:
    """Sync with <remote>/<branch> and read NEXT_TASK.md's content and
    authoring commit from it, entirely via local git plumbing.

    Only runs `git fetch` (the one network operation here) if min_sync_interval
    seconds have passed since the last sync recorded in state["last_sync_at"].
    Between fetches, re-reads the already-fetched remote-tracking ref locally
    - free, no network. Never touches the working tree.

    Returns (ok, info, detail). On success, info has: task (TaskInfo),
    commit_sha, author_email, author_name, committed_at.
    """
    now = now_fn()
    last_sync_at = state.get("last_sync_at")
    if last_sync_at is None or (now - last_sync_at) >= min_sync_interval:
        fetch = run_git_fn(["fetch", "--quiet", remote, branch], repo_root)
        state["last_sync_at"] = now
        if fetch.returncode != 0:
            return False, {}, f"git fetch {remote} {branch} failed: {fetch.stderr.strip()[:300]}"

    ref = f"{remote}/{branch}"
    show = run_git_fn(["show", f"{ref}:{task_rel_path}"], repo_root)
    if show.returncode != 0:
        return False, {}, f"{task_rel_path} not found on {ref}: {show.stderr.strip()[:300]}"

    try:
        task = parse_task(show.stdout)
    except MalformedTaskError as exc:
        return False, {}, f"malformed task on {ref}: {exc}"

    log_result = run_git_fn(
        ["log", "-1", "--format=%H%x1f%ae%x1f%an%x1f%aI", ref, "--", task_rel_path],
        repo_root,
    )
    if log_result.returncode != 0 or not log_result.stdout.strip():
        return False, {}, f"could not determine authoring commit for {task_rel_path} on {ref}"
    try:
        sha, author_email, author_name, committed_at = log_result.stdout.strip().split("\x1f")
    except ValueError:
        return False, {}, "unexpected git log output format"

    return True, {
        "task": task,
        "commit_sha": sha,
        "author_email": author_email,
        "author_name": author_name,
        "committed_at": committed_at,
    }, "ok"


def load_authorized_authors(path: Path = AUTHORIZED_AUTHORS_PATH) -> set:
    """Empty by default (ships with no one authorized) until a human
    deliberately adds trusted committer emails - see authorized_authors.json."""
    if not path.exists():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    emails = data.get("authorized_emails", [])
    if not isinstance(emails, list):
        return set()
    return {e.strip().lower() for e in emails if isinstance(e, str) and e.strip()}


def is_author_authorized(author_email: str, authorized_emails: set) -> bool:
    return author_email.strip().lower() in authorized_emails


def _version_key(ext_dir: Path) -> tuple:
    match = re.search(r"anthropic\.claude-code-([\d.]+)-win32-x64$", ext_dir.name)
    if not match:
        return (0,)
    return tuple(int(part) for part in match.group(1).split(".") if part.isdigit())


def resolve_claude_executable(override: Optional[str] = None) -> Path:
    """Find the bundled Claude Code native binary.

    Precedence: explicit --claude-exe override > CLAUDE_CLI_PATH env var >
    newest anthropic.claude-code-*-win32-x64 VS Code extension. Never falls
    back to installing or downloading a second runtime.
    """
    if override:
        path = Path(override)
        if path.is_file():
            return path
        raise FileNotFoundError(f"configured claude executable not found: {path}")

    env_override = os.environ.get("CLAUDE_CLI_PATH")
    if env_override:
        path = Path(env_override)
        if path.is_file():
            return path
        raise FileNotFoundError(f"CLAUDE_CLI_PATH does not exist: {path}")

    ext_root = Path(os.environ.get("USERPROFILE", str(Path.home()))) / ".vscode" / "extensions"
    candidates = list(ext_root.glob("anthropic.claude-code-*-win32-x64"))
    for ext_dir in sorted(candidates, key=_version_key, reverse=True):
        exe = ext_dir / "resources" / "native-binary" / "claude.exe"
        if exe.is_file():
            return exe
    raise FileNotFoundError(
        f"bundled Claude Code executable not found under {ext_root}; "
        "set CLAUDE_CLI_PATH or pass --claude-exe to override"
    )


def launch_claude(claude_exe: Path, cwd: Path) -> subprocess.CompletedProcess:
    command = [str(claude_exe), "-p", WORKER_PROMPT, "--output-format", "json"]
    if FORBIDDEN_FLAGS & set(command):
        # Explicit check, not `assert`: assertions are compiled out under
        # python -O / PYTHONOPTIMIZE=1, which would silently disable this
        # guard. This must never be optimizable away.
        raise RuntimeError("forbidden flag in launch command; refusing to launch")
    return subprocess.run(
        command,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=CLAUDE_LAUNCH_TIMEOUT_SECONDS,
        check=False,
    )


def run_once(
    claude_exe_override: Optional[str] = None,
    launch_fn: Callable[[Path, Path], subprocess.CompletedProcess] = launch_claude,
    task_path: Path = NEXT_TASK_PATH,
    state_path: Path = STATE_PATH,
    status_path: Path = STATUS_PATH,
    log_path: Path = LOG_PATH,
    repo_root: Path = REPO_ROOT,
    min_launch_interval: int = DEFAULT_MIN_SECONDS_BETWEEN_LAUNCHES,
    now_fn: Callable[[], float] = time.time,
    approve_launch: bool = False,
    github_remote: Optional[str] = None,
    github_branch: str = "main",
    authorized_authors_path: Path = AUTHORIZED_AUTHORS_PATH,
    min_sync_interval: int = DEFAULT_MIN_SYNC_SECONDS,
    sync_fn: Callable[..., tuple] = sync_remote_ref,
) -> str:
    """Run a single poll cycle. Returns the resulting lifecycle state.

    Two independent ways a launch can be authorized, either is sufficient:
      - approve_launch=True: an explicit, one-off manual override (main()'s
        --approve-launch flag). Requires a human to act, every time.
      - github_remote set: the task is read from <github_remote>/<github_branch>
        (never the local working-tree file, never a checkout/merge) and is
        authorized only if the commit that last touched NEXT_TASK.md there was
        authored by an email in authorized_authors.json - auditable (commit
        SHA + author are logged) and doesn't require per-task human action,
        but also isn't satisfied merely because a local file says READY.

    Neither is the default: with neither set, a READY task is reported as
    PENDING_APPROVAL and nothing is ever launched.
    """
    state = load_state(state_path)
    authorized = False
    authorization_detail = "manual approval only (no GitHub sync configured)"

    if github_remote:
        ok, info, detail = sync_fn(repo_root, github_remote, github_branch, min_sync_interval, state, now_fn)
        save_state(state, state_path)  # persist last_sync_at even when nothing else changes below
        if not ok:
            log(f"github sync failed: {detail}", log_path)
            write_status(state.get("last_task_id", "unknown"), "SYNC_FAILED", detail, status_path)
            return "SYNC_FAILED"
        task = info["task"]
        authorized_emails = load_authorized_authors(authorized_authors_path)
        authorized = is_author_authorized(info["author_email"], authorized_emails)
        authorization_detail = (
            f"commit {info['commit_sha'][:12]} by {info['author_email']} on "
            f"{github_remote}/{github_branch} "
            f"({'authorized' if authorized else 'author not in authorized_authors.json'})"
        )
    else:
        try:
            task = read_task(task_path)
        except MalformedTaskError as exc:
            log(f"malformed task file: {exc}", log_path)
            write_status(state.get("last_task_id", "unknown"), "FAILED", f"Malformed NEXT_TASK.md: {exc}", status_path)
            return "FAILED"

    if task.status == "DONE":
        write_status(task.task_id, "DONE", "Task marked complete by human/ChatGPT supervisor.", status_path)
        return "DONE"

    if task.status != "READY":
        return "IDLE"

    already_handled = (
        state.get("last_task_id") == task.task_id
        and state.get("last_state") in {"IN_PROGRESS", "WAITING_REVIEW"}
    )
    if already_handled:
        return state["last_state"]

    can_launch = approve_launch or authorized
    if not can_launch:
        # Dry-run/manual-approval default: report that a task is ready and
        # waiting, but do not resolve or launch anything, and do not touch
        # last_launch_at (no launch happened, so the rate limiter window
        # must not be consumed by a mere approval/authorization check).
        log(f"task {task.task_id} ready; not authorized to launch ({authorization_detail})", log_path)
        write_status(
            task.task_id,
            "PENDING_APPROVAL",
            f"READY task detected but not authorized to launch ({authorization_detail}). "
            "Requires --approve-launch or an authorized GitHub commit.",
            status_path,
        )
        return "PENDING_APPROVAL"

    # Bound how fast distinct Task IDs can trigger launches, regardless of how
    # quickly NEXT_TASK.md changes. This is a launch-rate cap, not a per-ID
    # dedup (that's already handled by already_handled above) - it protects
    # against unbounded unattended execution if a sequence of new Task IDs
    # appears in quick succession.
    now = now_fn()
    last_launch_at = state.get("last_launch_at")
    if last_launch_at is not None and (now - last_launch_at) < min_launch_interval:
        wait_remaining = int(min_launch_interval - (now - last_launch_at))
        log(f"rate limited: task {task.task_id} must wait {wait_remaining}s before launch", log_path)
        write_status(
            task.task_id,
            "RATE_LIMITED",
            f"Minimum {min_launch_interval}s between launches; {wait_remaining}s remaining.",
            status_path,
        )
        return "RATE_LIMITED"

    hooks_ok, hooks_detail = verify_hooks_configured(repo_root)
    if not hooks_ok:
        log(f"hooks not verified, refusing to launch: {hooks_detail}", log_path)
        write_status(task.task_id, "FAILED", f"Hook verification failed: {hooks_detail}", status_path)
        return "FAILED"

    state.update(last_task_id=task.task_id, last_state="IN_PROGRESS", last_launch_at=now)
    save_state(state, state_path)
    write_status(
        task.task_id, "IN_PROGRESS",
        f"Launching Claude Code headlessly for this task. Authorization: {authorization_detail}.",
        status_path,
    )
    log(f"launching claude for task {task.task_id} ({authorization_detail})", log_path)

    try:
        claude_exe = resolve_claude_executable(claude_exe_override)
    except FileNotFoundError as exc:
        log(f"claude executable not found: {exc}", log_path)
        state.update(last_state="FAILED")
        save_state(state, state_path)
        write_status(task.task_id, "FAILED", str(exc), status_path)
        return "FAILED"

    try:
        result = launch_fn(claude_exe, repo_root)
    except Exception as exc:  # noqa: BLE001 - convert any launch failure into a safe FAILED state
        log(f"claude launch failed: {type(exc).__name__}: {exc}", log_path)
        state.update(last_state="FAILED")
        save_state(state, state_path)
        write_status(task.task_id, "FAILED", f"{type(exc).__name__}: {exc}", status_path)
        return "FAILED"

    if result.returncode == 0:
        state.update(last_state="WAITING_REVIEW")
        save_state(state, state_path)
        write_status(task.task_id, "WAITING_REVIEW", "Claude session finished; awaiting human/ChatGPT review.", status_path)
        log(f"claude finished task {task.task_id} rc=0", log_path)
        return "WAITING_REVIEW"

    state.update(last_state="FAILED")
    save_state(state, state_path)
    detail = f"claude exited with code {result.returncode}"
    write_status(task.task_id, "FAILED", detail, status_path)
    log(detail, log_path)
    return "FAILED"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="Run a single poll cycle and exit")
    parser.add_argument("--interval", type=int, default=DEFAULT_POLL_SECONDS, help="Seconds between polls (default: %(default)s)")
    parser.add_argument("--claude-exe", default=None, help="Explicit path to claude.exe (overrides auto-discovery)")
    parser.add_argument(
        "--min-launch-interval",
        type=int,
        default=DEFAULT_MIN_SECONDS_BETWEEN_LAUNCHES,
        help="Minimum seconds between any two Claude launches, across Task IDs (default: %(default)s)",
    )
    parser.add_argument(
        "--update-integrity",
        action="store_true",
        help="Record this file's current sha256 into integrity.json and exit. "
        "Only run this after a human has reviewed the change to task_worker.py.",
    )
    parser.add_argument(
        "--approve-launch",
        action="store_true",
        help="Manually approve launching Claude for a detected READY task, "
        "overriding GitHub commit authorization if present. Without this flag "
        "AND without an authorized GitHub commit (see --github-remote), the "
        "worker only detects/tracks/reports READY tasks as PENDING_APPROVAL "
        "and never launches anything.",
    )
    parser.add_argument(
        "--github-remote",
        default=None,
        help="Enable GitHub-sync mode: read NEXT_TASK.md from <remote>/<branch> "
        "instead of the local working-tree file, and auto-authorize a launch "
        "only if the commit that last touched it there was authored by an "
        "email listed in authorized_authors.json. Not set by default (local "
        "file + --approve-launch only).",
    )
    parser.add_argument("--github-branch", default="main", help="Branch to sync (default: %(default)s)")
    parser.add_argument(
        "--sync-interval",
        type=int,
        default=DEFAULT_MIN_SYNC_SECONDS,
        help="Minimum seconds between git fetch calls in GitHub-sync mode (default: %(default)s)",
    )
    args = parser.parse_args(argv)

    if args.update_integrity:
        INTEGRITY_PATH.write_text(
            json.dumps({"sha256": compute_file_hash(SELF_PATH)}, indent=2) + "\n", encoding="utf-8"
        )
        print(f"integrity.json updated for {SELF_PATH.name}")
        return 0

    ok, detail = verify_integrity()
    if not ok:
        log(f"integrity check failed: {detail}")
        write_status("unknown", "FAILED", f"Integrity check failed: {detail}")
        print(f"FAILED: {detail}", file=sys.stderr)
        return 2

    if args.once:
        state = run_once(
            args.claude_exe,
            min_launch_interval=args.min_launch_interval,
            approve_launch=args.approve_launch,
            github_remote=args.github_remote,
            github_branch=args.github_branch,
            min_sync_interval=args.sync_interval,
        )
        print(state)
        return 0

    if args.github_remote:
        log(f"worker starting in GitHub-sync mode ({args.github_remote}/{args.github_branch}): "
            "READY tasks are launched only if commit-authorized (authorized_authors.json) "
            "or manually approved with --approve-launch")
    elif args.approve_launch:
        log("worker starting with --approve-launch: READY tasks will be launched automatically")
    else:
        log("worker starting in default dry-run/manual-approval mode: READY tasks will be reported, not launched")
    try:
        while True:
            ok, detail = verify_integrity()
            if not ok:
                log(f"integrity check failed mid-loop: {detail}")
                write_status("unknown", "FAILED", f"Integrity check failed: {detail}")
                return 2
            run_once(
                args.claude_exe,
                min_launch_interval=args.min_launch_interval,
                approve_launch=args.approve_launch,
                github_remote=args.github_remote,
                github_branch=args.github_branch,
                min_sync_interval=args.sync_interval,
            )
            time.sleep(args.interval)
    except KeyboardInterrupt:
        log("worker stopped (KeyboardInterrupt)")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
