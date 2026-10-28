# TASKS_FULL — archived full-project queue (NOT used for the prototype; see docs/TASKS.md)

Format per task: heading, one metadata line, `acceptance:` (an executable check), optional `notes:`.
status: todo | doing | done | blocked. owner: agent | human. spend: none | approved.
Stages follow the development roadmap (1 env, 2 sandbox, 3 spec, 4 corpus, 5 ledger, 6 baseline agent,
7 checker, 8 runner, 9 gate, 10 eval harness, 11 pilot/freeze, 12 full run, 13 analysis).

## Stage 1 — environment
## T-001 Verify scaffold installs and verify.sh passes
status: todo | stage: 1 | depends: - | owner: agent | spend: none
acceptance: `pip install -e ".[dev]" && ./scripts/verify.sh`
## T-002 Native toolchain setup (human)
status: todo | stage: 1 | depends: T-001 | owner: human | spend: none
acceptance: `./scripts/check_env.sh` reports no MISSING; `./scripts/smoke_env.sh` prints SMOKE PASSED; output of check_env saved to docs/ENV_VERSIONS.md
notes: follow docs/SETUP.md (Brewfile, Ghidra via scripts/setup_ghidra.sh)
## T-003 Formalize the toolchain smoke test as pytest tests
status: todo | stage: 1 | depends: T-002 | owner: agent | spend: none
acceptance: `python -m pytest tests/sandbox -m toolchain` (compile with clang, strip, re-sign, otool, Unicorn emulate, Ghidra headless import, one real Ghidra decompile if natives exist)
notes: base it on scripts/smoke_env.sh; toolchain tests run via verify.sh --full
## Stage 2 — sandbox
## T-010 No-network execution wrapper (egre.sandbox)
status: todo | stage: 2 | depends: T-003 | owner: agent | spend: none
acceptance: `python -m pytest tests/sandbox -m toolchain -k sandbox`
notes: sandbox-exec profile denying network, plus ulimit/timeout resource limits; sandbox-exec is deprecated, so test it and document if unavailable
## T-011 Determinism and no-network tests
status: todo | stage: 2 | depends: T-010 | owner: agent | spend: none
acceptance: same tool call twice gives identical output; outbound connection under the wrapper fails (tests)
## Stage 3 — specification
## T-020 Complete claim taxonomy and evidence contracts (human)
status: todo | stage: 3 | depends: T-001 | owner: human | spend: none
acceptance: no TODO left in docs/CLAIM_TAXONOMY.md; reviewed by two passes
## T-021 Pydantic claim schema from taxonomy
status: todo | stage: 3 | depends: T-020 | owner: agent | spend: none
acceptance: `python -m pytest tests/claims -q`; schema round-trips every example in CLAIM_TAXONOMY.md
## T-022 Status rules and reason-code module
status: todo | stage: 3 | depends: T-021 | owner: agent | spend: none
acceptance: `python -m pytest tests/controller -k status_rules`
## T-023 Hand-label >= 30 example claims (human)
status: todo | stage: 3 | depends: T-020 | owner: human | spend: none
acceptance: tests/fixtures/claims_gold_seed.json exists; two labeling passes agree on nearly all items

## Stage 4 — corpus and truth
## T-030 Program template framework with seeds
status: todo | stage: 4 | depends: T-021 | owner: agent | spend: none
acceptance: `python -m pytest tests/corpus -k framework`; same seed -> identical source
## T-031 Primitive templates (CRC variants, base64 variants, XTEA, RC4-like)
status: todo | stage: 4 | depends: T-030 | owner: agent | spend: none
acceptance: `python -m pytest tests/corpus -k primitives`
## T-032 Validator and state-machine templates
status: todo | stage: 4 | depends: T-030 | owner: agent | spend: none
acceptance: `python -m pytest tests/corpus -k validators`
## T-033 Build matrix (-O0/-O2, stripped, re-signed)
status: todo | stage: 4 | depends: T-031 | owner: agent | spend: none
acceptance: `python -m pytest tests/corpus -m toolchain -k build_matrix`
notes: clang -arch arm64; strip; codesign --force --sign - (stripping invalidates the signature); record binary hashes
## T-034 Truth-fact emitter (T1–T5 schema)
status: todo | stage: 4 | depends: T-031 | owner: agent | spend: none
acceptance: `python -m pytest tests/corpus -k truth_emit`
## T-035 Independent truth verifier (concrete execution, separate code path)
status: todo | stage: 4 | depends: T-033, T-034 | owner: agent | spend: none
acceptance: every truth fact for every generated binary confirmed by the verifier
## T-036 Tier B misleading-evidence variants
status: todo | stage: 4 | depends: T-035 | owner: agent | spend: none
acceptance: variants keep oracle outcomes identical to their clean pair (tests)

