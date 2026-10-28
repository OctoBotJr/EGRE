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

## 2026-10-28 iter 3 — P-02 — plan
- plan: add runner tests first, then implement independent primitive references, native program execution under a no-network `sandbox-exec` profile with timeout and strict output parsing, and deterministic claim verification over the protected reference-vector inputs.
- files to touch: `tests/runner/`, `src/egre/runner/refs.py`, `src/egre/runner/executor.py`, `src/egre/runner/verify.py`, then `docs/TASKS.md`, `docs/STATUS.md`, and this append-only log after verification.
- test-first outline: `python -m pytest tests/runner -m toolchain -q` must confirm each of the seven binaries' true primitive, refute every wrong known primitive, map a bad binary path to `inconclusive` rather than `refuted`, and prove the executor's sandbox blocks a network attempt; then `./scripts/verify.sh` must pass.

## 2026-10-28 iter 3 — P-02 — done
- changed: added deterministic primitive references and fixed experiment inputs in `src/egre/runner/refs.py`, strict native execution with timeout and the required no-network profile in `src/egre/runner/executor.py`, fail-closed typed verdicts in `src/egre/runner/verify.py`, and 13 toolchain tests in `tests/runner/test_runner.py`; proposed D-017 for the documented nested-seatbelt fallback and updated only P-02/loop state.
- acceptance: `python -m pytest tests/runner -m toolchain -q` -> pass (13 tests: independent vectors; all seven true primitives confirmed and all 21 wrong known primitives refuted; bad path, unknown primitive, and a late mixed harness failure inconclusive; network probe blocked; malformed I/O rejected).
- verify: `./scripts/verify.sh` -> pass (ruff clean, mypy clean across 17 source files, 13 tests passed and 16 toolchain tests deselected).
- review: no test was deleted, skipped, loosened, or made circular; reference functions are checked against protected independent vectors (`tests/runner/test_runner.py:21`) and binary verdicts against protected truth (`tests/runner/test_runner.py:39`). No LLM output participates; every `ExecError`, including one after mismatches, wins as `inconclusive` (`src/egre/runner/verify.py:29`, `tests/runner/test_runner.py:64`). Runtime imports remain inside runner, scope is limited to P-02, no dependency or novelty claim was added, and `./scripts/check_protected.sh` passed. The fresh review tightened exact output framing and added the mixed-failure I3 regression.
- notes / surprises / follow-ups: the first acceptance run found that the outer Codex seatbelt rejects nested `sandbox-exec` with status 71. The task-authorized fallback now triggers only for that exact denial (`src/egre/runner/executor.py:39`); proposed D-017 records that the outer seatbelt, not this wrapper, supplies network isolation in that environment. Initial verifier passes found only import ordering and a mypy name collision; both were corrected before the final acceptance/verifier sequence. P-03 is now the first eligible task.
- stop signal: `CONTINUE`.

## 2026-10-28 iter 4 — P-03 — plan
- plan: add ledger and mediator toolchain tests first, then implement immutable append-only observations, ARM64 `mov`/`movk` constant reconstruction, and validated disassemble/read-memory/run tools that alone write ledger records and expose compact handle-bearing views.
- files to touch: `tests/ledger/`, `tests/mediator/`, `src/egre/ledger/store.py`, `src/egre/ledger/constants.py`, `src/egre/mediator/tools.py`, package exports only if needed, then `docs/TASKS.md`, `docs/STATUS.md`, and this append-only log after verification.
- test-first outline: `python -m pytest tests/ledger tests/mediator -m toolchain -q` must prove the required clean/obfuscated/decoy signature-constant behavior, `mov`/`movk` reconstruction, immutable agent-facing read access with unknown handles rejected, and validated mediator calls recorded with correct anchors/facts; then `./scripts/verify.sh` must pass.

