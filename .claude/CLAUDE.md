# Supervisor-controlled execution

Before doing substantive work, read:
- `SUPERVISOR/PROTOCOL.md`
- `SUPERVISOR/NEXT_TASK.md`
- `ARCHITECTURE.md` if present

Treat `SUPERVISOR/NEXT_TASK.md` as the current work contract. Do not ask the user to repeat routine task instructions. Work only within its objective and constraints.

Permission requests are reviewed by the local supervisor hook and, where permitted, by the OpenAI supervisor. Do not attempt to bypass, disable, edit, or weaken supervisor hooks, settings, or policy files.

After each meaningful change:
1. Validate the change.
2. Inspect the actual result, not just the intended result.
3. Fix safe issues found during validation.
4. Continue until the current task's completion criteria are satisfied.

If a supervisor hook rejects an action, do not retry the same action with a trivial variation. Use the feedback to choose a safer alternative. Escalate only when the alternative would materially change scope or risk.
