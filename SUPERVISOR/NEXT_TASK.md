# Supervisor Next Task

**Status:** READY
**Task ID:** 0002

## Objective
Implement the minimum local ChatGPT-to-Claude task handoff worker so Claude Code can autonomously pick up repository tasks without requiring the user to copy/paste prompts into Claude for each task.

## Required outcome
- Add a small, maintainable local worker that watches `SUPERVISOR/NEXT_TASK.md` for a new `Status: READY` task.
- The worker must invoke the existing bundled Claude Code executable from the installed VS Code extension; do not install a second Claude runtime.
- The worker must run Claude in supported headless/programmatic mode and use the existing repository configuration and supervisor hooks.
- Prevent duplicate execution of the same Task ID.
- Track task state safely (`READY`, `IN_PROGRESS`, `WAITING_REVIEW`, `DONE`, `FAILED`) without bypassing supervisor controls.
- Write concise execution status to `SUPERVISOR/STATUS.md` without recording secrets.
- Keep polling/resource usage low; prefer local file-state checks and avoid unnecessary GitHub/API calls.
- Fail safely if Claude cannot be launched, the task file is malformed, or the worker encounters an unexpected error.
- Provide a simple way to start/stop the worker on Windows.
- Add non-destructive tests for task detection, duplicate prevention, malformed task handling, and graceful failure.

## Constraints
- Do not read, transmit, log, or commit secrets.
- Do not bypass, weaken, or modify the existing supervisor security policy merely to make the worker work.
- Do not deploy or publish anything.
- Do not automatically approve risky Claude operations.
- Do not create an Anthropic API integration unless the existing Claude Code subscription/runtime cannot support the required execution path and the limitation is explicitly reported first.
- Do not make broad unrelated changes.

## Acceptance criteria
1. A READY task can be detected locally and launched exactly once.
2. The bundled Claude Code executable is invoked using a configurable/validated path rather than a hardcoded assumption where practical.
3. Existing `.claude` hooks remain active and are not bypassed.
4. Duplicate polling does not launch the same Task ID repeatedly.
5. `SUPERVISOR/STATUS.md` records lifecycle state and concise errors without secrets.
6. Worker tests pass without modifying protected supervisor security files.
7. Startup/stop instructions are documented.
8. The implementation is small enough to maintain and uses no unnecessary paid service.

## Next action
Inspect the existing repository and Claude Code configuration first. Implement only the minimum worker needed for this handoff. Do not start video production in this task; video production begins after the worker is validated.
