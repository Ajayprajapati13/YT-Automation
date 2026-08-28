# TASK-009 — Cinematic Character-Led Explainer Polish

## Objective

Improve the existing TASK-008 character-led GPU proof from a technically correct prototype into a more polished, cinematic YouTube technology-explainer style.

Do NOT change the established fictional presenter design. Do NOT generate or approximate a new human character.

## Source of truth

Use the canonical character asset:

`assets/character/character_reference_sheet.png`

Preserve the existing white/near-white visual identity and restrained blue/teal technical palette.

## Problems to fix from TASK-008 review

1. Prevent accidental character cropping at scene boundaries.
2. Remove visible fragments/bleed from adjacent poses in the reference sheet extraction.
3. Avoid compositions where the character and diagram look like unrelated objects placed on a slide.
4. Reduce large unused areas of the canvas.
5. Make the presenter visually interact with the diagrams.
6. Replace static-looking title/slide behavior with animated visual storytelling.
7. Make camera movement intentional rather than merely shifting the whole canvas.
8. Make scene transitions visually connect concepts.

## Creative direction

Target a premium technology-explainer feel rather than an animated PowerPoint.

Use this interaction pattern where practical:

character introduces concept
→ relevant diagram enters/assembles
→ character points/explains
→ diagram animates in response
→ camera follows the important element
→ concept transitions into the next visual

The character should feel like the presenter guiding the viewer through the explanation.

## 60-second proof sequence

Create a new 55–65 second proof around:

1. HOOK — "Why does AI need so many GPUs?"
   - Character enters intentionally.
   - Title animates in rather than appearing as a static header.
   - Establish the question visually.

2. CPU VS GPU
   - CPU's few cores build/appear sequentially.
   - GPU's many parallel cores assemble/multiply.
   - Character points or gestures toward the GPU side.
   - Camera gives emphasis to the comparison.

3. PARALLEL PROCESSING
   - Data particles/lines visibly flow into multiple GPU cores.
   - Multiple operations happen in parallel.
   - Character explains the concept without blocking the diagram.

4. GPU + AI
   - Data flows through GPU compute/memory toward an AI model.
   - Use a visually connected pipeline rather than separate boxes appearing independently.
   - Character reacts/points to the active part of the pipeline.

5. SCALE
   - Visually communicate why modern AI workloads require many GPUs.
   - Use controlled multiplication/expansion of GPU resources rather than a static number.

6. TAKEAWAY
   - Character returns in a clean closing composition.
   - One concise takeaway statement.
   - Clean finish suitable for extending into a longer video.

## Character requirements

- Keep the existing character exactly as the brand identity.
- Use only cleanly extracted usable poses.
- No accidental clipping of head, hands, arms, or body.
- No adjacent-pose fragments.
- Maintain consistent apparent scale/proportions.
- Character should occupy intentional visual positions.
- Character must not cover important diagram labels.
- Do not apply excessive glow to character pixels.

If the current reference sheet cannot produce a clean pose required by a shot, reuse an existing clean pose or stop and report the limitation. Do not fabricate a replacement human character.

## Visual requirements

- 1920x1080, 30 FPS.
- White or near-white background.
- Strong contrast and readable typography.
- Minimal but purposeful grid/depth elements.
- Animated diagrams and data flows.
- Object-level motion, not only whole-frame motion.
- Intentional camera pushes/pans/scale changes.
- Smooth transitions between concepts.
- Restrained glow/accent effects.
- No large unexplained empty regions.
- Avoid excessive text.

## Audio

- Reuse the existing narration/TTS pipeline.
- Keep narration synchronized with visual events.
- Narration should drive scene timing.
- Include AAC audio in final MP4.
- Validate audio level and A/V duration alignment.

## Implementation constraints

1. Work in `C:\YT-Automation`.
2. Sync with `origin/main` before starting.
3. Reuse existing rendering architecture.
4. Do not rewrite the engine from scratch.
5. Do not install packages unless a real missing prerequisite blocks the task.
6. Do not modify unrelated files.
7. Generated media stays ignored and must not be committed.
8. Do not publish to YouTube.
9. Do not start the full 2–3 minute production render.

## Validation

Render a 55–65 second proof and validate with ffprobe:

- H.264
- 1920x1080
- 30 FPS
- yuv420p
- duration within target range
- AAC audio
- reasonable/exact A/V duration alignment

Perform representative-frame inspection from the actual muxed MP4. Specifically check:

- no character clipping
- no pose bleed/fragments
- character consistency
- intentional presenter placement
- diagram interaction
- title animation
- object-level animation
- camera movement
- scene transitions
- white background clarity
- typography readability
- diagram contrast
- no excessive empty space
- no excessive glow
- no clipping/overlap

## Git authorization

After successful implementation and validation, commit and push only:

- source files actually changed for TASK-009
- required character metadata/configuration if applicable
- `.github/automation/status/TASK-009.json`

Do not commit MP4/WAV files, temporary renders, caches, virtual environments, credentials, or local Claude settings.

If blocked, do not commit implementation changes; commit only the status JSON describing the blocker and smallest viable next action.

## Status handoff

Create:

`.github/automation/status/TASK-009.json`

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

After implementation, validation, visual inspection, and status push, stop.

Do not begin the full 2–3 minute video.
Do not publish to YouTube.
