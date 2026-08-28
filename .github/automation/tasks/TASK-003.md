# TASK-003 — Local Git Bridge Verification

## Objective

Verify that the existing local `C:\YT-Automation` working directory is correctly connected to the GitHub repository and can participate in the ChatGPT → GitHub → Claude → GitHub workflow.

## Instructions

1. Work in the existing local project at `C:\YT-Automation`. Do not use an isolated clone.
2. Do not modify application source code.
3. Do not install packages.
4. Do not render or generate video/audio.
5. Do not stage, commit, or push any changes.
6. Inspect and report:
   - current branch
   - configured `origin` URL (redact credentials if present)
   - local HEAD SHA
   - whether local `main` tracks `origin/main`
   - whether the working tree is clean
   - whether `.github/automation/tasks/TASK-003.md` is visible from the local checkout
7. Create only this status file locally:
   `.github/automation/status/TASK-003.json`
8. The JSON must contain:
   - `task_id`: `TASK-003`
   - `status`: `COMPLETED`
   - `timestamp`
   - `branch`
   - `head_sha`
   - `remote`
   - `tracking`
   - `working_tree_clean`
   - `task_visible_locally`
   - `summary`
9. Do not commit or push the status file. Leave it as an uncommitted working-tree change.

## Success criteria

The local checkout is connected to `origin/main`, the task is visible locally, and the status JSON is created without modifying application code.

Stop after completing the status file and reporting the verification results.
