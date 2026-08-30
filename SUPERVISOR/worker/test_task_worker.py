"""Non-destructive unit tests for the task handoff worker.

Runs with the standard library only (no pytest dependency). Never launches a
real Claude Code process - the subprocess launch is always a stub function
injected via run_once(launch_fn=...).

Run with: python SUPERVISOR/worker/test_task_worker.py -v
"""
from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

import task_worker


def _fake_completed(returncode: int) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=["claude"], returncode=returncode, stdout="{}", stderr="")


FAKE_TRUSTED_KEY_ID = "ABCDEF0123456789"


def _fake_signature_fn(status="G", key=FAKE_TRUSTED_KEY_ID, signer="Test Signer <trusted@example.com>"):
    """A signature_fn stand-in for run_once()'s injectable seam - never
    invokes real git/gpg. Matches get_commit_signature_info()'s (ok, info,
    detail) contract exactly."""
    def _fn(repo_root, commit_sha):
        return True, {"sig_status": status, "signing_key": key, "signer_name": signer}, "ok"
    return _fn


class _GitFixture:
    """A local bare repo standing in for GitHub, an 'author' clone that
    commits/pushes to it (standing in for ChatGPT/whoever authors tasks), and
    a separate 'worker' clone (`local_path`) that only ever syncs via fetch -
    matching the real topology, where the worker's checkout is never the
    thing doing the pushing. This separation matters: `git push` updates the
    pusher's own remote-tracking ref as a side effect, independent of fetch -
    collapsing author and worker into one repo would make sync_remote_ref's
    fetch-rate-limiting untestable (it would always appear "already synced").
    No network either way - everything is plain filesystem paths."""

    def __init__(self, tmp_root: Path):
        self.remote_path = tmp_root / "remote.git"
        self.author_path = tmp_root / "author"
        self.local_path = tmp_root / "worker"  # this is what tests pass as repo_root
        self.author_path.mkdir()
        self.local_path.mkdir()
        self._git(["init", "--quiet", "--bare", "-b", "main", str(self.remote_path)], tmp_root)
        self._git(["init", "--quiet", "-b", "main"], self.author_path)
        self._git(["remote", "add", "origin", str(self.remote_path)], self.author_path)
        (self.author_path / "SUPERVISOR").mkdir()
        self._git(["init", "--quiet", "-b", "main"], self.local_path)
        self._git(["remote", "add", "origin", str(self.remote_path)], self.local_path)

    def _git(self, args: list, cwd: Path) -> subprocess.CompletedProcess:
        result = task_worker.run_git(args, cwd)
        if result.returncode != 0:
            raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr}")
        return result

    def commit_task(self, status: str, task_id: str, author_email: str, author_name: str = "Test Author") -> str:
        """Write+commit+push NEXT_TASK.md from the author clone, with an
        explicit, controlled commit author. Returns the new commit sha."""
        task_path = self.author_path / "SUPERVISOR" / "NEXT_TASK.md"
        task_path.write_text(f"**Status:** {status}\n**Task ID:** {task_id}\n", encoding="utf-8")
        self._git(["add", "SUPERVISOR/NEXT_TASK.md"], self.author_path)
        self._git(
            ["-c", f"user.email={author_email}", "-c", f"user.name={author_name}",
             "commit", "--quiet", "-m", f"task {task_id} {status}"],
            self.author_path,
        )
        self._git(["push", "--quiet", "origin", "main"], self.author_path)
        sha = self._git(["rev-parse", "HEAD"], self.author_path).stdout.strip()
        return sha


def _write_valid_hooks_config(repo_root: Path) -> None:
    """Mimic a repo_root with a real, minimally valid .claude/settings.json,
    so tests exercising an actual launch pass verify_hooks_configured()."""
    claude_dir = repo_root / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    (claude_dir / "settings.json").write_text(
        json.dumps({"hooks": {"PreToolUse": [], "Stop": []}}), encoding="utf-8"
    )


class ParseTaskTests(unittest.TestCase):
    def test_parses_status_and_task_id(self):
        text = "# Header\n\n**Status:** READY\n**Task ID:** 0002\n\n## Objective\nDo the thing.\n"
        task = task_worker.parse_task(text)
        self.assertEqual(task.status, "READY")
        self.assertEqual(task.task_id, "0002")

    def test_missing_status_raises(self):
        text = "# Header\n\n**Task ID:** 0002\n"
        with self.assertRaises(task_worker.MalformedTaskError):
            task_worker.parse_task(text)

    def test_missing_task_id_raises(self):
        text = "# Header\n\n**Status:** READY\n"
        with self.assertRaises(task_worker.MalformedTaskError):
            task_worker.parse_task(text)

    def test_empty_file_raises(self):
        with self.assertRaises(task_worker.MalformedTaskError):
            task_worker.parse_task("")


class RunOnceTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.task_path = root / "NEXT_TASK.md"
        self.state_path = root / "state.json"
        self.status_path = root / "STATUS.md"
        self.log_path = root / "worker.log"
        self.repo_root = root
        _write_valid_hooks_config(self.repo_root)

    def _write_task(self, status: str, task_id: str = "0002"):
        self.task_path.write_text(f"**Status:** {status}\n**Task ID:** {task_id}\n", encoding="utf-8")

    def _run_once(self, **overrides):
        kwargs = dict(
            task_path=self.task_path,
            state_path=self.state_path,
            status_path=self.status_path,
            log_path=self.log_path,
            repo_root=self.repo_root,
            # Tests in this class are about detection/dedup/failure paths,
            # not about the approval gate or rate limiter specifically, so
            # both default to "already handled" so a launch actually happens.
            min_launch_interval=0,
            approve_launch=True,
        )
        kwargs.update(overrides)
        return task_worker.run_once(**kwargs)

    def test_no_task_file_is_malformed_not_crash(self):
        result = self._run_once(launch_fn=lambda exe, cwd: _fake_completed(0))
        self.assertEqual(result, "FAILED")
        self.assertIn("FAILED", self.status_path.read_text(encoding="utf-8"))

    def test_status_not_ready_is_idle_and_does_not_launch(self):
        self._write_task("BLOCKED")
        calls = []
        result = self._run_once(launch_fn=lambda exe, cwd: calls.append(1) or _fake_completed(0))
        self.assertEqual(result, "IDLE")
        self.assertEqual(calls, [])
        self.assertFalse(self.status_path.exists())

    def test_status_done_is_reflected_without_launch(self):
        self._write_task("DONE")
        calls = []
        result = self._run_once(launch_fn=lambda exe, cwd: calls.append(1) or _fake_completed(0))
        self.assertEqual(result, "DONE")
        self.assertEqual(calls, [])

    def test_ready_task_launches_exactly_once_across_repeated_polls(self):
        self._write_task("READY", task_id="0002")
        calls = []

        def launch_fn(exe, cwd):
            calls.append((exe, cwd))
            return _fake_completed(0)

        first = self._run_once(launch_fn=launch_fn, claude_exe_override=__file__)
        second = self._run_once(launch_fn=launch_fn, claude_exe_override=__file__)
        third = self._run_once(launch_fn=launch_fn, claude_exe_override=__file__)

        self.assertEqual(first, "WAITING_REVIEW")
        self.assertEqual(second, "WAITING_REVIEW")
        self.assertEqual(third, "WAITING_REVIEW")
        self.assertEqual(len(calls), 1, "same Task ID must only launch Claude once")

    def test_new_task_id_after_completion_launches_again(self):
        self._write_task("READY", task_id="0002")
        calls = []

        def launch_fn(exe, cwd):
            calls.append(1)
            return _fake_completed(0)

        self._run_once(launch_fn=launch_fn, claude_exe_override=__file__)
        self._write_task("READY", task_id="0003")
        self._run_once(launch_fn=launch_fn, claude_exe_override=__file__)

        self.assertEqual(len(calls), 2, "a new Task ID must be picked up and launched")

    def test_claude_executable_not_found_fails_safely(self):
        self._write_task("READY")
        missing = str(Path(self._tmp.name) / "does-not-exist.exe")
        result = self._run_once(launch_fn=lambda exe, cwd: _fake_completed(0), claude_exe_override=missing)
        self.assertEqual(result, "FAILED")
        self.assertIn("FAILED", self.status_path.read_text(encoding="utf-8"))

    def test_launch_exception_fails_safely_without_raising(self):
        self._write_task("READY")

        def raising_launch(exe, cwd):
            raise OSError("simulated launch failure")

        result = self._run_once(launch_fn=raising_launch, claude_exe_override=__file__)
        self.assertEqual(result, "FAILED")
        self.assertIn("simulated launch failure", self.status_path.read_text(encoding="utf-8"))

    def test_nonzero_exit_is_failed(self):
        self._write_task("READY")
        result = self._run_once(launch_fn=lambda exe, cwd: _fake_completed(1), claude_exe_override=__file__)
        self.assertEqual(result, "FAILED")

    def test_no_secrets_written_to_status_or_log(self):
        self._write_task("READY")
        self._run_once(launch_fn=lambda exe, cwd: _fake_completed(0), claude_exe_override=__file__)
        combined = self.status_path.read_text(encoding="utf-8") + self.log_path.read_text(encoding="utf-8")
        for marker in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "sk-"):
            self.assertNotIn(marker, combined)


