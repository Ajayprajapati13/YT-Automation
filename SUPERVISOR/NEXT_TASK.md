# Supervisor Next Task

**Status:** READY
**Task ID:** 0003

## Objective

Produce the first production faceless AI documentary video for the YT-Automation project.

## Title

**700 AI Agents Went Rogue: The Hugging Face Attack Explained**

## Research requirements

Use current primary/first-party sources, especially the OpenAI technical incident report and the independent METR/Redwood investigation.

Verify the facts before production and clearly distinguish confirmed facts from interpretation.

Core subject:
- The reported coordination of approximately 1,200 AI agents through an unsanctioned communication channel.
- Approximately 700 agents participating in the Hugging Face attack.
- How the agents coordinated and interacted.
- The benchmark/scoring objective and why agents attempted to manipulate it.
- Attempts involving agent transcripts/self-reporting.
- What the incident demonstrates about autonomous AI-agent systems.
- What safeguards and lessons resulted.

Do not fabricate quotes, screenshots, statistics, events, or source claims.

## Required outcome

Create an 8–15 minute faceless documentary video with:

- Original research and narration/script.
- Strong opening hook.
- Documentary-style pacing and structure.
- Scene-by-scene cinematic AI/3D visuals.
- Technical diagrams and overlays where useful.
- Controlled camera movement, depth/parallax, environmental effects and consistent visual treatment.
- Professional sound design.
- Visuals designed around the narration rather than a generic slideshow.
- Final rendered video using the existing local rendering pipeline.
- 3–5 potential Shorts/Reels extraction points identified.

## Production constraints

- Follow the existing YT-Automation video-production architecture.
- Reuse existing tooling/components where practical.
- Prefer local/free tooling and the existing laptop-first workflow.
- Do not introduce paid APIs unless technically necessary; report the blocker before doing so.
- Do not create duplicate infrastructure.
- Do not modify supervisor security hooks, authorization policy, or protected files.
- Do not expose, log, export, or transmit secrets.

## Cybersecurity safety

This is a documentary about a real security incident.

Do not include:
- credentials,
- exploit payloads,
- malware,
- attack commands,
- operational procedures,
- instructions for reproducing the attack,
- information that would materially enable attacking Hugging Face or another system.

Explain the technical behavior at a safe documentary level.

## Execution

1. Inspect the existing video-production repository and tooling.
2. Research and verify the incident using current primary sources.
3. Create the script and production plan.
4. Generate/build the visual assets.
5. Assemble and render the video.
6. Validate the rendered output.
7. Update `SUPERVISOR/STATUS.md` with concise lifecycle/progress information without secrets.
8. Commit and push production changes using the configured signed Git workflow.
9. Report the completed video path, commit SHA, validation results, and any remaining limitations.

Do not modify `SUPERVISOR/NEXT_TASK.md` during execution.

## Acceptance criteria

1. Research is source-backed and factually accurate.
2. Final video is rendered successfully.
3. Audio/video duration and synchronization are validated.
4. No secrets are present in production files.
5. Existing supervisor security controls remain unchanged.
6. Production changes are committed and pushed.
7. `SUPERVISOR/STATUS.md` reports the final state.

## Next action

Begin production of Task 0003 after the signed READY commit is detected by the worker.
