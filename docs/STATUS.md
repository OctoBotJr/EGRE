loop_signal: CONTINUE
current_stage: v2
last_task: V-06
last_verify: passed (full verify: ruff, mypy, 183 tests)
blockers: none
human_gates_pending: V-10 (new corpus + held-out vectors), V-11 (knowledge base validation), V-20 (full R1-R4 run)

# STATUS (overwrite each iteration; keep the first six lines in this exact key: value form)
- V2 mode: scope is docs/V2_SPEC.md, queue is docs/TASKS.md (archived prototype queue: docs/TASKS_PROTOTYPE.md). Ghidra, angr, Docker still skipped (v2 non-goals, section 9).
- V-01..V-05 done (see prior commits). V-06 done: src/egre/controller/status_v2.py — derive_status_v2(verdict) is verdict-only (refuted/verified/unverified, support no longer folded in); derive_flags() computes support_gap (verified AND cited_tier <= contested) plus pass-through citation_gap/self_contradicted from ClaimSupport; reason_codes(claim, ledger, task) implements the 3.8 codes EXCEPT UNEXECUTED_EVIDENCE/UNQUALIFIED_EVIDENCE (need tracer coverage, deferred to V-09); detect_post_hoc() implements the 3.5 temporal proxy given a HypothesisStep sequence + observation-to-step map (no real producer of that data yet — R1's schema output is V-13 — but the algorithm is implemented and unit-tested standalone). v1's controller/status.py (S0 path) is untouched. Added src/egre/report/subgraph.py (claim_subgraph_mermaid: walks only a claim's own cited observations -> anchored fn/bb -> defines_constant -> k, so the explanation never shows more than what was cited) and render_markdown_v2() in report/render.py (v2 claim table + one Mermaid block per claim, same registry-only id-matching invariant as v1's renderers).
- Next: V-07 (re-score R0 and scripted runs under S0/S1 — needs a small evaluation-side wrapper that runs claims through both contracts.t2.check and support.engine.tier and prints both).
- Environment: unchanged from prototype — project-local Python 3.11 `.venv`, native macOS arm64, no paid API key, local Ollama model for LLM runs. networkx required (installed via `pip install -e ".[dev,re]"`).