## 2026-10-28 iter 4 — P-03 — done
- changed: added immutable append-only observations and a read-only ledger capability in `src/egre/ledger/store.py`, ARM64 immediate and `mov`/`movk` reconstruction in `src/egre/ledger/constants.py`, validated Capstone/LIEF-backed disassemble/read-memory/run tools in `src/egre/mediator/tools.py`, and 11 toolchain tests across `tests/ledger/` and `tests/mediator/`; updated only P-03 and loop state.
- acceptance: `python -m pytest tests/ledger tests/mediator -m toolchain -q` -> pass (11 tests: required CRC/FNV/DJB2 clean, obfuscated, and decoy facts; split-constant reconstruction and clobber handling; immutable read-only ledger; unknown-handle rejection; validated and recorded mediator calls).
- verify: `./scripts/verify.sh` -> pass (ruff clean, mypy clean across 20 source files, 13 tests passed and 27 toolchain tests deselected).
- review: no test was deleted, skipped, loosened, or made circular; the corpus assertions use fixed expected constants and independent reference functions (`tests/mediator/test_tools.py:19`, `tests/mediator/test_tools.py:48`). No LLM output, claim verdict, truth oracle, or harness-failure classification was introduced. Observations and argument maps are immutable, the agent-facing reader has no write method, and unknown handles fail closed (`src/egre/ledger/store.py:32`, `src/egre/ledger/store.py:46`, `src/egre/ledger/store.py:95`, `tests/ledger/test_ledger.py:55`). Runtime imports stay within ledger/mediator/runner boundaries (`src/egre/mediator/tools.py:14`), scope and dependencies are unchanged, no novelty claim was added, and `./scripts/check_protected.sh` passed. The fresh review added a regression preventing split constants from being joined across a register clobber (`tests/ledger/test_ledger.py:43`).
- notes / surprises / follow-ups: the initial red test run failed only because the three P-03 modules did not yet exist; the first implemented acceptance/verifier sequence passed, as did the post-review sequence. Capstone handled all required constants, so the radare2 fallback was not needed. P-04 is now the first eligible task.
- stop signal: `CONTINUE`.

## 2026-10-28 iter 5 — P-04 — plan
- plan: add claims and T2 contract tests first, then implement a validated typed T2 claim, a registry capped at three claims, and a deterministic support checker for signature-bearing static observations or two matching distinct non-empty runs.
- files to touch: `tests/claims/`, `tests/contracts/`, `src/egre/claims/schema.py`, `src/egre/contracts/t2.py`, package exports only if needed, then `docs/TASKS.md`, `docs/STATUS.md`, and this append-only log after verification.
- test-first outline: `python -m pytest tests/claims tests/contracts -q` must cover rules (a) and (b), all four reason codes, unknown handles, anchor bounds, distinct non-empty run inputs, and clean/decoy-style constant cases; then `./scripts/verify.sh` must pass.

## 2026-10-28 iter 5 — P-04 — done
- changed: added the strict immutable T2 `Claim` model and three-claim ordered `Registry` in `src/egre/claims/schema.py`, deterministic signature/run support rules and typed reason codes in `src/egre/contracts/t2.py`, and 25 hand-built tests across `tests/claims/` and `tests/contracts/`; updated only P-04 and loop state.
- acceptance: `python -m pytest tests/claims tests/contracts -q` -> pass (25 tests: claim/registry validation; both support rules; all four reason codes; clean, unrelated, and decoy constants; anchor containment; distinct non-empty run inputs and fixed expected outputs).
- verify: `./scripts/verify.sh` -> pass (ruff clean, mypy clean across 22 source files, 38 tests passed and 27 toolchain tests deselected).
- review: no test was deleted, skipped, loosened, or changed to accommodate implementation; the new rule-(a) cases use fixed signature constants and rule-(b) cases use hand-built output values rather than the checker's reference implementation (`tests/contracts/test_t2.py:47`, `tests/contracts/test_t2.py:78`). No LLM, truth oracle, verdict, or harness-failure classification was introduced. Unknown handles fail closed (`src/egre/contracts/t2.py:87`), the checker receives only a read-only ledger capability, and runtime imports contain no corpus/evaluation dependency. Changes are limited to P-04 with no new dependency or novelty claim; `git diff --check` and `./scripts/check_protected.sh` passed. The fresh review removed circular test data and added regressions for uppercase hex and byte-distinct run inputs (`tests/contracts/test_t2.py:95`).
- notes / surprises / follow-ups: the initial red run failed only because the P-04 modules did not yet exist; the initial implementation passed acceptance and verification, and the strengthened post-review suite and verifier also passed. P-05 is now the first eligible task.
- stop signal: `CONTINUE`.

## 2026-10-28 iter 6 — P-05 — plan
- plan: add controller and report tests first, then implement deterministic status derivation for every support/verdict combination and JSON/Markdown rendering whose claims can only come from the registry plus computed statuses.
- files to touch: `tests/controller/`, `tests/report/`, `src/egre/controller/status.py`, `src/egre/report/render.py`, package exports only if needed, then `docs/TASKS.md`, `docs/STATUS.md`, and this append-only log after verification.
- test-first outline: `python -m pytest tests/controller tests/report -q` must cover the full support x verdict table, require `support_gap=True` only for confirmed claims with insufficient support, and prove report claims exactly equal registry claims in JSON and Markdown; then `./scripts/verify.sh` must pass.

