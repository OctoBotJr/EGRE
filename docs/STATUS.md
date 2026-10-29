loop_signal: CONTINUE
current_stage: v2
last_task: V-04
last_verify: passed (full verify: ruff, mypy, 144 tests)
blockers: none
human_gates_pending: V-10 (new corpus + held-out vectors), V-11 (knowledge base validation), V-20 (full R1-R4 run)

# STATUS (overwrite each iteration; keep the first six lines in this exact key: value form)
- V2 mode: scope is docs/V2_SPEC.md, queue is docs/TASKS.md (archived prototype queue: docs/TASKS_PROTOTYPE.md). Ghidra, angr, Docker still skipped (v2 non-goals, section 9).
- V-01/V-02/V-03 done (see prior commits). V-04 done: src/egre/graph/evidence.py builds a networkx DiGraph with the Program layer (fn/bb/ins/k nodes; contains/cfg_next/defines_constant edges, from V-03's CFG) and the Observation layer (obs:<handle> nodes; anchored_in edges — to every overlapping block for disasm/memory, to the function only for "run" since there's no tracer yet). JSON export/import via networkx's node_link_data/graph. I9 rebuild-equality verified (same ledger+CFG -> byte-identical JSON document). Added networkx>=3.2 to the `re` extra in pyproject.toml (flagged to user: pyproject.toml is a protected file; this is the dependency V2_SPEC.md section 4.1 calls for).
- Execution/knowledge/claims layers (executed edges, kb: nodes, claim:/exp: nodes) are deliberately NOT yet populated — those arrive with V-09 (tracer), V-12 (KB), and V-06/V-17 (claims/experiments) respectively, each extending build_evidence_graph's inputs rather than guessing the wiring now.
- Next: V-05 (support engine: rel, tiers, cited vs available, S0/S1 scoring modes) consumes this graph plus a claim's cited handles.
- Environment: unchanged from prototype — project-local Python 3.11 `.venv`, native macOS arm64, no paid API key, local Ollama model for LLM runs. networkx now required (installed via `pip install -e ".[dev,re]"`).
