# TASK-011 — Full Production Video Build

## Objective

Build the first full-length production video using the locked visual system established through TASK-010.

## Locked visual system — do not deviate

- White/near-white background
- Canonical fictional presenter from `assets/character/character_reference_sheet.png`
- Clean cinematic character staging and expressive available poses
- Blue/teal technical visual language
- Character actively interacts with diagrams
- Object-level animation
- Purposeful camera movement
- Cinematic but restrained transitions
- Narration-driven timing
- Professional technical-explainer composition

Do NOT revert to the dark TASK-005 style or the light/no-character TASK-006 style.

## Production target

Create the complete GPU/AI explainer based on the existing project story/content assets.

Target duration: approximately 2–3 minutes. Do not pad duration artificially; let the approved script/story determine the final runtime.

The complete video should have a coherent narrative rather than simply concatenating the previous 60-second proof.

## Story structure

Use the existing story/content files as the source of truth. Organize the full video into reusable Scene entries using `src/scene_engine.py`.

Each scene should define, as appropriate:

1. metadata
2. narration segment
3. character placement/pose
4. background/stage
5. diagram layer
6. object animation
7. camera behavior
8. transition
9. timing/validation expectations

Recommended narrative progression:

1. Hook — why AI needs so many GPUs
2. CPU vs GPU parallelism
3. What is inside a GPU
4. Parallel computation / thousands of operations
5. GPU memory and data movement
6. How AI workloads use GPU compute
7. Scaling to multiple GPUs
8. Why training/inference can require large GPU clusters
9. Presenter-led conclusion/takeaway

Adjust the exact scene count/order to the existing content/story files rather than inventing unrelated claims.

## Narration architecture

Close the TASK-010 architectural gap: narration must be associated with scene/beat segments rather than relying on one undifferentiated narration blob.

Use the existing TTS/voice-generation infrastructure where practical. Avoid unnecessary new dependencies or paid APIs.

Synchronize major visual events to narration beats.

## Character requirements

Use the existing canonical character identity.

Character should behave as the presenter, not as a decorative sticker:

- enter/exit intentionally where useful
- point or gesture toward the active concept when a clean available pose supports it
- use thoughtful/explanatory poses at appropriate beats
- maintain consistent scale/proportions
- avoid accidental cropping
- avoid adjacent-pose bleed
- avoid placing the character over labels or critical diagrams

Do not invent poor-quality human poses with primitive drawing. If a required pose cannot be produced cleanly from the approved assets, use the closest clean existing pose and preserve visual quality.

## Cinematic requirements

The full video should feel like a premium technology explainer, not an animated PowerPoint.

Use purposeful:

- camera pushes/pans/zooms
- staggered diagram construction
- GPU/core/data-flow animation
- controlled particles/data streams where useful
- visual cause-and-effect transitions
- depth/parallax where it genuinely improves clarity
- character-to-diagram interaction

Avoid:

- excessive glow
- random motion
- static slide-like holds
- oversized empty areas
- unnecessary decorative effects
- transition effects that dominate the content

### Transition requirement

The TASK-010 regression review identified the diagonal transition sweep as potentially too dominant. Keep it subtle: reduced width/opacity/duration or replace it with a cleaner transition if appropriate. The transition must never compete with the narration, character, title, or diagram.

## Rendering and performance

Use the existing rendering architecture.

Do not rewrite the engine from scratch.

Prefer deterministic scene rendering and reusable helpers.

Avoid generating unnecessary intermediate media.

Keep generated video/audio/temp artifacts out of Git.

## Validation

Render the complete production video and validate the actual final muxed MP4.

Required:

- 1920x1080
- 30 FPS
- H.264
- yuv420p
- AAC audio
- no unintended silent audio gaps
- audio/video duration alignment
- no clipping in audio

Perform representative-frame inspection across the entire timeline, including scene boundaries.

Check specifically for:

- character cropping
- pose bleed
- character consistency
- label/diagram overlap
- transition artifacts
- excessive empty space
- readability at 1080p
- camera framing
- animation continuity
- narration/visual synchronization
- accidental duplicate characters
- visual continuity between scenes

## Git rules

Do not commit generated MP4/WAV or temporary render artifacts.

Do not commit secrets, credentials, `.venv`, caches, `.claude/settings.local.json`, or unrelated files.

Commit only source/content/config/documentation changes required for TASK-011 and the status JSON.

## Publishing gate

**Do NOT publish to YouTube.**

The output is a production candidate for user review only.

No upload, scheduling, title/description publishing, thumbnail publishing, or public release is authorized by this task.

## Status handoff

Create:

`.github/automation/status/TASK-011.json`

Include:

- `task_id`
- `status`
- `timestamp`
- `summary`
- `changed_files`
- `output_file`
- `validation`
- `commit_sha`
- `git_actions_performed`
- `next_action`

If implementation is blocked by a genuine prerequisite, stop and report the blocker instead of fabricating an implementation.

## Stop condition

After the complete production candidate has been rendered, validated, visually inspected, and the status handoff has been committed and pushed, STOP.

Do not publish to YouTube.
Do not begin a second production video.
Do not perform unrelated cleanup.