## 2026-10-28 iter 6 — P-05 — done
- changed: added deterministic support-by-verdict status derivation in `src/egre/controller/status.py`, strict registry-only JSON and Markdown rendering in `src/egre/report/render.py`, and 13 tests across `tests/controller/` and `tests/report/`; updated only P-05 and loop state.
- acceptance: `python -m pytest tests/controller tests/report -q` -> pass (13 tests: all six support x verdict combinations, verified support-gap behavior, exact JSON claim equality, registry-ordered Markdown, and rejection of missing or invented status IDs).
- verify: `./scripts/verify.sh` -> pass (ruff clean, mypy clean across 24 source files, 51 tests passed and 27 toolchain tests deselected).
- review: no test was deleted, skipped, loosened, or made circular; expected status values are a fixed specification table (`tests/controller/test_status.py:8`), and report claims are compared directly with registry model dumps (`tests/report/test_render.py:21`). No LLM, truth oracle, executor outcome, ledger write, or harness-failure classification was introduced. Status derivation is deterministic (`src/egre/controller/status.py:26`), report rows originate only from registry iteration with exact status-ID matching (`src/egre/report/render.py:12`), and runtime imports contain no corpus/evaluation dependency. Changes are limited to P-05 with no new dependency or novelty claim; `git diff --check` and `./scripts/check_protected.sh` passed.
- notes / surprises / follow-ups: the initial red run failed only because the two P-05 modules did not yet exist; the first implementation passed acceptance and verification, and the fresh review required no follow-up changes. P-06 is now the first eligible task.
- stop signal: `CONTINUE`.

## 2026-10-28 iter 7 — P-06 — plan
- plan: add agent/LLM tests first, then implement a bounded JSON tool-call loop, deterministic fake responses and P1–P3 scripted policies, plus an import-safe real OpenAI adapter that reads credentials only when called.
- files to touch: `tests/agent/`, `tests/llm/`, `src/egre/agent/loop.py`, `src/egre/agent/policies.py`, `src/egre/llm/base.py`, `src/egre/llm/fake.py`, `src/egre/llm/openai.py`, package exports only if needed, then `docs/TASKS.md`, `docs/STATUS.md`, and this append-only log after verification.
- test-first outline: `python -m pytest tests/agent tests/llm -m toolchain -q` must run P1–P3 through the real mediator/ledger on all seven programs, prove the generic loop validates JSON and stops within 12 steps, make no network calls, and establish that the real adapter imports and constructs without an API key; then `./scripts/verify.sh` must pass.

## 2026-10-28 iter 7 — P-06 — done
- changed: added the provider-neutral LLM protocol, replay fake, lazy import-safe OpenAI adapter, bounded allowlisted JSON action loop, deterministic P1 grepper/P2 emulator/P3 prior-guesser policies, and 27 toolchain acceptance tests across all seven programs; updated only P-06 and loop state.
- acceptance: `python -m pytest tests/agent tests/llm -m toolchain -q` -> pass (27 tests: all 21 policy/program runs through the real mediator and ledger; JSON validation, 12-step bound, unknown-handle rejection, replay behavior, and network-free adapter construction/transport checks).
- verify: `./scripts/verify.sh` -> pass (ruff clean, mypy clean across 29 source files, 55 tests passed and 54 toolchain tests deselected).
- review: no test was deleted, skipped, loosened, or made circular; policy claims are checked against fixed expected maps independent of policy output (`tests/agent/test_policies.py:21`, `tests/agent/test_policies.py:30`, `tests/agent/test_policies.py:57`, `tests/agent/test_policies.py:67`). LLM output only selects validated tool/claim actions and never produces support, verdict, status, or truth (`src/egre/agent/loop.py:105`, `src/egre/agent/loop.py:123`); unissued handles fail closed (`src/egre/agent/loop.py:129`, `tests/agent/test_loop.py:47`), and only mediator calls can append observations. Runtime imports contain no corpus/evaluation dependency, the provider SDK is lazy and credentials are resolved only at call time (`src/egre/llm/openai.py:17`, `src/egre/llm/openai.py:48`), no dependency or novelty claim was added, and `git diff --check` plus `./scripts/check_protected.sh` passed. The fresh review added the direct unknown-handle regression.
- notes / surprises / follow-ups: the initial red run failed only because the P-06 modules did not yet exist. Acceptance then passed; the first standard verifier attempt found import ordering and exception-type lint only, which were corrected. The final acceptance/verifier sequence passed. P-07 is now the first eligible task.
- stop signal: `CONTINUE`.

