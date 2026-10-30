# TASKS — V2 queue (scope: docs/V2_SPEC.md). Prototype (v1) queue archived in docs/TASKS_PROTOTYPE.md.

status: todo | doing | done | blocked. Agents change `status` only. One task per iteration.
Human-owned tasks (oracle validation, machine-time gates) are marked `owner: human`.

## Phase A — baseline and hygiene

## V-01 Finish v1 P-09/P-10 polish, freeze R0
status: done | depends: - | owner: agent | spend: none
acceptance: evaluation CLI prints dedup counts and per-program table; `runs/ollama-qwen3.5-4b-final` frozen as R0; `docs/RESULTS_PROTOTYPE.md` written; `python -m pytest tests/evaluation -q` passes
notes: v2 spec section 8, Phase A. Mostly already done in v1 P-09/P-10 — confirm and close any gaps only.

## V-02 Full per-step context logging
status: done | depends: V-01 | owner: agent | spend: none
acceptance: run files log messages sent, raw response, and parsed action per step; a replay helper reconstructs the exact model context at any step from a run file; tests cover replay equality

## Phase B — graph and support engine (no tracer)

## V-03 CFG builder with Capstone
status: done | depends: V-02 | owner: agent | spend: none
acceptance: leaders = entry, branch targets, instruction after branch/ret; every corpus binary yields blocks covering [addr, addr+size) for the target function; decoy dead-branch block exists as its own block; tests on all v1 binaries

## V-04 Evidence graph builder
status: done | depends: V-03 | owner: agent | spend: none
acceptance: networkx graph + JSON export; node/edge types match V2_SPEC.md section 4.2; I9 rebuild-equality test (same ledger+binary+KB -> identical graph)

## V-05 Support engine: rel, tiers, scoring modes S0/S1
status: done | depends: V-04 | owner: agent | spend: none
acceptance: hand-built ledger fixtures covering every tier (contradicted/none/contested/structural/behavioral), the shared-constant case, and the contradiction case; S0 reproduces v1 results on existing runs exactly; tests in tests/support or equivalent

## V-06 Status, flags, reason codes v2; per-claim evidence subgraph in report
status: done | depends: V-05 | owner: agent | spend: none
acceptance: status/flags per V2_SPEC.md section 3.6; reason codes per section 3.8; report stays registry-only (test); flags (support_gap, citation_gap, self_contradicted, post_hoc) covered by tests; report includes a Mermaid evidence subgraph per claim

## V-07 Re-score R0 and scripted runs under S0/S1
status: done | depends: V-06 | owner: agent | spend: none
acceptance: evaluation CLI produces S0/S1 tables for existing runs; scripted-policy S0/S1 cells match V2_SPEC.md section 6 table (rows available at this phase: no tracer yet, so S2 rows deferred to V-09)

## Phase C — execution qualification

## V-08 Unicorn tracer for the target function
status: done | depends: V-03 | owner: agent | spend: none
acceptance: maps Mach-O segments via lief, sets up stack, places input buffer in x0/x1, uses an LR sentinel for return, hooks blocks, enables FP/SIMD via CPACR_EL1, bounds instructions by budget; tracer output equals native output on all reference vectors for all v1 binaries at -O0; dead-branch blocks never show as covered
notes: fallback if Unicorn mapping fails or is slow — ship S1 first (already done by V-07), mark constants UNQUALIFIED, record the limitation and keep going

## V-09 Auto-trace every agent run; scoring mode S2
status: done | depends: V-08 | owner: agent | spend: none
acceptance: every agent `run` call is traced automatically (coverage attaches to the run observation via `executed` edges); on tracer/native output mismatch record `tracer_mismatch`, drop coverage, never change the output; scripted-policy S2 cells match V2_SPEC.md section 6; R0 re-scored under S2 via offline replay-tracing

## Phase D — corpus v2 and knowledge base (human-owned oracles)

