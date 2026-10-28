# Playbook: implement a task
1. Re-read the task's acceptance line and the docs it names. State the acceptance test in your plan.
2. Write or extend tests first (tests/<component>/). Tests must fail for the right reason before code.
3. Implement the minimum that passes. Keep modules small; typed (pydantic/mypy-clean).
4. Respect invariants I1–I6 (docs/ARCHITECTURE.md). Runtime code never imports corpus/evaluation.
5. Run acceptance, then ./scripts/verify.sh. Max 3 attempts, then mark blocked.
6. Definition of done: acceptance passes, verify passes, PROGRESS/STATUS/TASKS updated, no protected file touched.
