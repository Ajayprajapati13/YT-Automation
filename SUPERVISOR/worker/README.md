# Task handoff worker (Task 0002)

A small local worker that watches `SUPERVISOR/NEXT_TASK.md` for a `**Status:**
READY` task, tracks its lifecycle, and reports status - so the repository
owner doesn't have to paste "Read SUPERVISOR/NEXT_TASK.md and execute the
READY task" into Claude for every task by hand.

**A READY task is never, on its own, sufficient authorization to launch
anything.** There are exactly two ways a launch can be authorized, and
neither is on by default:

1. **`--approve-launch`** - an explicit, one-off manual override. Requires a
   human to act, every time.
2. **GitHub-sync mode** (`--github-remote`) - the task is read from
   `<remote>/<branch>` (never the local working-tree file) and is
   auto-authorized only if the commit that last touched `NEXT_TASK.md` there
   carries a **cryptographically valid signature from a key listed in
   `trusted_signers.json`, AND** an author email listed in
   `authorized_authors.json` - both explicit, human-maintained allowlists
   that ship empty. A matching author email alone is never enough: that's
   plain commit metadata, trivially spoofed via `git -c user.email=...`.
   This is what makes autonomous operation possible without per-task
   intervention, while still requiring a real, auditable, unforgeable
   authorization event (a specific signed commit, from a specific trusted
   key) rather than trusting an arbitrary local file or spoofable metadata.

With neither set, a READY task is reported as `PENDING_APPROVAL` and the
worker stops there.

## What it does and does not do

- In local mode (no `--github-remote`): polls `SUPERVISOR/NEXT_TASK.md` on a
  local file-state basis only - no git fetch, no GitHub/API calls, launches
  only with `--approve-launch`.
- In GitHub-sync mode (`--github-remote origin`, say): fetches the given
  remote/branch (rate-limited by `--sync-interval`, default 300s - between
  fetches it just re-reads the already-fetched remote-tracking ref locally,
  which is free), then reads `NEXT_TASK.md` and its authoring commit
  (`sync_remote_ref`) purely via local git plumbing (`git show`/`git log`
  against `<remote>/<branch>`) - **never** a working-tree checkout, merge, or
  reset, so uncommitted local changes are never at risk, and a local edit to
  the working-tree `NEXT_TASK.md` has zero effect (see the design section
  below).
- Detects a READY task exactly once per Task ID (tracked in `state.json`,
  local to this machine, not committed), in both modes.
- **Never launches Claude without authorization** - explicit approval or a
  verified GitHub commit. Without either, a READY task is reported as
  `PENDING_APPROVAL` and nothing else happens - no executable resolution, no
  rate-limit consumption, no launch.
- When authorized, launches the same `claude.exe` native binary the VS Code
  extension itself uses, via `-p`/`--print` (headless mode), in the
  repository's working directory - so `.claude/settings.json`, its hooks, and
  `CLAUDE.md` all load and run exactly as they do in an interactive session.
- Verifies `.claude/settings.json` exists, parses, and declares `PreToolUse`
  and `Stop` hooks immediately before every launch (`verify_hooks_configured`)
  - refuses to launch (`FAILED`) rather than assume the hooks that make this
    safe are actually in place.
- Verifies its own on-disk content against a committed hash
  (`integrity.json`, see below) before every run - refuses to run at all on
  code that doesn't match the last human-reviewed baseline.
- Never passes `--dangerously-skip-permissions`, `--permission-mode
  bypassPermissions`, `--restricted`, `--bare`, or `--safe-mode`. Those either
  bypass the permission system or disable project hooks; using any of them
  here would defeat the point of the supervisor control loop. `launch_claude`
  raises `RuntimeError` (not `assert`, which `-O`/`PYTHONOPTIMIZE=1` would
  strip) if `FORBIDDEN_FLAGS` ever intersects the command it's about to run.
- Bounds launch frequency: at most one launch per `--min-launch-interval`
  seconds (default 300), regardless of how many distinct Task IDs appear -
  this is separate from per-ID dedup and specifically bounds unattended
  execution if new Task IDs appear in quick succession.
- Never reads, logs, or transmits secrets (API keys, tokens, passwords). It
  doesn't touch API keys at all - the launched CLI reuses whatever login/auth
  the user already has configured for Claude Code. In GitHub-sync mode,
  commit author emails/names are logged deliberately, for audit purposes -
  that's public git metadata already visible to anyone with read access to
  the repo, not a secret.
