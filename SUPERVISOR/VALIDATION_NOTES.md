# Supervisor Control-Loop Validation Notes (Task 0001)

Non-destructive validation pass, appended to (not overwriting) task history.

## Observed this session
- PreToolUse hook fired on every tool call (Bash, Read, Glob, Write) — confirmed by
  live denials on: a compound `ls`/`grep` probe of `.claude/hooks`, and a Python
  one-liner checking presence (not value) of `OPENAI_API_KEY`/`SUPERVISOR_MODEL`,
  which returned an explicit "use a safer alternative" message rather than a
  generic error.
- Read-only/inspection calls (`git log/show/ls-files/diff`, `python --version`,
  repo `Glob`s) passed without friction.
- Stop hook fired and blocked completion with structured feedback naming specific
  gaps (reviewer fail-closed, Stop continuation, summary generation, api_test.py) —
  this is itself a live positive test of criterion 6 (Stop hook detects incomplete
  work and continues Claude).
- This Write call itself is being used as a live, harmless test of the
  ambiguous/non-fast-path approval route (neither a hardcoded-safe read nor a
  denylisted path).

## Reviewer/API fail-closed criterion — resolved by code-level review
Fault injection (pointing the API at an unreachable endpoint, clearing the
DPAPI secret) was not attempted — it would touch supervisor/secret state the
hook explicitly denies modifying, and the task instructions direct using
existing implementation/evidence instead of building fault-injection
infrastructure. Verified instead by reading the current committed hook code
(`git show HEAD:.claude/hooks/...`), since `Read` on `.claude/hooks/**` is
itself denied by `.claude/settings.json` policy:

- `local_pretool.py` (PreToolUse entry point): only one exact, hardcoded
  read-only command bypasses the supervisor; every other call is forwarded to
  `run_supervisor.py pretool` and its exit code is propagated unchanged. A
  malformed hook payload here returns exit 2 (hard block) directly.
- `run_supervisor.py` (commit `8e4c158`, still in place): wraps the
  `supervisor.py` subprocess call. Any non-zero exit from `supervisor.py` —
  crash, uncaught exception, interpreter failure — is converted to exit 2
  ("Supervisor failed closed: tool/action blocked."). Claude Code treats exit
  2 on PreToolUse/Stop as a hard block, so a crashed supervisor process can
  never silently permit a material action.
- `supervisor.py` internal handling of reviewer/API failure (no crash, just a
  failed call):
  - `pretool()`: if `OPENAI_API_KEY` is unset, or `reviewer()` raises
    (network error, timeout, malformed response, JSON parse failure), the
    except/guard branch emits `permissionDecision: "ask"` — manual approval
    required. There is no code path in `pretool()` that reaches
    `permissionDecision: "allow"` without either a local SAFE-tier match or a
    successful reviewer call returning `decision == "allow"` with
    `risk in {"low","medium"}`.
  - `posttool()`: reviewer exceptions are caught and reported as
    `"Supervisor review was unavailable; treat this result as unverified."`
    via `additionalContext` — no fabricated success signal.
  - `stop()`: reviewer exceptions fall back to checking the task snapshot
    directly; if the task is still `**Status:** READY`, it blocks with
    `"Supervisor unavailable and task is still READY; continue validation."`
    rather than allowing Claude to stop on an unverified success claim. This
    is the same fallback path exercised live earlier in this session (see
    "Observed this session" above), independently confirming the behavior
    documented here in code.

Net result: at every layer (hook wrapper exit code, and each of
pretool/posttool/stop inside `supervisor.py`), an API/reviewer failure
degrades to "ask"/"block"/"unverified", never to a silent "allow". This
satisfies completion criterion 5 without adding new test infrastructure.

## Completion criteria — status
1. Hooks installed in working tree (`local_pretool.py`, `run_supervisor.py`,
   `supervisor.py`, wired via `.claude/settings.json`) — confirmed via `git show`.