class ApprovalGateTests(unittest.TestCase):
    """The worker must never launch Claude for a READY task unless explicitly
    approved (approve_launch=True / --approve-launch). This is the default
    dry-run/manual-approval behavior, not an opt-in safety feature."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.task_path = root / "NEXT_TASK.md"
        self.state_path = root / "state.json"
        self.status_path = root / "STATUS.md"
        self.log_path = root / "worker.log"
        self.repo_root = root
        _write_valid_hooks_config(self.repo_root)

    def _write_task(self, status: str, task_id: str = "0002"):
        self.task_path.write_text(f"**Status:** {status}\n**Task ID:** {task_id}\n", encoding="utf-8")

    def _run_once(self, **overrides):
        kwargs = dict(
            task_path=self.task_path,
            state_path=self.state_path,
            status_path=self.status_path,
            log_path=self.log_path,
            repo_root=self.repo_root,
            min_launch_interval=0,
        )
        kwargs.update(overrides)
        return task_worker.run_once(**kwargs)

    def test_default_is_no_approval_and_does_not_launch(self):
        self._write_task("READY")
        calls = []
        # approve_launch intentionally not passed: must default to False.
        result = self._run_once(launch_fn=lambda exe, cwd: calls.append(1) or _fake_completed(0), claude_exe_override=__file__)
        self.assertEqual(result, "PENDING_APPROVAL")
        self.assertEqual(calls, [], "Claude must never be launched without explicit approval")
        self.assertIn("PENDING_APPROVAL", self.status_path.read_text(encoding="utf-8"))

    def test_explicit_approve_launch_false_also_does_not_launch(self):
        self._write_task("READY")
        calls = []
        result = self._run_once(
            launch_fn=lambda exe, cwd: calls.append(1) or _fake_completed(0),
            claude_exe_override=__file__, approve_launch=False,
        )
        self.assertEqual(result, "PENDING_APPROVAL")
        self.assertEqual(calls, [])

    def test_explicit_approval_launches(self):
        self._write_task("READY")
        calls = []
        launch_fn = lambda exe, cwd: calls.append(1) or _fake_completed(0)
        pending = self._run_once(launch_fn=launch_fn, claude_exe_override=__file__, approve_launch=False)
        approved = self._run_once(launch_fn=launch_fn, claude_exe_override=__file__, approve_launch=True)
        self.assertEqual(pending, "PENDING_APPROVAL")
        self.assertEqual(approved, "WAITING_REVIEW")
        self.assertEqual(len(calls), 1)

    def test_pending_approval_does_not_consume_rate_limit_window(self):
        # Repeated PENDING_APPROVAL polls (no approval given) must not touch
        # last_launch_at, since nothing was actually launched - approval must
        # not be throttled by the launch-rate limiter.
        self._write_task("READY")
        calls = []
        launch_fn = lambda exe, cwd: calls.append(1) or _fake_completed(0)
        self._run_once(launch_fn=launch_fn, claude_exe_override=__file__, approve_launch=False, min_launch_interval=300)
        self._run_once(launch_fn=launch_fn, claude_exe_override=__file__, approve_launch=False, min_launch_interval=300)
        approved = self._run_once(launch_fn=launch_fn, claude_exe_override=__file__, approve_launch=True, min_launch_interval=300)
        self.assertEqual(approved, "WAITING_REVIEW")
        self.assertEqual(len(calls), 1)


class RateLimitTests(unittest.TestCase):
    """Bounds how fast distinct Task IDs can trigger a launch (not per-ID dedup,
    which RunOnceTests covers separately)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.task_path = root / "NEXT_TASK.md"
        self.state_path = root / "state.json"
        self.status_path = root / "STATUS.md"
        self.log_path = root / "worker.log"
        self.repo_root = root
        _write_valid_hooks_config(self.repo_root)

    def _write_task(self, status: str, task_id: str):
        self.task_path.write_text(f"**Status:** {status}\n**Task ID:** {task_id}\n", encoding="utf-8")

    def _run_once(self, **overrides):
        kwargs = dict(
            task_path=self.task_path,
            state_path=self.state_path,
            status_path=self.status_path,
            log_path=self.log_path,
            repo_root=self.repo_root,
            approve_launch=True,
        )
        kwargs.update(overrides)
        return task_worker.run_once(**kwargs)

    def test_second_distinct_task_id_within_interval_is_rate_limited(self):
        calls = []
        clock = {"t": 1000.0}

        def launch_fn(exe, cwd):
            calls.append(1)
            return _fake_completed(0)

        self._write_task("READY", task_id="0002")
        first = self._run_once(
            launch_fn=launch_fn, claude_exe_override=__file__,
            min_launch_interval=300, now_fn=lambda: clock["t"],
        )
        self._write_task("READY", task_id="0003")
        clock["t"] += 10  # well inside the 300s cooldown
        second = self._run_once(
            launch_fn=launch_fn, claude_exe_override=__file__,
            min_launch_interval=300, now_fn=lambda: clock["t"],
        )

        self.assertEqual(first, "WAITING_REVIEW")
        self.assertEqual(second, "RATE_LIMITED")
        self.assertEqual(len(calls), 1, "the rate limiter must block the second launch")
        self.assertIn("RATE_LIMITED", self.status_path.read_text(encoding="utf-8"))

    def test_launch_allowed_again_once_interval_elapses(self):
        calls = []
        clock = {"t": 1000.0}

        def launch_fn(exe, cwd):
            calls.append(1)
            return _fake_completed(0)

        self._write_task("READY", task_id="0002")
        self._run_once(
            launch_fn=launch_fn, claude_exe_override=__file__,
            min_launch_interval=300, now_fn=lambda: clock["t"],
        )
        self._write_task("READY", task_id="0003")
        clock["t"] += 301  # past the cooldown
        result = self._run_once(
            launch_fn=launch_fn, claude_exe_override=__file__,
            min_launch_interval=300, now_fn=lambda: clock["t"],
        )

        self.assertEqual(result, "WAITING_REVIEW")
        self.assertEqual(len(calls), 2, "a launch must be allowed again once the cooldown has passed")

    def test_rate_limited_state_is_retried_next_poll_not_stuck(self):
        # A RATE_LIMITED outcome must not be recorded as "handled" - the same
        # Task ID must still be able to launch once the cooldown passes,
        # without needing a new Task ID.
        calls = []
        clock = {"t": 1000.0}

        def launch_fn(exe, cwd):
            calls.append(1)
            return _fake_completed(0)

        self._write_task("READY", task_id="0002")
        self._run_once(
            launch_fn=launch_fn, claude_exe_override=__file__,
            min_launch_interval=300, now_fn=lambda: clock["t"],
        )
        self._write_task("READY", task_id="0003")
        clock["t"] += 10
        limited = self._run_once(
            launch_fn=launch_fn, claude_exe_override=__file__,
            min_launch_interval=300, now_fn=lambda: clock["t"],
        )
        clock["t"] += 301
        retried = self._run_once(
            launch_fn=launch_fn, claude_exe_override=__file__,
            min_launch_interval=300, now_fn=lambda: clock["t"],
        )

        self.assertEqual(limited, "RATE_LIMITED")
        self.assertEqual(retried, "WAITING_REVIEW")
        self.assertEqual(len(calls), 2)