- Never writes `**Status:** DONE` (or any other value) into
  `SUPERVISOR/NEXT_TASK.md`. That file is owned by the ChatGPT supervisor /
  repository owner (also enforced separately by `.claude/settings.json`
  permission denials on Claude's own Edit/Write tools). The worker only marks
  its own lifecycle as far as `WAITING_REVIEW` once the launched session
  exits; a human or the ChatGPT supervisor confirms completion out of band,
  the same way Task 0001 was closed out.

## Lifecycle states (`SUPERVISOR/STATUS.md`)

| State | Meaning |
|---|---|
| `PENDING_APPROVAL` | A READY task was detected but isn't authorized to launch - no `--approve-launch`, and (in GitHub-sync mode) either no authorized commit or GitHub-sync mode isn't enabled at all. This is the default outcome for any READY task. |
| `SYNC_FAILED` | GitHub-sync mode only: `git fetch`/`git show`/`git log` against `<remote>/<branch>` failed (unreachable remote, missing file, malformed content, etc). Nothing is launched. |
| `RATE_LIMITED` | Authorized, but a launch happened too recently (`--min-launch-interval`); will be retried on a later poll. |
| `IN_PROGRESS` | Authorized, rate limit and hook verification passed, and Claude was just launched for it. The status detail records *how* it was authorized (manual, or which commit/author). |
| `WAITING_REVIEW` | The launched Claude session exited cleanly (exit code 0); awaiting human/ChatGPT review before the task is marked DONE. |
| `DONE` | Reflects `NEXT_TASK.md` once a human/ChatGPT has set `**Status:** DONE` there. The worker only mirrors this - it never sets it. |
| `FAILED` | The task file was malformed, hooks couldn't be verified, `claude.exe` could not be resolved, the launch raised an exception, or the process exited non-zero. Concise, secret-free detail is included. |
| `IDLE` | (not written to STATUS.md) No READY task is currently pending. |

## Running it

```powershell
# Dry run: detect/track/report only, never launches (the default - safe to
# leave running unattended):
python SUPERVISOR\worker\task_worker.py --once
python SUPERVISOR\worker\task_worker.py --interval 60

# Explicitly approve launching Claude for whatever READY task is detected
# right now, regardless of GitHub authorization:
python SUPERVISOR\worker\task_worker.py --once --approve-launch

# GitHub-sync mode: autonomous, but only for commits from an email in
# authorized_authors.json. Safe to leave running continuously/unattended -
# an unauthorized commit is reported as PENDING_APPROVAL, not launched.
python SUPERVISOR\worker\task_worker.py --github-remote origin --github-branch main --interval 60
```

`start_worker.ps1` runs local dry-run mode by default (no flags passed). Edit
it (or invoke `task_worker.py` directly, as above) if you want it to start in
GitHub-sync mode instead. It's idempotent (a no-op if the tracked PID is
already running) and prefers the repo's `.venv\Scripts\python.exe` if
present. `stop_worker.ps1` only ever stops the one PID it tracked itself.

## GitHub-sync mode and commit-provenance authorization

