# TASK-006 — White Background + Audio Visual Quality Proof

## Objective

Create the next short visual-quality proof for the GPU/AI infrastructure motion-graphics video, using the existing motion-graphics engine and preserving the work completed in TASK-005.

The primary visual requirement for this milestone is a **clean white or near-white background** for improved viewing clarity and presentation. This milestone must also include **narration audio synchronized to the proof video**.

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
9. Add a concise narration track appropriate to the demonstrated GPU/AI infrastructure story. Reuse the existing voice-generation pipeline where practical; do not introduce a new TTS provider or API dependency for this milestone.
10. Synchronize the narration to the visual proof. The final MP4 should contain both video and an audio stream, with no unintended silence, clipping, or obvious timing mismatch.
11. Keep generated audio/video/temporary render artifacts under the existing ignored `output/` and `temp/` locations. Do not commit generated media.
12. Validate the generated MP4 with `ffprobe` for:
   - H.264 video
   - 1920x1080
   - 30 FPS
   - expected duration
   - yuv420p pixel format
   - AAC audio stream (or the codec produced by the existing supported pipeline if AAC is not currently available)
   - audio duration approximately matching video duration
13. Visually inspect representative frames from the render to confirm:
   - white/light background is actually present
   - text is readable
   - diagrams/nodes have clear contrast
   - motion remains smooth
   - no major clipping, overlap, or washed-out effects
14. Perform an audio sanity check using the available local tools (for example `ffprobe` stream metadata and, if practical, a short loudness/peak check). Report the result rather than assuming audio quality.
15. Do not publish to YouTube.
16. Do not commit generated video/audio files.
17. Do not modify unrelated files.

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

The status must explicitly report:

- final video duration
- video/audio codecs
- video resolution/FPS/pixel format
- audio presence and duration
- validation result
- generated output path

## Stop condition

After pushing the implementation and status, stop. Do not begin TASK-007 or the full-length render automatically.

The result will be reviewed before the next milestone is created.
