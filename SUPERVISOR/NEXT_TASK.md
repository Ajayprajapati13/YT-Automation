# Supervisor Next Task

**Status:** READY
**Task ID:** 0001

## Objective
Implement and validate the Claude Code AI-supervisor control loop described in `SUPERVISOR/PROTOCOL.md`.

## Required outcome
- Claude Code reads this file automatically at session start and when it is ready to stop.
- Low-risk tool calls can be auto-approved after deterministic local checks and OpenAI review.
- Dangerous or sensitive operations are blocked locally.
- Ambiguous/high-impact operations remain human approval requests.
- Post-tool results are reviewed and corrective feedback is returned to Claude when needed.
- The Stop hook checks this task and prevents Claude from stopping while the task remains incomplete.

## Constraints
- Do not read, transmit, or commit secrets.
- Do not use administrator/root privileges.
- Do not deploy or publish anything.
- Do not modify the supervisor security files except as explicitly required by this task.
- Validate with harmless/read-only tests before any real automation work.

## Completion criteria
1. Supervisor hooks are installed in the working tree.
2. Settings are valid JSON and hooks execute successfully.
3. Deterministic deny tests pass.
4. A harmless tool call can be reviewed successfully.
5. Reviewer failure falls back to manual approval/stop rather than auto-allow.
6. A Stop hook can detect this task and continue Claude when work remains.
7. A concise supervisor summary is generated after validation.

## Next action
Inspect the repository and existing Claude Code configuration first. Do not make broad unrelated changes. Report any prerequisite or security issue before implementing it.
