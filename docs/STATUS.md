loop_signal: STOP_HUMAN
current_stage: prototype
last_task: P-07
last_verify: passed (P-07 acceptance: 3 tests and 21-run demo; verify: 56 tests, 57 deselected)
blockers: none
human_gates_pending: P-08

# STATUS (overwrite each iteration; keep the first six lines in this exact key: value form)
- Prototype mode: scope is docs/PROTOTYPE.md, queue is docs/TASKS.md. Ghidra is skipped.
- Next: P-08 is a human-owned, spend-approved real-LLM run; set the provider spend cap and choose the provider before continuing.
- Environment: use the project-local Python 3.11 `.venv`. The Codex seatbelt rejects nested `sandbox-exec`; P-02 uses the task-authorized direct fallback only for that exact denial and records the limitation in proposed D-017.
