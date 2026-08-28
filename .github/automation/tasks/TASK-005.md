# TASK-005 — Build Next Video-Quality Milestone

## Objective

Continue the existing faceless YouTube automation project toward the cinematic motion-graphics output we are targeting.

## Instructions

1. Work only in the existing local checkout: `C:\YT-Automation`.
2. Sync with `origin/main` before starting.
3. Inspect the existing rendering/motion-graphics code before changing anything. Reuse the current architecture; do not rewrite working components unnecessarily.
4. Implement the next meaningful visual-quality milestone for the existing GPU/AI infrastructure story. Prioritize cinematic motion graphics, smooth transitions/easing, visual hierarchy, depth/parallax where practical, and clean typography over adding unnecessary features.
5. Use the existing assets/content where practical. Do not download random replacement assets unless required.
6. Keep the implementation deterministic and reproducible.
7. Render a short validation video/preview using the existing Python/FFmpeg pipeline.
8. Validate the rendered output with `ffprobe` and report resolution, FPS, duration, codec, and file size.
9. Do not publish to YouTube or any external platform.
10. Do not add secrets, credentials, API keys, or large generated binaries to Git.

## Git / handoff

- Commit and push the implementation and required source/config changes to `origin/main` after validation.
- Do not commit generated videos/audio, temp renders, `.venv`, caches, or local Claude settings; preserve the existing `.gitignore` behavior.
- Create `.github/automation/status/TASK-005.json` and include:
  - `task_id`
  - `status` (`IN_PROGRESS`, `COMPLETED`, or `FAILED`)
  - UTC `timestamp`
  - `summary`
  - `changed_files`
  - `validation`
  - `commit_sha`
  - `git_actions_performed`
  - `next_action`
- Commit and push the status file as part of the final handoff.

## Failure handling

If the existing pipeline is broken, fix only what is necessary for this milestone. If blocked by a missing dependency, permission, asset, or environment issue, stop rather than introducing a fragile workaround and report the exact blocker in the status file.

## Scope

This is a video-engineering task only. Do not build the task runner itself and do not work on YouTube publishing automation yet.
