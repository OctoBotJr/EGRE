# DECISIONS (append-only). Agents propose here; humans accept/reject.

Format: `D-NNN | date | status: proposed|accepted|rejected | title` then context, decision, consequences.

D-001 | accepted | Single LLM reasoning agent; all other components deterministic.
D-002 | accepted | Verdicts (contracts, experiments, truth) are never produced by an LLM.
D-003 | accepted | Evaluation code and truth are import-separated from runtime (invariant I5).
D-004 | accepted | Build and test against a fake/record-replay LLM first; real API calls only under `spend: approved`.
D-005 | accepted | Python >= 3.11, src layout, pydantic schemas.
D-006 | accepted | Report rendered only from the claim registry (invariant I4).
D-007 | accepted | Harness failure yields `inconclusive`, never `refuted` (invariant I3).
D-008 | accepted | Human-owned files are protected mechanically (scripts/check_protected.sh), not only by prompt.
D-009 | accepted | Everything runs natively on macOS arm64; no Docker/Linux. Corpus is Mach-O arm64 built with Apple clang, stripped, ad-hoc re-signed. Threat to validity: differs from ELF-based prior work and from model training familiarity.
D-010 | accepted | Ghidra 12.1.x needs JDK 21+ and its macOS arm64 native decompiler may have to be built locally. If that fails, proceed with radare2 + Capstone + Unicorn and add Ghidra later as its own task.
D-011 | accepted | angr is optional/experimental (CLE's Mach-O backend has limited support). Experiments use Unicorn emulation + native execution; T5 uses trace/emulation coverage.
D-012 | accepted | No gdb/strace/ltrace on macOS. Dynamic evidence comes from Unicorn hooks and sandboxed native runs; lldb optional.
D-013 | accepted | Reproducibility on a host machine via Brewfile + recorded versions + build hashes; no container.
D-014 | accepted | Prototype executes programs natively under sandbox-exec (function-level evidence via a one-function wrapper) instead of Unicorn; Unicorn is a later swap behind the Executor interface.
D-015 | accepted | Prototype claim type is T2 only, with a closed primitive set and a `target` function whose address is given in the task file.
D-016 | accepted | Ghidra is optional and skipped for the prototype.