This is the mechanism that lets the worker run unattended without you having
to approve every single task, while still refusing to launch anything just
because a local file (or an unsigned commit's plain-text metadata) happens to
say READY.

**Why not just trust the commit author email?** Because author-email commit
metadata is trivially spoofed - `git -c user.email=anyone@example.com commit`
sets it to whatever the committer wants, with no verification at all (this
repo's own test suite does exactly that to build fixtures). Trusting it alone
would mean anyone able to push a commit could impersonate a trusted identity.
So author email is necessary but never sufficient - it's checked *together
with* a cryptographic signature from an explicitly trusted key:

1. `sync_remote_ref()` fetches `<remote>/<branch>` (rate-limited) and reads
   `NEXT_TASK.md` from it via `git show` - never the working tree. It also
   gets the **commit SHA, author email, author name, and commit date** of
   whoever last touched that file there (`git log`).
2. `get_commit_signature_info()` reads that same commit's GPG/SSH signature
   status via `git log --format=%G?/%GK/%GS` - local git plumbing against
   the already-fetched commit object, no network. This reflects whatever
   public keys are already imported into this machine's own GPG keyring.
3. `is_commit_authorized()` requires **all three** of:
   - a cryptographically valid signature (`%G?` is `G` or `U` - the
     signature math checks out; `N`/unsigned, `B`/bad, `X`/`Y`/expired,
     `R`/revoked, or `E`/unverifiable are all rejected)
   - the signing key id (`%GK`) is listed in `trusted_signers.json`
   - the author email is listed in `authorized_authors.json`

   **Both allowlist files ship empty** - nothing is auto-trusted until a
   human deliberately populates them. Find the values for a given commit
   with:
   ```powershell
   git log -1 --format=%ae -- SUPERVISOR/NEXT_TASK.md   # author email
   git log -1 --format=%GK -- SUPERVISOR/NEXT_TASK.md   # signing key id (once signed)
   ```
4. Only if all three hold does the task auto-launch - and the commit SHA +
   signing key + author + this reasoning are written into `STATUS.md`/the
   log for every launch, so every autonomous launch has a specific,
   auditable justification, not just "a file said READY" or "the metadata
   claimed to be someone trusted."
5. An unauthorized (or unsigned, or wrongly-signed) commit doesn't crash or
   silently do nothing - it's reported as `PENDING_APPROVAL` with the
   specific reason (no signature / untrusted key / untrusted email), and
   `--approve-launch` still works as a manual override on top of it,
   entirely independent of the signature mechanism, if you want to approve
   that specific case anyway.

**What this does not change:** dedup by Task ID, the launch-rate limiter,
`verify_hooks_configured()`, and `FORBIDDEN_FLAGS` all still apply
identically in GitHub-sync mode - authorization only decides *whether* a
launch is allowed to be attempted, not whether the existing safety checks
still run.

**Populating the allowlists:**

```json
// authorized_authors.json
{
  "authorized_emails": ["ci-bot@example.com"]
}

// trusted_signers.json
{
  "trusted_key_ids": ["ABCDEF0123456789"]
}
```

Whatever identity actually authors the commits you want auto-trusted (a
ChatGPT/automation integration's commit email and its signing key, or your
own) goes here - and for signature verification to succeed at all, that
key's **public** key needs to already be imported into this machine's GPG
keyring (`gpg --import`). Neither file is protected by
`.claude/settings.json`'s deny-list, so treat adding an entry to either as a
real security decision, reviewed like any other change before it's
committed.

## Integrity baseline (`integrity.json`)

Before doing anything else, the worker hashes its own `task_worker.py` and
compares it against `integrity.json` (sha256, committed alongside the code).
If the file is missing, unreadable, or the hash doesn't match, the worker
refuses to run at all (`FAILED`, exit code 2) - including mid-loop, checked
before every iteration, not just at startup.

This is **tamper-evidence, not tamper-proofing**: `integrity.json` isn't
protected by `.claude/settings.json`'s permission deny-list the way
`SUPERVISOR/NEXT_TASK.md` and `.claude/hooks/**` are, so anyone who can write
`task_worker.py` can generally also update `integrity.json` to match. It
catches accidental/incidental drift (e.g. a task editing files under
`SUPERVISOR/` without realizing what it's touching), not a determined
adversary. The durable fix - adding `SUPERVISOR/worker/**` to that deny-list
- requires a human/repository-owner edit to `.claude/settings.json`; Claude's
own Edit/Write on that file is itself denied, so this worker cannot make that
change for itself.

```powershell
# Only after a human has read and reviewed the current task_worker.py:
python SUPERVISOR\worker\task_worker.py --update-integrity
```

## Configuring the Claude executable path

By default the worker auto-discovers the newest
`anthropic.claude-code-*-win32-x64` VS Code extension under
`%USERPROFILE%\.vscode\extensions\` and uses its
`resources\native-binary\claude.exe`. To override:

```powershell
# One-off override:
python SUPERVISOR\worker\task_worker.py --claude-exe "C:\path\to\claude.exe"

# Persistent override (e.g. if the CLI is installed standalone instead of
# via the VS Code extension):
$env:CLAUDE_CLI_PATH = "C:\path\to\claude.exe"
```

If neither is set and no matching extension is found, the worker fails safely
(`FAILED` state, concise reason in `STATUS.md`/`logs\task_worker.log`) - it
never falls back to installing a second Claude runtime or calling the
Anthropic API directly.

## Recovering from a crash mid-task

`state.json` records `last_task_id`/`last_state` locally (not committed - see
`.gitignore`). If the worker process itself is killed while a launch is in
flight, `state.json` can be left showing `IN_PROGRESS` for a task that isn't
actually running anymore. This is intentionally not auto-retried (to avoid a
second concurrent launch racing an unknown surviving process) - confirm no
`claude.exe` process from this repo is still running, then delete
`state.json` to let the worker pick the task up again.

## Tests

```powershell
python SUPERVISOR\worker\test_task_worker.py -v
```

Standard library `unittest` only (no pytest dependency added). Every test
runs against temporary files and an injected fake launcher - no test ever
spawns a real Claude Code process. GitHub-sync tests use a local bare git
repo as a stand-in for GitHub (plain filesystem paths, `git init --bare`) -
no test ever performs real network access.