## 2026-10-28 iter 8 — P-07 — plan
- plan: add evaluation acceptance tests first, then implement the deterministic support-by-truth matrix, C1/C2/C3 precision-and-coverage views, evaluation JSON/CLI output, and an end-to-end scripted demo over all seven programs.
- files to touch: `tests/evaluation/`, `src/egre/evaluation/metrics.py`, `src/egre/evaluation/cli.py`, `src/egre/demo.py`, package exports only if needed, generated gitignored `runs/demo.json`, then `docs/TASKS.md`, `docs/STATUS.md`, and this append-only log after verification.
- test-first outline: `python -m pytest tests/evaluation -m toolchain -q` must assert every exact P1/P2/P3 outcome and all three gate views from `docs/PROTOTYPE.md`; `python -m egre.demo` must print the per-policy matrix plus C1/C2/C3 and write `runs/demo.json`; then `./scripts/verify.sh` must pass.

## 2026-10-28 iter 8 — P-07 — done
- changed: added offline claim/run evaluation, support-by-truth aggregation, C1/C2/C3 precision and coverage metrics, saved-JSON CLI rendering, and the full scripted demo in `src/egre/evaluation/` and `src/egre/demo.py`; added exact end-to-end acceptance tests in `tests/evaluation/`; generated gitignored `runs/demo.json`; updated only P-07 and loop state.
- acceptance: `python -m pytest tests/evaluation -m toolchain -q` -> pass (3 tests asserting all 21 policy/program outcomes, the 14/3/1/4 support x truth matrix, and exact gate metrics); `python -m egre.demo` -> pass (printed the per-policy matrix and C1/C2/C3, wrote valid `runs/demo.json`).
- verify: `./scripts/verify.sh` -> pass (ruff clean, mypy clean across 32 source files, 56 tests passed and 57 toolchain tests deselected).
- review: no test was deleted, skipped, loosened, or made circular; exact policy outcomes and counts are fixed independently of implementation output (`tests/evaluation/test_metrics.py:11`, `tests/evaluation/test_metrics.py:71`). Truth is joined only in the offline evaluator after support and experiment verdicts are independently derived (`src/egre/evaluation/metrics.py:98`, `src/egre/evaluation/metrics.py:111`), and no LLM output decides support, verdict, status, or truth. Existing fail-closed runner and ledger behavior are reused unchanged; runtime packages import no corpus/evaluation code. Changes are limited to P-07, add no dependency or novelty claim, and `git diff --check` plus `./scripts/check_protected.sh` passed.
- notes / surprises / follow-ups: the intentional red run failed because P-07 modules did not exist. Acceptance then passed; the first verifier attempt found only exception-type lint, which was corrected before the final acceptance/demo/verifier sequence passed. C1/C2/C3 precision is claim-level, while coverage is the fraction of the 21 policy/program opportunities retaining a true claim. P-08 is now the first eligible task and requires the human spend gate.
- stop signal: `STOP_HUMAN`.

## 2026-10-28 iter 9 — P-09 — plan
- plan: document the completed scripted prototype demo, its verified gate table, and its limitations; state explicitly that the optional paid P-08 real-LLM run was deferred by the user.
- files to touch: `README.md`, then `docs/TASKS.md`, `docs/STATUS.md`, and this append-only log after verification.
- test-first outline: inspect the generated `runs/demo.json` values used in the README, run `python -m egre.demo`, then run `./scripts/verify.sh --full`; review the diff for claims beyond the tested prototype scope.