class VerifyIntegrityTests(unittest.TestCase):
    """task_worker.py refuses to run if its on-disk content doesn't match the
    last human-reviewed hash. These tests point verify_integrity() at fixture
    files, never at the real task_worker.py/integrity.json."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.self_path = root / "fake_worker.py"
        self.self_path.write_text("print('hello')\n", encoding="utf-8")
        self.integrity_path = root / "integrity.json"

    def test_missing_integrity_file_fails_closed(self):
        ok, detail = task_worker.verify_integrity(self.self_path, self.integrity_path)
        self.assertFalse(ok)
        self.assertIn("missing", detail)

    def test_matching_hash_passes(self):
        digest = task_worker.compute_file_hash(self.self_path)
        self.integrity_path.write_text(json.dumps({"sha256": digest}), encoding="utf-8")
        ok, _ = task_worker.verify_integrity(self.self_path, self.integrity_path)
        self.assertTrue(ok)

    def test_mismatched_hash_fails_closed(self):
        self.integrity_path.write_text(json.dumps({"sha256": "0" * 64}), encoding="utf-8")
        ok, detail = task_worker.verify_integrity(self.self_path, self.integrity_path)
        self.assertFalse(ok)
        self.assertIn("does not match", detail)

    def test_modification_after_baseline_is_detected(self):
        digest = task_worker.compute_file_hash(self.self_path)
        self.integrity_path.write_text(json.dumps({"sha256": digest}), encoding="utf-8")
        self.self_path.write_text("print('tampered')\n", encoding="utf-8")
        ok, _ = task_worker.verify_integrity(self.self_path, self.integrity_path)
        self.assertFalse(ok, "a file changed after the baseline was recorded must fail the check")

    def test_corrupt_integrity_json_fails_closed_not_crash(self):
        self.integrity_path.write_text("{not valid json", encoding="utf-8")
        ok, detail = task_worker.verify_integrity(self.self_path, self.integrity_path)
        self.assertFalse(ok)
        self.assertIn("cannot read", detail)


class VerifyHooksConfiguredTests(unittest.TestCase):
    """The worker must refuse to launch Claude if it can't confirm the repo's
    .claude/settings.json actually declares the supervisor hooks."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo_root = Path(self._tmp.name)

    def test_missing_settings_file_fails_closed(self):
        ok, detail = task_worker.verify_hooks_configured(self.repo_root)
        self.assertFalse(ok)
        self.assertIn("not found", detail)

    def test_valid_settings_with_required_hooks_passes(self):
        _write_valid_hooks_config(self.repo_root)
        ok, _ = task_worker.verify_hooks_configured(self.repo_root)
        self.assertTrue(ok)

    def test_settings_missing_stop_hook_fails_closed(self):
        claude_dir = self.repo_root / ".claude"
        claude_dir.mkdir(parents=True)
        (claude_dir / "settings.json").write_text(json.dumps({"hooks": {"PreToolUse": []}}), encoding="utf-8")
        ok, detail = task_worker.verify_hooks_configured(self.repo_root)
        self.assertFalse(ok)
        self.assertIn("Stop", detail)

    def test_corrupt_settings_json_fails_closed_not_crash(self):
        claude_dir = self.repo_root / ".claude"
        claude_dir.mkdir(parents=True)
        (claude_dir / "settings.json").write_text("{not valid json", encoding="utf-8")
        ok, detail = task_worker.verify_hooks_configured(self.repo_root)
        self.assertFalse(ok)
        self.assertIn("cannot parse", detail)

    def test_run_once_refuses_to_launch_without_verified_hooks(self):
        # End-to-end through run_once(): an approved launch must still be
        # blocked if the target repo_root has no valid .claude/settings.json,
        # even though the task is READY, approved, and not rate-limited.
        task_path = self.repo_root / "NEXT_TASK.md"
        task_path.write_text("**Status:** READY\n**Task ID:** 0002\n", encoding="utf-8")
        calls = []
        result = task_worker.run_once(
            claude_exe_override=__file__,
            launch_fn=lambda exe, cwd: calls.append(1) or _fake_completed(0),
            task_path=task_path,
            state_path=self.repo_root / "state.json",
            status_path=self.repo_root / "STATUS.md",
            log_path=self.repo_root / "worker.log",
            repo_root=self.repo_root,
            min_launch_interval=0,
            approve_launch=True,
        )
        self.assertEqual(result, "FAILED")
        self.assertEqual(calls, [], "must not launch when hooks cannot be verified")


class AuthorizedAuthorsTests(unittest.TestCase):
    """authorized_authors.json is empty by default: no email is trusted until
    a human deliberately adds one."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = Path(self._tmp.name) / "authorized_authors.json"

    def test_missing_file_means_no_one_authorized(self):
        emails = task_worker.load_authorized_authors(self.path)
        self.assertEqual(emails, set())
        self.assertFalse(task_worker.is_author_authorized("anyone@example.com", emails))

    def test_populated_file_authorizes_matching_email_case_insensitively(self):
        self.path.write_text(json.dumps({"authorized_emails": ["Trusted@Example.com"]}), encoding="utf-8")
        emails = task_worker.load_authorized_authors(self.path)
        self.assertTrue(task_worker.is_author_authorized("trusted@example.com", emails))
        self.assertFalse(task_worker.is_author_authorized("someone-else@example.com", emails))

    def test_corrupt_file_fails_closed_to_no_one_authorized(self):
        self.path.write_text("{not valid json", encoding="utf-8")
        emails = task_worker.load_authorized_authors(self.path)
        self.assertEqual(emails, set())


class TrustedSignersTests(unittest.TestCase):
    """trusted_signers.json is empty by default: no signing key is trusted
    until a human deliberately adds one."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = Path(self._tmp.name) / "trusted_signers.json"

    def test_missing_file_means_no_key_trusted(self):
        keys = task_worker.load_trusted_signers(self.path)
        self.assertEqual(keys, set())

    def test_populated_file_matches_case_insensitively(self):
        self.path.write_text(json.dumps({"trusted_key_ids": ["abcd1234"]}), encoding="utf-8")
        keys = task_worker.load_trusted_signers(self.path)
        self.assertIn("ABCD1234", keys)

    def test_corrupt_file_fails_closed_to_no_key_trusted(self):
        self.path.write_text("{not valid json", encoding="utf-8")
        keys = task_worker.load_trusted_signers(self.path)
        self.assertEqual(keys, set())


