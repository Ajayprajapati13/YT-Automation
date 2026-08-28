# TASK-007 — Character-Led GPU Explainer Proof

## Objective

Build the next visual-quality milestone as a polished character-led technical explainer using the existing GPU/AI motion-graphics pipeline.

The presenter should be a consistent fictional 3D/cartoon technical host, used as the on-screen speaker instead of a real person's face. Use the approved character concept from the latest storyboard reference: friendly young technical presenter, dark styled hair, expressive face, white hoodie with blue accents, clean professional presentation style.

## Creative direction

Create a coherent 45–60 second proof-of-quality for the GPU architecture topic.

The character is the recurring presenter/host. Do NOT attempt to reproduce or identify a real person. Treat the character as an original fictional brand asset.

Use a clean white or near-white background with a restrained professional blue/teal technical palette and strong contrast.

The character should appear in multiple useful presenter poses/states, such as:
- introducing the topic
- explaining a CPU vs GPU comparison
- pointing toward a GPU diagram
- explaining parallel processing
- concluding/key takeaway

Do not make the character static on every shot. Use purposeful entrances, exits, pose changes, scale changes, or camera movement where technically practical.

## Storyboard / sequence

Target sequence, approximately 5–8 seconds per beat:

1. INTRO — Character introduces GPU architecture.
2. WHAT IS A GPU? — Character + GPU visual/diagram.
3. CPU VS GPU — Sequential CPU blocks transition into massive GPU parallel blocks.
4. INSIDE THE GPU — Show compute cores, memory/controller, and data flow.
5. AI CONNECTION — Data → parallel GPU processing → AI model.
6. TAKEAWAY — Character delivers the core message with a clean closing composition.

Use narration synchronized to these beats. Reuse the existing narration/TTS pipeline where practical; do not introduce unnecessary dependencies.

## Visual quality requirements

1. Preserve the useful motion-graphics engine work from previous milestones.
2. White/light background must remain clear and consistent.
3. Use strong typography hierarchy and readable labels.
4. Use animated diagrams rather than static slides.
5. Use purposeful camera movement and transitions.
6. Add restrained glow/accent effects only where they improve focus.
7. Use depth/parallax where useful, without making the scene visually busy.
8. Character should integrate naturally with diagrams rather than simply being pasted beside them.
9. Maintain consistent character appearance across all shots.
10. Avoid excessive text; narration should carry the explanation.

## Audio requirements

- Include narration in the final MP4.
- Synchronize visual beats with narration timing.
- Validate that audio exists and duration aligns with video.
- Prefer a clean, intelligible voice suitable for a technical YouTube explainer.
- Do not publish to YouTube.

## Implementation constraints

1. Work in the existing local project at `C:\YT-Automation`.
2. Sync with `origin/main` before starting.
3. Reuse the existing rendering architecture where possible.
4. Do not rewrite the engine from scratch.
5. Do not install packages unless an actual missing prerequisite blocks the task; if blocked, stop and report it.
6. Do not modify unrelated files.
7. Generated media must remain ignored and must not be committed.
8. Do not commit secrets, credentials, API keys, or local Claude settings.

## Validation

Render a 45–60 second proof and validate with `ffprobe`:

- H.264 video
- 1920x1080
- 30 FPS
- yuv420p
- duration within target range
- AAC audio present
- audio/video durations reasonably aligned

Visually inspect representative frames from the rendered proof for:

- character consistency
- white/light background
- readable typography
- diagram contrast
- clean composition
- smooth transitions
- no clipping/overlap
- no excessive glow

If the character cannot be generated/used consistently with the existing local assets, do NOT fake consistency. Stop and report the blocker and propose the smallest viable asset-generation approach.

## Git authorization

After implementation and validation, commit and push only:

- source files actually changed for TASK-007
- required character asset metadata/configuration, if applicable
- `.github/automation/status/TASK-007.json`

Do not commit generated MP4/WAV files, temporary renders, caches, virtual environments, or credentials.

## Status handoff

Create:

`.github/automation/status/TASK-007.json`

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

After pushing the implementation and status, stop. Do not begin the full 2–3 minute video or YouTube publishing automatically.