## Stage 5 — ledger and mediator
## T-040 Ledger record schema and append-only store
status: todo | stage: 5 | depends: T-021 | owner: agent | spend: none
acceptance: `python -m pytest tests/ledger`; agent-facing API has no write path (test)
## T-041 Provenance links and reachability tags
status: todo | stage: 5 | depends: T-040 | owner: agent | spend: none
acceptance: `python -m pytest tests/ledger -k provenance`
## T-042 Static adapters (disassembly, strings, xrefs)
status: todo | stage: 5 | depends: T-041, T-010 | owner: agent | spend: none
acceptance: `python -m pytest tests/ledger -m toolchain -k static_adapters`
## T-043 Dynamic adapters (Unicorn emulation + trace hooks, sandboxed native run)
status: todo | stage: 5 | depends: T-041, T-010 | owner: agent | spend: none
acceptance: `python -m pytest tests/ledger -m toolchain -k dynamic_adapters`
notes: no strace/gdb on macOS; map Mach-O segments (via lief) into Unicorn; trace = code/block hooks
## T-044 Tool mediator (allowlist, schemas, limits)
status: todo | stage: 5 | depends: T-040 | owner: agent | spend: none
acceptance: `python -m pytest tests/mediator`; raw shell and network requests rejected
## T-045 Session replay rebuilds identical ledger
status: todo | stage: 5 | depends: T-042, T-044 | owner: agent | spend: none
acceptance: replay test passes

## Stage 6 — baseline agent (C0, C1)
## T-050 LLM client: fake, record/replay, provider adapters
status: todo | stage: 6 | depends: T-001 | owner: agent | spend: none
acceptance: `python -m pytest tests/llm`; no network in tests
## T-051 ReAct-style agent loop on scripted fake trajectories
status: todo | stage: 6 | depends: T-044, T-050 | owner: agent | spend: none
acceptance: `python -m pytest tests/agent`
## T-052 Typed claim channel and registry
status: todo | stage: 6 | depends: T-021, T-051 | owner: agent | spend: none
acceptance: `python -m pytest tests/claims -k registry`; unknown handle citations rejected
## T-053 Run logging (steps, prompts, tokens, cost)
status: todo | stage: 6 | depends: T-051 | owner: agent | spend: none
acceptance: `python -m pytest tests/agent -k logging`
## T-054 Pilot: real model on <= 10 programs (human approves spend)
status: todo | stage: 6 | depends: T-052, T-053, T-036 | owner: human | spend: approved
acceptance: transcripts reviewed; agent uses tools sensibly

## Stage 7 — contract checker (C2)
## T-060 Checker framework
status: todo | stage: 7 | depends: T-022, T-041 | owner: agent | spend: none
acceptance: `python -m pytest tests/contracts -k framework`
## T-061 Contracts for T1–T5
status: todo | stage: 7 | depends: T-060, T-020 | owner: agent | spend: none
acceptance: `python -m pytest tests/contracts -k per_type`
## T-062 Provenance grouping
status: todo | stage: 7 | depends: T-060 | owner: agent | spend: none
acceptance: `python -m pytest tests/contracts -k provenance`
## T-063 Positive controls and shared-origin suites
status: todo | stage: 7 | depends: T-061, T-062 | owner: agent | spend: none
acceptance: no positive control downgraded; shared-origin negatives not validated
## T-064 Checker reproduces hand labels (exit check)
status: todo | stage: 7 | depends: T-063, T-023 | owner: agent | spend: none
acceptance: `python -m pytest tests/contracts -k gold_seed` passes with exact agreement

