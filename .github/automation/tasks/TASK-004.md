# TASK-004 — Establish the Claude Task/Status Workflow

## Objective

Turn the current GitHub task/status mechanism into a reliable operating workflow for future ChatGPT → GitHub → Claude → GitHub execution.

## Next steps

1. Work only in the existing local checkout:
   `C:\YT-Automation`

2. Synchronize the local checkout with `origin/main` before processing tasks.

3. Configure the local `main` branch to track `origin/main` using the non-destructive upstream configuration.

4. Inspect the existing `.github/automation/` structure and recommend a minimal, maintainable task/status convention.

5. Define a predictable task lifecycle:
   `PENDING → IN_PROGRESS → COMPLETED | FAILED`

6. Define the minimum status JSON fields needed for ChatGPT to evaluate Claude's work, including task ID, status, timestamp, summary, changed files, validation results, and commit SHA where applicable.

7. Recommend how Claude should identify the next pending task without executing multiple tasks unintentionally.

8. Recommend safeguards so Claude never performs a commit, push, destructive Git operation, credential operation, or production/publishing action unless the task explicitly authorizes it.

9. Do not modify application code.
10. Do not render or generate video/audio.
11. Do not publish to YouTube.
12. Do not make destructive Git changes.

## Required output

Create only this local report:

`.github/automation/status/TASK-004.json`

The report must contain:

- `task_id`
- `status`
- `timestamp`
- `summary`
- `current_branch`
- `upstream`
- `working_tree_clean`
- `recommendations`
- `next_action`

Commit and push ONLY the TASK-004 status file after completing the analysis so ChatGPT can read the result from GitHub.

## Success criteria

ChatGPT can read TASK-004's status from GitHub and use its `next_action` as the basis for the next task.
