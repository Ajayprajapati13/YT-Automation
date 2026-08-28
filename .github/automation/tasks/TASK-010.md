# TASK-010 — Lock Visual System + Production Architecture

## Objective

Lock the channel's production visual direction based on TASK-009 and prepare the reusable architecture for the full GPU explainer. Do not render the full 2–3 minute video yet.

## Locked visual direction

Use this as the default channel style:

- White/near-white background for clarity.
- Existing fictional presenter is the canonical character; do not redesign it.
- Blue/teal technical visual language.
- Character-led storytelling rather than slide-like presentation.
- Cinematic composition, purposeful camera movement, object-level animation, connected transitions, and restrained effects.
- Narration drives scene timing.

## Cinematic character direction

Where existing clean poses allow it, stage the presenter with deliberate cinematic body language:

- confident hook/introduction
- pointing toward the active technical element
- open-hand explaining gesture
- thoughtful/reaction pose
- emphasis/reaction pose
- clean closing pose

Use scale, placement, camera framing, and interaction with diagrams to make poses feel intentional. Do not invent or fake human poses with primitive drawing. If additional poses are needed later, identify them as asset requirements.

## Production architecture

Using the existing TASK-009 implementation, define a reusable scene structure that can support the complete video:

1. Scene metadata/story beat
2. Narration segment
3. Character pose/placement
4. Background/stage
5. Diagram/technical visual layers
6. Object animations/data flows
7. Camera actions
8. Transition
9. Timing/validation metadata

Prefer data-driven scene definitions over hard-coding every future scene.

## Required work

1. Sync with `origin/main`.
2. Inspect TASK-009 implementation and identify reusable components already present.
3. Refactor only where it materially improves reuse/maintainability.
4. Create or update a compact production-scene schema/configuration suitable for the full GPU story.
5. Document the visual rules and scene contract in the repository.
6. Convert the existing 60-second proof's beats into the reusable scene representation where practical.
7. Preserve the current output quality; do not regress the TASK-009 proof.
8. Run a short regression render, preferably 15–30 seconds, rather than another full 60-second render unless required by validation.
9. Validate the regression MP4 with ffprobe and inspect representative frames.

## Explicit non-goals

- Do not render the full 2–3 minute production video.
- Do not publish to YouTube.
- Do not redesign the character.
- Do not generate approximate human character artwork.
- Do not introduce unnecessary dependencies.
- Do not commit generated media.
- Do not modify unrelated project files.

## Acceptance criteria

The architecture must make it straightforward to add the remaining full-video scenes without duplicating rendering logic.

Regression proof must retain:

- 1920x1080
- 30 FPS
- H.264/yuv420p
- AAC audio
- white background
- canonical character
- readable diagrams
- intentional character placement
- cinematic object-level motion
- no accidental character clipping or pose bleed

## Git authorization

After successful implementation and validation, commit and push only source/config/documentation changes and `.github/automation/status/TASK-010.json`.

Do not commit MP4/WAV, temporary renders, caches, virtual environments, secrets, or local Claude settings.

If blocked, stop and report the smallest viable next action in the status file.

## Status handoff

Create `.github/automation/status/TASK-010.json` with:

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

After implementation, regression validation, visual inspection, and status push, stop. Await the next task before building the full video.