## Stage 8 — experiment runner
## T-070 Runner base; harness failure -> inconclusive
status: todo | stage: 8 | depends: T-043 | owner: agent | spend: none
acceptance: `python -m pytest tests/runner -k base`
## T-071 T2 verification harness (reference vectors)
status: todo | stage: 8 | depends: T-070, T-035 | owner: agent | spend: none
acceptance: `python -m pytest tests/runner -m toolchain -k t2`
## T-072 T4 verification harness (differential/boundary inputs)
status: todo | stage: 8 | depends: T-070, T-035 | owner: agent | spend: none
acceptance: `python -m pytest tests/runner -m toolchain -k t4`
## T-073 T5 reachability (trace/emulation coverage; symbolic optional)
status: todo | stage: 8 | depends: T-070, T-035 | owner: agent | spend: none
acceptance: `python -m pytest tests/runner -m toolchain -k t5`
notes: angr is optional/experimental on Mach-O (D-011)
## T-074 Runner-vs-oracle agreement report (>= 95% agree, <= 30% inconclusive)
status: todo | stage: 8 | depends: T-071, T-072, T-073 | owner: agent | spend: none
acceptance: report generated under runs/; thresholds met or documented as failed

## Stage 9 — gate (C3) and control (C4)
## T-080 Status controller
status: todo | stage: 9 | depends: T-061, T-070 | owner: agent | spend: none
acceptance: `python -m pytest tests/controller`
## T-081 Reason-code feedback to the agent
status: todo | stage: 9 | depends: T-080, T-052 | owner: agent | spend: none
acceptance: `python -m pytest tests/agent -k feedback`
## T-082 Registry-only report renderer
status: todo | stage: 9 | depends: T-080 | owner: agent | spend: none
acceptance: `python -m pytest tests/report`; report claims == registry claims (test)
## T-083 Condition wiring C0–C4 incl. random-abstention control
status: todo | stage: 9 | depends: T-081, T-082 | owner: agent | spend: none
acceptance: `python -m pytest tests/controller -k conditions`

## Stage 10 — evaluation harness
## T-090 Claim normalizer (free text -> typed claims)
status: todo | stage: 10 | depends: T-021, T-050 | owner: agent | spend: none
acceptance: `python -m pytest tests/evaluation -k normalizer` (fake LLM)
## T-091 Metrics (support x truth matrix, precision-coverage, bootstrap by program)
status: todo | stage: 10 | depends: T-034 | owner: agent | spend: none
acceptance: `python -m pytest tests/evaluation -k metrics`
## T-092 Gold annotation export/import tooling
status: todo | stage: 10 | depends: T-091 | owner: agent | spend: none
acceptance: `python -m pytest tests/evaluation -k gold_io`
## T-093 Annotate >= 300 claims, double-annotated (human)
status: todo | stage: 10 | depends: T-092 | owner: human | spend: none
acceptance: gold files present for both annotators
## T-094 Kappa and checker/normalizer agreement report
status: todo | stage: 10 | depends: T-093 | owner: agent | spend: none
acceptance: kappa computed; checker kappa >= 0.7 or documented failure

## Stage 11 — pilot and freeze
## T-100 Pilot all conditions (human approves spend)
status: todo | stage: 11 | depends: T-083, T-094 | owner: human | spend: approved
acceptance: pilot runs complete; cost per run measured; artifacts reviewed
## T-101 Freeze configuration and pre-register thresholds (human)
status: todo | stage: 11 | depends: T-100 | owner: human | spend: none
acceptance: one command reproduces the pilot from the frozen config

## Stage 12 — full run
## T-110 Resume-safe experiment orchestrator with budget caps
status: todo | stage: 12 | depends: T-101 | owner: agent | spend: none
acceptance: `python -m pytest tests/controller -k orchestrator` (fake LLM, interruption/resume)
## T-111 Execute full run (human approves spend)
status: todo | stage: 12 | depends: T-110 | owner: human | spend: approved
acceptance: all planned cells present in runs/, incl. failures

## Stage 13 — analysis and release
## T-120 Analysis scripts and ablations
status: todo | stage: 13 | depends: T-111 | owner: agent | spend: none
acceptance: reproduces headline tables from raw records with one command
## T-121 Release packaging (generator, oracle, ledger, gate, logs)
status: todo | stage: 13 | depends: T-120 | owner: agent | spend: none
acceptance: clean-checkout reproduction of tables from retained records