## 2026-10-28 iter 9 — P-09 — done
- changed: added the `Prototype demo` section to `README.md` with the no-key command, the generated support/truth and C1/C2/C3 tables, explanations of the gate views, and an explicit limitations list; recorded that optional P-08 was deferred and updated only P-09 and loop state.
- acceptance: README contains `python -m egre.demo`, the verified 14/3/1/4 support x truth matrix, exact C1/C2/C3 output, and all required limitations (seven programs, one claim type, native execution rather than emulation, scripted rather than real agents); `python -m egre.demo` regenerated valid `runs/demo.json`.
- verify: `./scripts/verify.sh --full` -> pass (ruff clean, mypy clean across 32 source files, 113 tests passed).
- review: output values match the generated demo; wording is limited to this corpus and does not claim general effectiveness or a real-LLM result. No code, test, dependency, protected file, verdict logic, ledger path, or runtime boundary changed; `git diff --check` and `./scripts/check_protected.sh` passed.
- notes / surprises / follow-ups: P-08 remains `todo` but was explicitly deferred by the user; the complete no-spend scripted prototype is documented and reproducible.
- stop signal: `STOP_HUMAN` because the only remaining prototype task is the deferred human-owned P-08 real-LLM run.

## 2026-10-29 iter 10 — P-08 — plan
- plan: adapt the OpenAI-compatible provider to the explicitly authorized local Ollama endpoint, add bounded local-model response parsing and detailed traces, implement resumable per-program/repeat run files and directory evaluation, then attempt only the one-program/one-repeat smoke run if localhost Ollama is reachable.
- files to touch: `src/egre/llm/{base,openai}.py`, `src/egre/agent/loop.py`, new `src/egre/cli/`, `src/egre/evaluation/{cli,metrics}.py`, additive tests under `tests/{llm,agent,cli,evaluation}/`, and after verification only P-08/status entries in `docs/TASKS.md`, `docs/STATUS.md`, and this append-only log.
- test-first outline: add network-free fake-client tests for base URL/settings/usage/reasoning, tolerant JSON extraction, invalid-step accounting, zero-claim completion, per-response trace persistence, resumable output naming/filtering, and directory evaluation totals; run focused tests, `./scripts/verify.sh --full`, then probe only `http://localhost:11434` and run the authorized smoke commands if reachable.

## 2026-10-29 iter 10 — P-08 — partial (code complete; local runs pending)
- changed: extended the import-safe OpenAI-compatible adapter with configurable base URL, temperature, output-token cap and timeout; added raw response/reasoning/token capture; made the bounded loop tolerate fenced/prose JSON and `<think>` blocks while counting every invalid or timed-out step; added zero-claim completion; implemented the local-only, resumable per-program/repeat run CLI and run-directory evaluation with support x truth, C1/C2/C3, total claims, zero-claim runs and invalid-step totals. P-08 metadata now records `owner: agent`, `spend: none`, and the local Ollama model; its status remains `doing` because the requested runs are pending.
- tests added: network-free fake-client coverage in `tests/llm/test_local_openai.py`, local-response and invalid-step coverage in `tests/agent/test_local_loop.py`, run-file/resume/local-endpoint coverage in `tests/cli/test_run.py`, and directory aggregation coverage in `tests/evaluation/test_run_directory.py`.
- verify: `PATH="$PWD/.venv/bin:$PATH" ./scripts/verify.sh --full` -> pass (Ruff clean; mypy clean across 34 source files; 125 tests passed in 6.51 s). Focused P-08 tests also passed (12 tests). `git diff --check` and `./scripts/check_protected.sh` passed.
- review: no test was deleted, skipped, loosened, or made circular. LLM output only proposes validated actions and claims; deterministic support, native experiment verdict, status and truth join remain in the evaluator. Unknown ledger handles still fail closed, only mediator tools append evidence, executor failures still produce `inconclusive`, runtime boundary tests pass, no dependency or novelty claim was added, and no protected file changed.
- smoke reachability check: `curl --max-time 3 --silent --show-error --fail http://localhost:11434/v1/models` exited 7 with the real output `curl: (7) Failed to connect to localhost port 11434 after 0 ms: Couldn't connect to server`. Per the task instruction, no workaround was attempted and the smoke command was not run.
- human smoke commands: `OPENAI_BASE_URL=http://localhost:11434/v1 OPENAI_API_KEY=ollama python -m egre.cli.run --llm openai --model qwen3.5:4b --programs crc32_clean --repeats 1 --out runs/smoke-qwen3.5-4b`, then `python -m egre.evaluation.cli runs/smoke-qwen3.5-4b`.
- full batch commands: `OPENAI_BASE_URL=http://localhost:11434/v1 OPENAI_API_KEY=ollama python -m egre.cli.run --llm openai --model qwen3.5:4b --repeats 3 --out runs/ollama-qwen3.5-4b`, then `python -m egre.evaluation.cli runs/ollama-qwen3.5-4b`.
- stop signal: `STOP_HUMAN`; run the smoke and full batch from the user's terminal. No commit was created.

