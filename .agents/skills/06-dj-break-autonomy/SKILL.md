---
name: dj-break-autonomy
description: Use when running unattended /goal or /teamwork autonomous loops during the 2-hour hackathon break.
---

<AUTONOMOUS_EXECUTION_PROTOCOL>
1. BRANCH ISOLATION: Immediately checkout `feat/dj-break-autonomy` before starting unattended loops.
2. TASK QUEUE LOOP: Read `TASKS.md`. Claim the highest-priority unchecked `[ ]` item.
3. ATOMIC VERIFICATION GATE: After coding each task, run `pytest -q --tb=short` (backend) and `tsc --noEmit` (frontend).
4. SELF-HEALING ROLLBACK:
   - If checks pass: mark `[x]` in `TASKS.md` and run `git add -A && git commit -m "feat(auto): complete task"`.
   - If checks fail after 3 fix attempts: run `git reset --hard HEAD`, log the blocker in `BLOCKERS.md`, and move to the next independent task in `TASKS.md`. Never leave the repo in a broken build state.
</AUTONOMOUS_EXECUTION_PROTOCOL>