class GetCommitSignatureInfoTests(unittest.TestCase):
    """Parses git's %G?/%GK/%GS format output. Uses a fake run_git_fn stub
    returning exactly what real git would print for each signature state -
    no real git or gpg invocation needed to test the parsing itself."""

    def _stub(self, stdout: str, returncode: int = 0):
        def _fn(args, repo_root, timeout=None):
            return subprocess.CompletedProcess(args=args, returncode=returncode, stdout=stdout, stderr="")
        return _fn

    def test_good_signature_parsed(self):
        ok, info, _ = task_worker.get_commit_signature_info(
            Path("."), "deadbeef",
            run_git_fn=self._stub("G\x1fABCDEF0123456789\x1fTest Signer <trusted@example.com>\n"),
        )
        self.assertTrue(ok)
        self.assertEqual(info["sig_status"], "G")
        self.assertEqual(info["signing_key"], "ABCDEF0123456789")

    def test_unsigned_commit_parsed_as_n(self):
        ok, info, _ = task_worker.get_commit_signature_info(
            Path("."), "deadbeef", run_git_fn=self._stub("N\x1f\x1f\n"),
        )
        self.assertTrue(ok)
        self.assertEqual(info["sig_status"], "N")
        self.assertEqual(info["signing_key"], "")

    def test_git_command_failure_fails_safely(self):
        ok, info, detail = task_worker.get_commit_signature_info(
            Path("."), "deadbeef", run_git_fn=self._stub("", returncode=128),
        )
        self.assertFalse(ok)
        self.assertEqual(info, {})
        self.assertTrue(detail)

    def test_unexpected_format_fails_safely(self):
        ok, info, detail = task_worker.get_commit_signature_info(
            Path("."), "deadbeef", run_git_fn=self._stub("only one field\n"),
        )
        self.assertFalse(ok)
        self.assertIn("unexpected", detail.lower())


class IsCommitAuthorizedTests(unittest.TestCase):
    """The core authorization decision, tested as pure logic against every
    combination - no git/gpg involved. This is the truth table proving a
    spoofable author email is never sufficient by itself."""

    TRUSTED_EMAILS = {"trusted@example.com"}
    TRUSTED_KEYS = {"ABCDEF0123456789"}

    def _sig(self, status="G", key="ABCDEF0123456789"):
        return {"sig_status": status, "signing_key": key, "signer_name": "Test Signer"}

    def test_valid_signature_trusted_key_trusted_email_is_authorized(self):
        ok, reason = task_worker.is_commit_authorized(
            "trusted@example.com", self.TRUSTED_EMAILS, self._sig(), self.TRUSTED_KEYS,
        )
        self.assertTrue(ok, reason)

    def test_no_signature_is_never_authorized_even_with_trusted_email(self):
        # The critical case: spoofed/plain author-email metadata claiming to
        # be the trusted author, but the commit isn't signed at all.
        ok, reason = task_worker.is_commit_authorized(
            "trusted@example.com", self.TRUSTED_EMAILS, self._sig(status="N", key=""), self.TRUSTED_KEYS,
        )
        self.assertFalse(ok)
        self.assertIn("no valid commit signature", reason)

    def test_bad_signature_is_never_authorized_even_with_trusted_email(self):
        ok, reason = task_worker.is_commit_authorized(
            "trusted@example.com", self.TRUSTED_EMAILS, self._sig(status="B"), self.TRUSTED_KEYS,
        )
        self.assertFalse(ok)

    def test_expired_or_revoked_signature_is_never_authorized(self):
        for status in ("X", "Y", "R", "E"):
            ok, reason = task_worker.is_commit_authorized(
                "trusted@example.com", self.TRUSTED_EMAILS, self._sig(status=status), self.TRUSTED_KEYS,
            )
            self.assertFalse(ok, f"status={status} must not be authorized")

    def test_valid_signature_from_untrusted_key_is_not_authorized(self):
        ok, reason = task_worker.is_commit_authorized(
            "trusted@example.com", self.TRUSTED_EMAILS, self._sig(key="0000000000000000"), self.TRUSTED_KEYS,
        )
        self.assertFalse(ok)
        self.assertIn("not in trusted_signers.json", reason)

    def test_valid_trusted_signature_with_untrusted_email_is_not_authorized(self):
        ok, reason = task_worker.is_commit_authorized(
            "untrusted@example.com", self.TRUSTED_EMAILS, self._sig(), self.TRUSTED_KEYS,
        )
        self.assertFalse(ok)
        self.assertIn("authorized_authors.json", reason)

    def test_unknown_trust_status_u_is_accepted_when_key_and_email_trusted(self):
        # "U" = cryptographically good signature, key ownertrust just isn't
        # certified in GPG's own web-of-trust - which this design doesn't
        # rely on (trusted_signers.json is the trust anchor instead).
        ok, reason = task_worker.is_commit_authorized(
            "trusted@example.com", self.TRUSTED_EMAILS, self._sig(status="U"), self.TRUSTED_KEYS,
        )
        self.assertTrue(ok, reason)

    def test_empty_signing_key_is_never_authorized(self):
        ok, reason = task_worker.is_commit_authorized(
            "trusted@example.com", self.TRUSTED_EMAILS, self._sig(status="G", key=""), self.TRUSTED_KEYS,
        )
        self.assertFalse(ok)


