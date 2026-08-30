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

## Known gap
- `reviewer/API failure -> fail closed` could not be fault-injected safely from
  inside this session: doing so would require touching OPENAI_API_KEY / DPAPI
  secret state, which the hook itself explicitly told this session not to do.
  No test harness or documented dry-run procedure for this exists outside the
  protected `.claude/hooks/` files. This check needs either a manual test by the
  repo owner (e.g. temporarily pointing SUPERVISOR_MODEL/API base at an
  unreachable endpoint) or a code-level review of `run_supervisor.py` /
  `supervisor.py`, neither of which this session can perform under current
  permissions.
