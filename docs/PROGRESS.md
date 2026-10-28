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

## 2026-10-28 iter 2 — P-01 — plan
- plan: add toolchain-marked corpus build tests first, then implement the offline Mach-O arm64 builder that compiles all seven protected sources, records `_target` address and size before stripping, strips and ad-hoc signs each binary, and writes truth-free agent task JSON.
- files to touch: `tests/corpus/`, `src/egre/corpus/build.py`, generated `corpus/bin/` and `corpus/tasks/`, then `docs/TASKS.md`, `docs/STATUS.md`, and this append-only log after verification.
- test-first outline: `python -m egre.corpus.build && python -m pytest tests/corpus -m toolchain -q` must establish seven signed arm64 Mach-O executables, compare every native result with the independent protected `corpus/reference_vectors.json` oracle for each offline truth primitive, and reject truth-bearing keys in every agent-visible task; then `./scripts/verify.sh` must pass.

## 2026-10-28 iter 2 — P-01 — done
- changed: added `src/egre/corpus/build.py`, `tests/corpus/test_build.py`, seven generated truth-free `corpus/tasks/*.json` files, and seven gitignored generated `corpus/bin/*` executables; updated only the P-01 task status and loop records.
- acceptance: `python -m egre.corpus.build && python -m pytest tests/corpus -m toolchain -q` -> pass (3 tests: exactly seven stripped, ad-hoc-signed arm64 Mach-O executables; all 49 program/vector outputs matched the independent oracle; task schemas contained no truth fields).
- verify: `./scripts/verify.sh` -> pass (ruff clean, mypy clean across 14 source files, 13 tests passed and 3 toolchain tests deselected).
- review: no tests were deleted, skipped, loosened, or made circular (`tests/corpus/test_build.py:25`, `tests/corpus/test_build.py:44`, `tests/corpus/test_build.py:64`); expected outputs come from protected `corpus/reference_vectors.json`, not builder output (`tests/corpus/test_build.py:12`, `tests/corpus/test_build.py:55`); no LLM, verdict, ledger, runtime-boundary, dependency, novelty-claim, or scope changes were introduced; `./scripts/check_protected.sh` passed. The fresh review added the explicit stripped-symbol assertion at `tests/corpus/test_build.py:37`.
- notes / surprises / follow-ups: the first verifier run found import ordering and the second found LIEF's union return type; both were corrected, and the third attempt plus the post-review rerun passed. `_target` sizes are derived before stripping from the next symbol boundary inside Mach-O `__text`; P-02 is now the first eligible task.
- stop signal: `CONTINUE`.