class GitHubSyncTests(unittest.TestCase):
    """sync_remote_ref() reads NEXT_TASK.md and its authoring commit from
    <remote>/<branch> via local git plumbing only - a bare repo on disk
    stands in for GitHub, so this never touches the network."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp_root = Path(self._tmp.name)
        self.fixture = _GitFixture(self.tmp_root)

    def test_sync_reads_task_and_commit_provenance(self):
        sha = self.fixture.commit_task("READY", "0002", "trusted@example.com")
        state = {}
        ok, info, detail = task_worker.sync_remote_ref(
            self.fixture.local_path, "origin", "main", min_sync_interval=0, state=state,
        )
        self.assertTrue(ok, detail)
        self.assertEqual(info["task"].status, "READY")
        self.assertEqual(info["task"].task_id, "0002")
        self.assertEqual(info["author_email"], "trusted@example.com")
        self.assertEqual(info["commit_sha"], sha)
        self.assertIn("last_sync_at", state)

    def test_sync_failure_on_unreachable_remote_fails_safely(self):
        task_worker.run_git(
            ["remote", "set-url", "origin", str(self.tmp_root / "does-not-exist")],
            self.fixture.local_path,
        )
        ok, info, detail = task_worker.sync_remote_ref(
            self.fixture.local_path, "origin", "main", min_sync_interval=0, state={},
        )
        self.assertFalse(ok)
        self.assertTrue(detail)
        self.assertEqual(info, {})

    def test_sync_rate_limits_fetch_but_still_reads_locally(self):
        self.fixture.commit_task("READY", "0002", "trusted@example.com")
        state = {}
        clock = {"t": 1000.0}

        ok1, info1, _ = task_worker.sync_remote_ref(
            self.fixture.local_path, "origin", "main", min_sync_interval=300,
            state=state, now_fn=lambda: clock["t"],
        )
        self.assertTrue(ok1)
        first_sync_at = state["last_sync_at"]

        self.fixture.commit_task("READY", "0003", "trusted@example.com")
        clock["t"] += 10  # still inside the 300s sync interval
        ok2, info2, _ = task_worker.sync_remote_ref(
            self.fixture.local_path, "origin", "main", min_sync_interval=300,
            state=state, now_fn=lambda: clock["t"],
        )
        self.assertTrue(ok2)
        self.assertEqual(info2["task"].task_id, "0002", "must not have re-fetched yet, so still sees the old commit")
        self.assertEqual(state["last_sync_at"], first_sync_at, "must not fetch again inside the interval")

        clock["t"] += 301  # past the interval
        ok3, info3, _ = task_worker.sync_remote_ref(
            self.fixture.local_path, "origin", "main", min_sync_interval=300,
            state=state, now_fn=lambda: clock["t"],
        )
        self.assertTrue(ok3)
        self.assertEqual(info3["task"].task_id, "0003", "must fetch again once the interval has passed")
        self.assertGreater(state["last_sync_at"], first_sync_at)

    def test_malformed_task_on_remote_fails_safely(self):
        task_path = self.fixture.author_path / "SUPERVISOR" / "NEXT_TASK.md"
        task_path.write_text("not a task file\n", encoding="utf-8")
        task_worker.run_git(["add", "SUPERVISOR/NEXT_TASK.md"], self.fixture.author_path)
        task_worker.run_git(
            ["-c", "user.email=trusted@example.com", "-c", "user.name=Trusted",
             "commit", "--quiet", "-m", "bad"],
            self.fixture.author_path,
        )
        task_worker.run_git(["push", "--quiet", "origin", "main"], self.fixture.author_path)
        ok, info, detail = task_worker.sync_remote_ref(
            self.fixture.local_path, "origin", "main", min_sync_interval=0, state={},
        )
        self.assertFalse(ok)
        self.assertIn("malformed", detail.lower())


class RunOnceGitHubModeTests(unittest.TestCase):
    """End-to-end run_once() in GitHub-sync mode: commit-provenance
    authorization gates launches without requiring --approve-launch every
    time, while all the existing safety checks (dedup, rate limit, hooks,
    forbidden flags) still apply exactly as in local-file mode."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp_root = Path(self._tmp.name)
        self.fixture = _GitFixture(self.tmp_root)
        _write_valid_hooks_config(self.fixture.local_path)
        self.state_path = self.fixture.local_path / "state.json"
        self.status_path = self.fixture.local_path / "STATUS.md"
        self.log_path = self.fixture.local_path / "worker.log"
        self.authorized_authors_path = self.fixture.local_path / "authorized_authors.json"
        self.trusted_signers_path = self.fixture.local_path / "trusted_signers.json"
        self.trusted_signers_path.write_text(
            json.dumps({"trusted_key_ids": [FAKE_TRUSTED_KEY_ID]}), encoding="utf-8"
        )

    def _run_once(self, **overrides):
        kwargs = dict(
            state_path=self.state_path,
            status_path=self.status_path,
            log_path=self.log_path,
            repo_root=self.fixture.local_path,
            github_remote="origin",
            github_branch="main",
            authorized_authors_path=self.authorized_authors_path,
            trusted_signers_path=self.trusted_signers_path,
            min_sync_interval=0,
            min_launch_interval=0,
            # Tests in this class are about dedup/hooks/forbidden-flags/etc,
            # not the signature mechanism itself (see
            # RunOnceGitHubModeSignatureTests for that) - default to a
            # signature that's already valid and from the pre-trusted key,
            # so only the author-email allowlist varies per test as before.
            signature_fn=_fake_signature_fn(),
        )
        kwargs.update(overrides)
        return task_worker.run_once(**kwargs)

    def test_authorized_commit_launches_without_manual_approval(self):
        self.authorized_authors_path.write_text(
            json.dumps({"authorized_emails": ["trusted@example.com"]}), encoding="utf-8"
        )
        self.fixture.commit_task("READY", "0002", "trusted@example.com")
        calls = []
        result = self._run_once(
            launch_fn=lambda exe, cwd: calls.append(1) or _fake_completed(0),
            claude_exe_override=__file__,
            # approve_launch intentionally omitted - authorization alone must be enough.
        )
        self.assertEqual(result, "WAITING_REVIEW")
        self.assertEqual(len(calls), 1)

    def test_unauthorized_commit_does_not_launch(self):
        # authorized_authors.json left unpopulated - no one is authorized.
        self.fixture.commit_task("READY", "0002", "untrusted@example.com")
        calls = []
        result = self._run_once(
            launch_fn=lambda exe, cwd: calls.append(1) or _fake_completed(0),
            claude_exe_override=__file__,
        )
        self.assertEqual(result, "PENDING_APPROVAL")
        self.assertEqual(calls, [])

    def test_unauthorized_commit_can_still_be_manually_approved(self):
        self.fixture.commit_task("READY", "0002", "untrusted@example.com")
        calls = []
        result = self._run_once(
            launch_fn=lambda exe, cwd: calls.append(1) or _fake_completed(0),
            claude_exe_override=__file__,
            approve_launch=True,
        )
        self.assertEqual(result, "WAITING_REVIEW")
        self.assertEqual(len(calls), 1)

    def test_sync_failure_reports_sync_failed_and_does_not_launch(self):
        task_worker.run_git(
            ["remote", "set-url", "origin", str(self.tmp_root / "does-not-exist")],
            self.fixture.local_path,
        )
        calls = []
        result = self._run_once(
            launch_fn=lambda exe, cwd: calls.append(1) or _fake_completed(0),
            claude_exe_override=__file__,
        )
        self.assertEqual(result, "SYNC_FAILED")
        self.assertEqual(calls, [])

    def test_local_working_tree_edit_is_ignored_in_github_mode(self):
        # The remote (authorized) task says BLOCKED. A local-only edit
        # claiming READY must have zero effect - GitHub-sync mode never
        # reads the local working-tree file at all.
        self.authorized_authors_path.write_text(
            json.dumps({"authorized_emails": ["trusted@example.com"]}), encoding="utf-8"
        )
        self.fixture.commit_task("BLOCKED", "0002", "trusted@example.com")
        tampered_path = self.fixture.local_path / "SUPERVISOR" / "NEXT_TASK.md"
        tampered_path.parent.mkdir(parents=True, exist_ok=True)
        tampered_path.write_text("**Status:** READY\n**Task ID:** 9999\n", encoding="utf-8")
        calls = []
        result = self._run_once(
            launch_fn=lambda exe, cwd: calls.append(1) or _fake_completed(0),
            claude_exe_override=__file__,
            task_path=tampered_path,  # even if something pointed at it, it must be ignored
        )
        self.assertEqual(result, "IDLE")
        self.assertEqual(calls, [])

    def test_duplicate_task_id_not_relaunched_in_github_mode(self):
        self.authorized_authors_path.write_text(
            json.dumps({"authorized_emails": ["trusted@example.com"]}), encoding="utf-8"
        )
        self.fixture.commit_task("READY", "0002", "trusted@example.com")
        calls = []
        launch_fn = lambda exe, cwd: calls.append(1) or _fake_completed(0)
        first = self._run_once(launch_fn=launch_fn, claude_exe_override=__file__)
        second = self._run_once(launch_fn=launch_fn, claude_exe_override=__file__)
        self.assertEqual(first, "WAITING_REVIEW")
        self.assertEqual(second, "WAITING_REVIEW")
        self.assertEqual(len(calls), 1)

    def test_hooks_still_enforced_in_github_mode(self):
        self.authorized_authors_path.write_text(
            json.dumps({"authorized_emails": ["trusted@example.com"]}), encoding="utf-8"
        )
        self.fixture.commit_task("READY", "0002", "trusted@example.com")
        # Break the hooks config to prove it's still checked in GitHub mode too.
        (self.fixture.local_path / ".claude" / "settings.json").write_text(
            json.dumps({"hooks": {}}), encoding="utf-8"
        )
        calls = []
        result = self._run_once(
            launch_fn=lambda exe, cwd: calls.append(1) or _fake_completed(0),
            claude_exe_override=__file__,
        )
        self.assertEqual(result, "FAILED")
        self.assertEqual(calls, [])

    def test_forbidden_flags_still_enforced_in_github_mode(self):
        self.authorized_authors_path.write_text(
            json.dumps({"authorized_emails": ["trusted@example.com"]}), encoding="utf-8"
        )
        self.fixture.commit_task("READY", "0002", "trusted@example.com")
        original = set(task_worker.FORBIDDEN_FLAGS)
        task_worker.FORBIDDEN_FLAGS.add("-p")
        try:
            result = self._run_once(claude_exe_override=__file__)  # default launch_fn=launch_claude
        finally:
            task_worker.FORBIDDEN_FLAGS.clear()
            task_worker.FORBIDDEN_FLAGS.update(original)
        self.assertEqual(result, "FAILED")

    def test_no_secrets_in_status_or_log_github_mode(self):
        self.authorized_authors_path.write_text(
            json.dumps({"authorized_emails": ["trusted@example.com"]}), encoding="utf-8"
        )
        self.fixture.commit_task("READY", "0002", "trusted@example.com")
        self._run_once(launch_fn=lambda exe, cwd: _fake_completed(0), claude_exe_override=__file__)
        combined = self.status_path.read_text(encoding="utf-8") + self.log_path.read_text(encoding="utf-8")
        for marker in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "sk-"):
            self.assertNotIn(marker, combined)


