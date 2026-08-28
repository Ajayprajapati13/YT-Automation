# TASK-006 — White Background Visual Clarity Proof

## Objective

Create the next short visual-quality proof for the GPU/AI infrastructure motion-graphics video, using the existing motion-graphics engine and preserving the work completed in TASK-005.

The primary visual requirement for this milestone is a **clean white background** for improved viewing clarity and presentation.

## Requirements

1. Work in the existing local project at `C:\YT-Automation`.
2. Sync with `origin/main` before starting.
3. Reuse the existing motion-graphics engine. Do not rewrite it from scratch.
4. Change the visual treatment so the primary scene background is white or near-white, suitable for clear technical diagrams and typography.
5. Ensure foreground elements have sufficient contrast against the white background. Do not simply invert every existing color blindly; choose a coherent professional technical palette.
6. Preserve and use the useful TASK-005 improvements where appropriate:
   - animated camera movement
   - parallax/depth cues
   - node/diagram animation
   - restrained glow/accent effects
   - caption hierarchy
   - smooth easing/transitions
7. Avoid excessive glow or effects that reduce legibility on the light background.
8. Produce a **30–45 second proof-of-quality render**, not the full 2–3 minute video.
9. Validate the generated MP4 with `ffprobe` for:
   - H.264 video
   - 1920x1080
   - 30 FPS
   - expected duration
   - yuv420p pixel format
10. Visually inspect representative frames from the render to confirm:
   - white/light background is actually present
   - text is readable
   - diagrams/nodes have clear contrast
   - motion remains smooth
   - no major clipping, overlap, or washed-out effects
11. Do not publish to YouTube.
12. Do not commit generated video/audio files.
13. Do not modify unrelated files.

## Git authorization

After implementation and validation, commit and push **only the source files changed for TASK-006 and the TASK-006 status JSON**. Do not stage generated media, temporary files, `.venv`, caches, or credentials.

## Status handoff

Create:

`.github/automation/status/TASK-006.json`

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

After pushing the implementation and status, stop. Do not begin TASK-007 or the full-length render automatically.

The result will be reviewed before the next milestone is created.
