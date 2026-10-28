# PROGRESS (append-only log; newest at bottom)

Entry format:
## <ISO date> iter <n> — <task id> — <done|blocked|partial>
- plan: ...
- changed: files
- acceptance: <command> -> <pass/fail + one-line summary>
- verify: <pass/fail>
- notes / surprises / follow-ups: ...

## 2026-10-28 iter 1 — P-00 — plan
- plan: create the project-local Python virtual environment, install the development dependencies, then run `./scripts/verify.sh`, `./scripts/check_env.sh`, and `./scripts/smoke_env.sh`; record any native macOS arm64 or optional-tool limitation without starting P-01.
- files to touch: `.venv/` (gitignored), `docs/PROGRESS.md`, `docs/STATUS.md`, and `docs/TASKS.md` only after all P-00 acceptance checks pass.
- test-first outline: use the existing verifier and environment/smoke scripts as the acceptance checks; do not modify tests or protected files.

## 2026-10-28 iter 1 — P-00 — done
- changed: created a gitignored Python 3.11 `.venv` with `.[dev,re]`; updated only `docs/PROGRESS.md`, `docs/STATUS.md`, and the P-00 status in `docs/TASKS.md`.
- acceptance: `source .venv/bin/activate && ./scripts/verify.sh` -> pass (ruff clean, mypy clean, 13 tests passed); `./scripts/check_env.sh` -> pass with no required `MISSING` entries (Ghidra and angr warnings are optional); `./scripts/smoke_env.sh` -> pass with `SMOKE PASSED` when run as a native macOS process outside the Codex seatbelt.
- verify: pass.
- review: no test, runtime, claim, verdict, ledger, dependency declaration, protected file, or research claim was changed; P-00 only created the local environment and updated loop state.
- notes / surprises / follow-ups: inside the Codex seatbelt, Unicorn 2.1.4 receives a denial for the read-only `hw.cachelinesize` sysctl and falls back to `mrs ctr_el0`, which macOS terminates with SIGILL. The identical Unicorn check passes natively outside that outer seatbelt. The prototype's own `sandbox-exec` no-network check still ran and blocked network successfully. Ghidra remains intentionally skipped.
- stop signal: `STOP_HUMAN` after P-00 because `git rev-parse --show-toplevel` resolves to `/Users/sanjeevprasanna`, not this project. The project is untracked in that home-level repository, so the requested commit and `scripts/loop.sh` cannot be run safely until the intended project repository is restored or explicitly initialized.