class RunOnceGitHubModeSignatureTests(unittest.TestCase):
    """End-to-end proof that GitHub-sync authorization requires a valid,
    trusted commit signature - a matching author email alone (spoofable via
    `git -c user.email=...`, as _GitFixture.commit_task itself does) is
    never sufficient."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp_root = Path(self._tmp.name)
        self.fixture = _GitFixture(self.tmp_root)
        _write_valid_hooks_config(self.fixture.local_path)
        self.state_path = self.fixture.local_path / "state.json"
        self.status_path = self.fixture.local_path / "STATUS.md"
        self.log_path = self.fixture.local_path / "worker.log"
        self.authorized_authors_path = self.fixture.local_path / "authorized_authors.json"
        self.trusted_signers_path = self.fixture.local_path / "trusted_signers.json"
        # Both allowlists populated with the identity commit_task() uses -
        # the only variable under test is the signature itself.
        self.authorized_authors_path.write_text(
            json.dumps({"authorized_emails": ["trusted@example.com"]}), encoding="utf-8"
        )
        self.trusted_signers_path.write_text(
            json.dumps({"trusted_key_ids": [FAKE_TRUSTED_KEY_ID]}), encoding="utf-8"
        )

    def _run_once(self, **overrides):
        kwargs = dict(
            state_path=self.state_path,
            status_path=self.status_path,
            log_path=self.log_path,
            repo_root=self.fixture.local_path,
            github_remote="origin",
            github_branch="main",
            authorized_authors_path=self.authorized_authors_path,
            trusted_signers_path=self.trusted_signers_path,
            min_sync_interval=0,
            min_launch_interval=0,
        )
        kwargs.update(overrides)
        return task_worker.run_once(**kwargs)

    def test_real_unsigned_commit_from_authorized_email_does_not_launch(self):
        # _GitFixture.commit_task() creates a real, ordinary (unsigned)
        # commit with an explicit -c user.email - exactly the spoofing this
        # mechanism closes. No injected signature_fn here: this exercises
        # the real get_commit_signature_info() against a real git repo.
        self.fixture.commit_task("READY", "0002", "trusted@example.com")
        calls = []
        result = self._run_once(
            launch_fn=lambda exe, cwd: calls.append(1) or _fake_completed(0),
            claude_exe_override=__file__,
        )
        self.assertEqual(result, "PENDING_APPROVAL")
        self.assertEqual(calls, [], "a spoofable author email alone must never authorize a launch")
        self.assertIn("no valid commit signature", self.status_path.read_text(encoding="utf-8"))

    def test_valid_signature_from_untrusted_key_does_not_launch(self):
        self.fixture.commit_task("READY", "0002", "trusted@example.com")
        calls = []
        result = self._run_once(
            launch_fn=lambda exe, cwd: calls.append(1) or _fake_completed(0),
            claude_exe_override=__file__,
            signature_fn=_fake_signature_fn(status="G", key="0000000000000000"),
        )
        self.assertEqual(result, "PENDING_APPROVAL")
        self.assertEqual(calls, [])
        self.assertIn("not in trusted_signers.json", self.status_path.read_text(encoding="utf-8"))

    def test_bad_signature_from_trusted_key_does_not_launch(self):
        self.fixture.commit_task("READY", "0002", "trusted@example.com")
        calls = []
        result = self._run_once(
            launch_fn=lambda exe, cwd: calls.append(1) or _fake_completed(0),
            claude_exe_override=__file__,
            signature_fn=_fake_signature_fn(status="B"),
        )
        self.assertEqual(result, "PENDING_APPROVAL")
        self.assertEqual(calls, [])

    def test_valid_trusted_signature_from_untrusted_email_does_not_launch(self):
        self.fixture.commit_task("READY", "0002", "someone-else@example.com")
        calls = []
        result = self._run_once(
            launch_fn=lambda exe, cwd: calls.append(1) or _fake_completed(0),
            claude_exe_override=__file__,
            signature_fn=_fake_signature_fn(),  # valid, trusted key
        )
        self.assertEqual(result, "PENDING_APPROVAL")
        self.assertEqual(calls, [])

    def test_fully_verified_authorized_commit_launches_without_manual_approval(self):
        self.fixture.commit_task("READY", "0002", "trusted@example.com")
        calls = []
        result = self._run_once(
            launch_fn=lambda exe, cwd: calls.append(1) or _fake_completed(0),
            claude_exe_override=__file__,
            signature_fn=_fake_signature_fn(),  # valid signature, trusted key
            # approve_launch intentionally omitted - verified signature +
            # trusted key + authorized email must be sufficient on their own.
        )
        self.assertEqual(result, "WAITING_REVIEW")
        self.assertEqual(len(calls), 1)
        # STATUS.md is overwritten by the later WAITING_REVIEW write, so the
        # IN_PROGRESS-time authorization detail is only preserved in the log.
        self.assertIn("verified signature by trusted key", self.log_path.read_text(encoding="utf-8"))

    def test_unverified_commit_can_still_be_manually_approved(self):
        # The manual --approve-launch fallback must remain independent of
        # the signature mechanism entirely.
        self.fixture.commit_task("READY", "0002", "trusted@example.com")  # real, unsigned
        calls = []
        result = self._run_once(
            launch_fn=lambda exe, cwd: calls.append(1) or _fake_completed(0),
            claude_exe_override=__file__,
            approve_launch=True,
        )
        self.assertEqual(result, "WAITING_REVIEW")
        self.assertEqual(len(calls), 1)


class ResolveClaudeExecutableTests(unittest.TestCase):
    def test_override_missing_raises(self):
        with self.assertRaises(FileNotFoundError):
            task_worker.resolve_claude_executable(override="Z:/nope/claude.exe")

    def test_override_existing_returns_path(self):
        result = task_worker.resolve_claude_executable(override=__file__)
        self.assertEqual(result, Path(__file__))


class LaunchCommandSafetyTests(unittest.TestCase):
    def test_launch_command_never_contains_forbidden_flags(self):
        captured = {}
        real_run = subprocess.run

        def spy_run(command, **kwargs):
            captured["command"] = command
            return subprocess.CompletedProcess(args=command, returncode=0, stdout="{}", stderr="")

        subprocess.run = spy_run
        try:
            task_worker.launch_claude(Path(__file__), Path("."))
        finally:
            subprocess.run = real_run

        command = captured["command"]
        self.assertFalse(task_worker.FORBIDDEN_FLAGS & set(command))
        self.assertIn("-p", command)

    def test_launch_raises_if_a_forbidden_flag_is_present(self):
        # launch_claude()'s real command never includes a forbidden flag, so
        # to test the guard itself, force an intersection by temporarily
        # treating a flag that IS always in the command ("-p") as forbidden.
        # subprocess.run is never reached: the guard must raise first.
        original = set(task_worker.FORBIDDEN_FLAGS)
        task_worker.FORBIDDEN_FLAGS.add("-p")
        real_run = subprocess.run

        def spy_run(*args, **kwargs):
            raise AssertionError("subprocess.run must not be called when a forbidden flag is present")

        subprocess.run = spy_run
        try:
            with self.assertRaises(RuntimeError):
                task_worker.launch_claude(Path(__file__), Path("."))
        finally:
            subprocess.run = real_run
            task_worker.FORBIDDEN_FLAGS.clear()
            task_worker.FORBIDDEN_FLAGS.update(original)


if __name__ == "__main__":
    unittest.main()
