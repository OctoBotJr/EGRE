loop_signal: STOP_HUMAN
current_stage: prototype
last_task: P-00
last_verify: passed (13 tests; smoke passed)
blockers: project directory is not a standalone Git checkout; Git root resolves to /Users/sanjeevprasanna, so commit and loop.sh are unsafe
human_gates_pending: restore or initialize the intended project Git repository; P-08

# STATUS (overwrite each iteration; keep the first six lines in this exact key: value form)
- Prototype mode: scope is docs/PROTOTYPE.md, queue is docs/TASKS.md. Ghidra is skipped.
- Next: restore or initialize the intended project Git repository, commit P-00, then run P-01 Corpus build.
- Environment: use the project-local Python 3.11 `.venv`; native Unicorn smoke must run outside the Codex seatbelt because that seatbelt denies `hw.cachelinesize`, causing Unicorn's macOS fallback to trap on `CTR_EL0`.