## V-10 New corpus programs, -O2 builds, held-out vectors
status: done | depends: V-09 | owner: human | spend: none
acceptance: `fnv1_clean`, `jamcrc_clean`, `crc32c_clean`, `sdbm_execdecoy` added per V2_SPEC.md section 5.1; all 11 programs built at -O0 and -O2, stripped, ad-hoc re-signed (22 binaries); native outputs match reference vectors on all vectors; held-out verdict vectors stored separately from public vectors and never referenced by runtime code

## V-11 Knowledge base kb/algorithms.json
status: done | depends: V-10 | owner: human | spend: none
notes: shipped with 10/13 entries (elf_hash, sdbm, djb2a excluded -- unresolved/unvalidated, see commit)
acceptance: 13 entries per V2_SPEC.md section 5.2 with id/family/aliases/description/parameters/signature_constants/public_vectors; reference implementations validated against published check values, zlib cross-checks, or two independent implementations; entries that fail validation are excluded, not guessed; validation tests committed

## V-12 lookup_knowledge tool, knowledge graph nodes
status: done | depends: V-11 | owner: agent | spend: none
acceptance: exact constant-value index plus keyword match over names/aliases/descriptions; returns public KB fields with K- handles; I7 test (no support path passes through a knowledge node); I10 test (held-out vectors never exposed through tools, KB file, or prompts)

## Phase E — agent-side improvements

## V-13 Schema-constrained output with hypotheses field (R1)
status: done | depends: V-07 | owner: agent | spend: none
acceptance: response_format / JSON schema output behind a flag, includes a `hypotheses` list with confidences; fake-client tests; invalid-step accounting unchanged from v1

## V-14 query_graph tool (R2)
status: done | depends: V-13, V-04 | owner: agent | spend: none
acceptance: three fixed read-only queries — constants_in(function), executed_blocks(function), observations(function, kind?) — return handles only; I8 test (tool call never adds or changes citations on a claim)

## V-15 Reason-code feedback loop, <= 2 revisions (R3)
status: done | depends: V-14, V-06 | owner: agent | spend: none
acceptance: scripted policy that revises a claim after receiving UNEXECUTED_EVIDENCE reaches the expected tier within 2 revisions; revision count capped and tested

## V-16 Open-world mode (R4)
status: done | depends: V-12, V-14 | owner: agent | spend: none
acceptance: H = all KB entries + other; P4 on fnv1_clean and jamcrc_clean yields `contested` per V2_SPEC.md section 6

## V-17 Experiment designer (discriminating inputs)
status: done | depends: V-11 | owner: agent | spend: none
acceptance: for the live hypothesis set, designer chooses inputs maximizing distinct predicted outputs; every pair of KB hypotheses is separated by at least one designed input or reported as indistinguishable; designed inputs are generated, not copied from public KB vectors; feeds the verdict runner

## Phase F — evaluation

## V-18 Metrics v2: views C1/C2s/C2b/C3/J
status: done | depends: V-09, V-17 | owner: agent | spend: none
acceptance: deterministic scripted-policy table (P1-P4) matches V2_SPEC.md section 6 on all 22 binaries; coverage and all rates (citation-gap, self-contradiction, contested, post-hoc, reason-code counts) computed per program and per variant

## V-19 Counterfactual probe (H7)
status: done | depends: V-02, V-18 | owner: agent | spend: none
acceptance: offline replay rebuilds exact per-step context, swaps cited evidence for a rival's (and a remove-evidence variant), queries the model 3x at temperature 0 / fixed seed; evidence-sensitive vs evidence-insensitive classification per claim; fake-client tests; LLM is subject only (I11)

## V-20 Full R1-R4 run with local model, re-score, write results
status: todo | depends: V-16, V-19 | owner: human | spend: machine time
acceptance: R1-R4 executed with the local model (budget per V2_SPEC.md section 6: 33 runs/condition at -O0, -O2 for R1 only); all runs re-scored under S0/S1/S2; `docs/RESULTS_V2.md` written with tables, caveats, and honest limitations