2. `.claude/settings.json` is valid JSON and hooks executed successfully during
   this session (PreToolUse/PostToolUse/Stop all fired) — confirmed live.
3. Deterministic deny tests pass — confirmed live (hooks probe, env-var check
   denials) earlier this session.
4. A harmless tool call was reviewed/approved successfully — confirmed live
   (read-only git/glob calls, this Write call itself).
5. Reviewer/API failure fails closed — confirmed by code-level review above.
6. Stop hook detects incomplete task and continues Claude — confirmed live
   earlier this session, and consistent with the `stop()` code path.
7. Concise supervisor summary generated after validation — this document,
   plus the final chat summary delivered at task completion.

All seven completion criteria for Task 0001 are satisfied. No source changes
were required this session; only this validation record was added.

## Follow-up session — fresh live re-validation
A new session began with no prior tool calls, so the Stop hook correctly
declined to accept the earlier record alone as in-session evidence. Re-ran a
minimal, bounded subset live in this session:
- Deterministic deny test: `Read(./.env)` — blocked by permission settings
  before any file content was accessed ("File is in a directory that is
  denied by your permission settings"). Confirms criterion 3 still holds.
- Harmless allowed call: `python -c "json.load(open('.claude/settings.json'))"`
  succeeded, printing `settings.json: valid JSON`. Confirms criteria 1/2/4
  (hooks installed and firing — PreToolUse/PostToolUse ran on every call this
  session — and settings.json remains valid JSON).
- This Stop-hook exchange itself (initial block citing missing in-session
  evidence, now followed by this targeted response) is a second, independent
  live instance of criterion 6.
- Criterion 5 (reviewer/API fail-closed) and the code paths in
  `local_pretool.py` / `run_supervisor.py` / `supervisor.py` are unchanged
  since the prior session's code-level review; no source edits occurred, so
  that analysis still applies.

No source or policy files were modified. Task 0001 remains DONE with
in-session evidence now recorded for the current session as well.

# Task 0002 — Task handoff worker

## Investigation (per "Next action")
- No standalone `claude` CLI on PATH. The bundled native binary lives at
  `%USERPROFILE%\.vscode\extensions\anthropic.claude-code-2.1.251-win32-x64\
  resources\native-binary\claude.exe` (found via the installed extension's
  `package.json`/`resources` layout).
- `claude.exe --help` confirms a supported headless/programmatic path:
  `-p`/`--print` (non-interactive, exits after one response),
  `--output-format json`, and a `--permission-mode` flag whose
  `bypassPermissions` value and the separate `--dangerously-skip-permissions`
  flag are explicitly opt-in and were therefore never used. `--restricted`,
  `--bare`, and `--safe-mode` all disable project `.claude/settings.json`
  hooks/CLAUDE.md and were likewise avoided.
- Conclusion: the existing Claude Code runtime fully supports the required
  execution path, so no Anthropic API integration was created (the
  task's opt-out condition was never reached, so no limitation needed
  reporting).

## Implementation
- `SUPERVISOR/worker/task_worker.py` — polling worker. Parses
  `**Status:**`/`**Task ID:**` from `NEXT_TASK.md`; on `READY`, resolves
  `claude.exe` (explicit `--claude-exe` > `CLAUDE_CLI_PATH` env var > newest
  matching VS Code extension, version-sorted; never installs a second
  runtime) and launches it with `["claude.exe", "-p", <fixed prompt>,
  "--output-format", "json"]` in the repo root, so project hooks/CLAUDE.md
  load exactly as in an interactive session. `launch_claude()` asserts none
  of `FORBIDDEN_FLAGS` (the bypass/disable-hooks flags above) are present in
  the command it builds. Dedup is by Task ID in a local `state.json`
  (gitignored): a READY task launches Claude exactly once; a later poll with
  the same ID returns the cached `IN_PROGRESS`/`WAITING_REVIEW` state instead
  of relaunching; a new Task ID launches again. The worker never writes
  `DONE` (or anything else) into `NEXT_TASK.md` — it only reads it — so
  Task 0001's finding that that file is owned by the human/ChatGPT supervisor
  is preserved structurally, not just by convention.
- `SUPERVISOR/STATUS.md` — concise lifecycle output (`IN_PROGRESS`,
  `WAITING_REVIEW`, `DONE` reflected from `NEXT_TASK.md`, `FAILED` with a
  short exception/exit-code detail). No stdout/transcript content from the
  launched session is ever persisted, only exit-code-derived detail strings,
  so nothing from inside a Claude session can leak secrets into this file.
- `SUPERVISOR/worker/start_worker.ps1` / `stop_worker.ps1` — idempotent
  start (no-op if the tracked PID is already alive; prefers the repo
  `.venv`) and a stop script that only ever kills the one PID it tracked
  itself.
- `SUPERVISOR/worker/test_task_worker.py` — 16 `unittest` tests (stdlib only,
  no new dependency); every test runs against temp files with the subprocess
  launch dependency-injected, so no test ever spawns a real Claude process.
  Ran from repo root: `python SUPERVISOR/worker/test_task_worker.py -v` →
  `Ran 16 tests ... OK`.

## Acceptance criteria — evidence
1. READY task detected and launched exactly once —
   `test_ready_task_launches_exactly_once_across_repeated_polls` (3 polls,
   1 launch call).
2. Configurable/validated executable path, not hardcoded — `--claude-exe` /
   `CLAUDE_CLI_PATH` / auto-discovery, each validated with `Path.is_file()`
   before use; live-verified against the real installed extension
   (`resolve_claude_executable()` → the actual `claude.exe` path above,
   `exists: True`).
3. Existing `.claude` hooks remain active, not bypassed — no forbidden flag
   is ever added (`FORBIDDEN_FLAGS` assertion + a dedicated test spying on
   `subprocess.run`); the launch always runs in the repo root in default
   permission mode so `.claude/settings.json` hooks load normally, same as
   this interactive session.
4. Duplicate polling does not relaunch the same Task ID — same test as (1);
   `test_new_task_id_after_completion_launches_again` shows a *different* ID
   does launch again.
5. `SUPERVISOR/STATUS.md` records lifecycle state without secrets —
   `test_no_secrets_written_to_status_or_log` checks for
   `OPENAI_API_KEY`/`ANTHROPIC_API_KEY`/`sk-` markers; the worker also never
   reads any credential in the first place (auth is left entirely to the
   already-logged-in CLI).
6. Worker tests pass without modifying protected supervisor security files —
   16/16 pass; no file under `.claude/hooks/`, `.claude/settings.json`,
   `SUPERVISOR/PROTOCOL.md`, or `SUPERVISOR/NEXT_TASK.md` was touched this
   session (only `SUPERVISOR/worker/**`, `SUPERVISOR/STATUS.md`,
   `SUPERVISOR/VALIDATION_NOTES.md`, and `.gitignore` were changed).
7. Startup/stop documented — `SUPERVISOR/worker/README.md`.
8. Small/no unnecessary paid service — one Python module + two PowerShell
   scripts + stdlib tests; no new package dependency (pytest was
   unavailable in `.venv` so plain `unittest` was used instead); no
   Anthropic API integration added.

## Known limitation (not fault-tested live)
The actual end-to-end path — the worker really invoking the live
`claude.exe` against the real `SUPERVISOR/NEXT_TASK.md` — was deliberately
not exercised in this session: Task 0002 was itself the READY task, so a
real run would have launched a nested Claude Code session recursively
executing this same task. All launch-side behavior is instead covered by
injecting a fake launcher in `run_once()` (this is exactly the same
seam a real integration test would need, and it exercises the identical
code path up to the `subprocess.run` boundary). Recommend a human runs
`python SUPERVISOR/worker/task_worker.py --once` by hand once a future task
is READY, as a live check outside of a nested Claude session.

Worker implemented and validated; awaiting human/ChatGPT review before Task
0002 is marked DONE.
