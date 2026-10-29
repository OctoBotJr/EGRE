loop_signal: CONTINUE
current_stage: v2
last_task: V-09 (+ Phase D handoff staged)
last_verify: passed (full verify: ruff, mypy, 226 tests)
blockers: none
human_gates_pending: V-10 (new corpus + held-out vectors — see docs/PHASE_D_HANDOFF.md), V-11 (knowledge base validation — 10/13 entries pre-validated, 3 flagged in the handoff doc), V-20 (full R1-R4 run)

# STATUS (overwrite each iteration; keep the first six lines in this exact key: value form)
- V2 mode: scope is docs/V2_SPEC.md, queue is docs/TASKS.md (archived prototype queue: docs/TASKS_PROTOTYPE.md). Ghidra, angr, Docker still skipped (v2 non-goals, section 9). Phase B (V-03..V-07) and Phase C (V-08, V-09) complete.
- V-09 recap: Observation gained coverage/tracer_mismatch; MediatorTools.run() auto-traces every call; build_evidence_graph adds "executed" edges; support/engine.py gained rel_s2/tier_s2/evaluate_claim_s2/qualified_blocks(); controller/status_v2.py's reason_codes() gained UNEXECUTED_EVIDENCE/UNQUALIFIED_EVIDENCE; evaluation/rescoring.py gained retrace_ledger()/rescore_document_with_s2(). Empirically, S2 re-scoring of the real R0 corpus finds more of the S0/S1 blind spot than S1 alone (4 claims drop to <=contested under S2 vs 1 under S1), and fully resolves the fnv1a_crcdecoy decoy that S1 could only call "contested".
- Phase D handoff: docs/PHASE_D_HANDOFF.md + corpus/v2_pending/ staging (new corpus sources, catalog/truth/reference-vector additions, held-out vectors, kb/algorithms.json draft with 10/13 entries pre-validated against real external sources, kb_reference_impls.py) are ready for the human to review and merge into the protected corpus files. build.py now supports "opt": "O2" per catalog entry. Nothing is merged into corpus/src, corpus/catalog.json, corpus/truth, corpus/reference_vectors.json, or kb/ yet — those moves are the human's call.
- Now working Phase E in parallel (agent-side, does not depend on Phase D): V-13 (schema-constrained output with a hypotheses field, R1) is next, then V-14 (query_graph tool, R2), V-15 (reason-code feedback loop, R3). V-16 (open-world mode) depends on V-12/KB, so it waits on Phase D.
- Environment: unchanged from prototype — project-local Python 3.11 `.venv`, native macOS arm64, no paid API key, local Ollama model for LLM runs. networkx and unicorn both required (installed via `pip install -e ".[dev,re]"`). Full test suite now takes ~25s (was ~6s before V-09) since MediatorTools.run() builds a Unicorn tracer on every call.