## 2026-10-29 iter 10 — P-08 — done
- changed: preserved the 21 completed local-model run files in `runs/ollama-qwen3.5-4b-final` and added `docs/RESULTS_PROTOTYPE.md` with the exact evaluation table, uniform run configuration, endpoint-reported token totals, cautious interpretation, and four requested trace inspections.
- acceptance: `python -m egre.evaluation.cli runs/ollama-qwen3.5-4b-final` -> pass (21 runs; 25 claims; support x truth 6/0/17/2; C1 92.0% precision and 90.5% coverage; C2 100.0% and 23.8%; C3 100.0% and 90.5%; 2 zero-claim runs; 46 invalid steps). All 21 files use `qwen3.5:4b`, temperature 0.2, max tokens 700 and timeout 120.0 seconds.
- verify: the first full-verifier attempt exposed stricter type checking from the now-installed OpenAI SDK; the adapter's dynamic optional-SDK boundary was typed explicitly without changing runtime behavior. The second `./scripts/verify.sh --full` passed (Ruff clean, mypy clean across 34 source files, 125 tests passed in 6.25 s).
- manual review: `crc32_obfpoly-repeat-001` and `fnv1a_crcdecoy-repeat-001` made correct but insufficiently supported memory-only claims; `djb2_fnvdecoy-repeat-001` ended with no accepted claim after invalid calls; the false `crc32` claim in `fnv1a_crcdecoy-repeat-002` cited only memory and was independently refuted. None of the four inspected cases called `run`.
- review: results were copied rather than regenerated; documented counts match the evaluation CLI and run JSON. No scoring, verdict, support, truth, ledger, protected file, dependency or existing test expectation changed. P-08 is complete and P-10 is the user-authorized next analysis-only task.
- stop signal: `CONTINUE`.

## 2026-10-29 iter 11 — P-10 — plan
- plan: extend only the run-directory evaluation presentation with insufficient-support reason counts, per-program aggregation, duplicate-primitive detection, and a separately labeled deduplicated C1/C2/C3 comparison; preserve the existing primary scoring path and output.
- files to touch: additive tests in `tests/evaluation/test_run_directory.py`, analysis helpers in `src/egre/evaluation/metrics.py`, rendering in `src/egre/evaluation/cli.py`, then P-10/status entries in `docs/TASKS.md`, `docs/STATUS.md`, and this append-only log after verification.
- test-first outline: construct fixed run documents containing multiple reason codes, zero-claim runs, invalid steps and duplicate primitives; assert exact reason/per-program/duplicate counts and deduplicated views while retaining all existing assertions unchanged; run evaluation tests, the CLI on the final 21-run snapshot, and `./scripts/verify.sh --full`.

## 2026-10-29 iter 11 — P-10 — done
- changed: kept the primary support x truth and C1/C2/C3 scoring untouched, then added insufficient-support reason counts, a per-program aggregate, duplicate `(run, primitive)` detection, and a separately labeled first-registered-claim deduplicated view to the run-directory CLI.
- acceptance: `python -m pytest tests/evaluation -q` -> pass (6 tests). `python -m egre.evaluation.cli runs/ollama-qwen3.5-4b-final` reports 19 `NO_SIGNATURE_EVIDENCE` claims; per-program rows for all seven variants; 4 runs containing duplicate primitives; and deduplicated views C1 = 21 claims/19 true/2 false/90.5% precision/90.5% coverage, C2 = 3/3/0/100.0%/14.3%, C3 = 19/19/0/100.0%/90.5%.
- verify: the first full-verifier attempt found one Ruff formatting issue in the table header; it was corrected without semantic changes. The second `./scripts/verify.sh --full` passed (Ruff clean, mypy clean across 34 source files, 126 tests passed in 8.55 s). `git diff --check` and `./scripts/check_protected.sh` passed.
- review: no existing test was deleted, skipped, loosened, or changed; the additive test uses fixed hand-authored outcomes and expected aggregates, so it is not circular. The original `summarize` path remains the primary output, while deduplication creates new run values and calls the same deterministic summarizer. No LLM output decides support, verdict, status or truth; no runner, ledger, runtime boundary, dependency, protected file or novelty claim changed.
- notes: deduplication keeps the first registered claim for each primitive in each run, making the comparison deterministic and explicitly labeled. P-09 already satisfied its README acceptance before this iteration, so it was not reopened.
- stop signal: `STOP_DONE`; all prototype tasks P-00 through P-10 are complete.
