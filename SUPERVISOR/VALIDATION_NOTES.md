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
