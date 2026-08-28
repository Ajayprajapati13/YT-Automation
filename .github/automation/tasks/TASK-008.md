# TASK-008 — Integrate Character Reference Asset

## Objective

Integrate the user-provided fictional presenter reference into the existing video pipeline and prepare the character-led proof for the next render.

## Required local asset

The user has placed the character reference image at:

`C:\YT-Automation\assets\character\character_reference_sheet.png`

Treat this file as the canonical character reference. Do not replace it, redraw it with Pillow, or generate an approximate human character.

## Instructions

1. Work in the existing local project at `C:\YT-Automation`.
2. Sync with `origin/main` before starting.
3. Verify the character reference exists, is readable, and record its dimensions/file type.
4. Inspect the reference sheet and determine the most useful pose(s) for compositing into the video.
5. Do not commit the reference sheet if it is not present in the local repository yet unless it is actually copied/added from the exact user-provided file.
6. If the sheet contains multiple poses in one image, do not pretend they are separate transparent production assets. Determine the smallest technically sound approach for using/cropping the appropriate character regions.
7. Reuse the existing Pillow/FFmpeg rendering architecture.
8. Do not install new packages unless a real prerequisite blocks the task.
9. Integrate the character into a short 45–60 second GPU explainer proof based on the TASK-007 storyboard.
10. Keep the white/near-white background and blue/teal technical palette.
11. Character should act as the visual presenter: introduce the topic, point/explain diagrams where practical, and appear in the conclusion.
12. Use existing narration/TTS pipeline and synchronize visual beats with narration.
13. Do not publish to YouTube.
14. Do not commit generated MP4/WAV or temporary render artifacts.
15. Do not modify unrelated files.

## Quality gate

The character integration must be honest about asset limitations. If the single reference sheet cannot provide sufficiently clean reusable poses without destructive/poor-quality extraction, stop and report the blocker rather than producing a visibly poor fake presenter.

## Validation

If implementation succeeds:

- Render a 45–60 second proof.
- Validate H.264, 1920x1080, 30 FPS, yuv420p.
- Validate AAC audio and reasonable A/V duration alignment.
- Visually inspect representative frames for character clarity, consistency, clean extraction, white background, diagram readability, and no obvious artifacts.

## Git authorization

After successful implementation and validation, commit and push only:

- source files actually changed for TASK-008
- the exact character reference asset if it is appropriate and legally/technically suitable for repository storage
- `.github/automation/status/TASK-008.json`

Never commit secrets, credentials, `.claude/settings.local.json`, `.venv`, caches, temporary renders, or generated media.

If blocked, do not commit implementation changes; commit only the TASK-008 status JSON describing the blocker and smallest viable next action.

## Status handoff

Create:

`.github/automation/status/TASK-008.json`

Include at minimum:

- `task_id`
- `status`
- `timestamp`
- `summary`
- `changed_files`
- `validation`
- `commit_sha`
- `git_actions_performed`
- `next_action`

## Stop condition

After implementation/validation and the status handoff, stop. Do not start the full 2–3 minute video and do not publish to YouTube.
