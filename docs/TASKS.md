# TASKS — PROTOTYPE queue (3-hour slice; scope: docs/PROTOTYPE.md). Full queue archived in docs/TASKS_FULL.md.

status: todo | doing | done | blocked. Agents change `status` only. One task per iteration.
Time boxes are guidance for the human; if a task exceeds 2x its box, mark blocked and use the fallback noted.

## P-00 Environment (human, ~15 min)
status: done | depends: - | owner: human | spend: none
acceptance: `source .venv/bin/activate && ./scripts/verify.sh` passes; `./scripts/check_env.sh` has no MISSING for clang/strip/codesign/otool/sandbox-exec/radare2(optional)/python libs; `./scripts/smoke_env.sh` prints SMOKE PASSED
notes: Ghidra is NOT needed (warn only). Skip setup_ghidra.sh.
## P-01 Corpus build (~20 min)
status: done | depends: P-00 | owner: agent | spend: none
acceptance: `python -m egre.corpus.build && python -m pytest tests/corpus -m toolchain -q` — 7 stripped, signed arm64 Mach-O binaries; each binary's native output equals corpus/reference_vectors.json for its truth primitive on every input; task JSONs contain no truth fields
## P-02 References, executor, runner verdicts (~25 min)
status: done | depends: P-01 | owner: agent | spend: none
acceptance: `python -m pytest tests/runner -m toolchain -q` — verify_claim confirms the true primitive and refutes each wrong primitive for all 7 programs; bad binary path -> inconclusive (never refuted); no-network wrapper blocks a network call
notes: fallback if sandbox-exec misbehaves: run without it and record the limitation in DECISIONS.md
## P-03 Ledger, constant extraction, mediator tools (~30 min)
status: done | depends: P-01 | owner: agent | spend: none
acceptance: `python -m pytest tests/ledger tests/mediator -m toolchain -q` — disasm facts of crc32_clean include 0xEDB88320; crc32_obfpoly does NOT; fnv1a_crcdecoy includes it; djb2_fnvdecoy includes 5381 and the FNV constants; agent-facing API has no write path; unknown handle rejected
notes: this is the riskiest task (mov/movk reconstruction); if constants fail after 20 min, fall back to radare2 `pdf` text for disassembly while keeping extract_constants
## P-04 Claims and T2 contract checker (~15 min)
status: done | depends: P-03 | owner: agent | spend: none
acceptance: `python -m pytest tests/claims tests/contracts -q` — hand-built ledger/claim cases for rules (a) and (b) and all four reason codes, incl. the decoy cases
## P-05 Status controller and registry-only report (~10 min)
status: done | depends: P-02, P-04 | owner: agent | spend: none
acceptance: `python -m pytest tests/controller tests/report -q` — full (support x verdict) table; report claims == registry claims (test); support_gap flag set when verified but insufficient
## P-06 Agent loop, fake LLM, scripted policies, one real provider adapter (~25 min)
status: done | depends: P-05 | owner: agent | spend: none
acceptance: `python -m pytest tests/agent tests/llm -m toolchain -q` — policies P1-P3 run on all 7 programs through the real mediator/ledger; no network in tests; real adapter is import-safe without a key
## P-07 Evaluation table and demo (~15 min)
status: done | depends: P-06 | owner: agent | spend: none
acceptance: `python -m pytest tests/evaluation -m toolchain -q` asserts the exact expected outcomes in docs/PROTOTYPE.md; `python -m egre.demo` prints the matrix and views C1/C2/C3 and writes runs/demo.json
## P-08 Real LLM run (human approves spend, ~20 min)
status: todo | depends: P-07 | owner: human | spend: approved
acceptance: `python -m egre.cli.run --llm <provider> --repeats 3` then `python -m egre.evaluation.cli runs/<dir>` prints the table for 7 programs x 3 repeats; cost and token totals logged
notes: set a hard spend cap on the provider account first; key via environment variable only
## P-09 README demo section and limitations (~5 min)
status: done | depends: P-07 | owner: agent | spend: none
acceptance: README has a "Prototype demo" section with the command, the output table, and an honest limitations list (7 programs, one claim type, native execution not emulation, scripted vs real agent)
