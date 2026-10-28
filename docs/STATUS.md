loop_signal: CONTINUE
current_stage: prototype
last_task: P-01
last_verify: passed (P-01 acceptance: 3 toolchain tests; verify: 13 tests, 3 deselected)
blockers: none
human_gates_pending: P-08

# STATUS (overwrite each iteration; keep the first six lines in this exact key: value form)
- Prototype mode: scope is docs/PROTOTYPE.md, queue is docs/TASKS.md. Ghidra is skipped.
- Next: run P-02 References, executor, runner verdicts.
- Environment: use the project-local Python 3.11 `.venv`; native Unicorn smoke must run outside the Codex seatbelt because that seatbelt denies `hw.cachelinesize`, causing Unicorn's macOS fallback to trap on `CTR_EL0`.
