# ARCHITECTURE (human-owned; protected)

One LLM reasoning agent; everything else deterministic. The offline evaluation harness is
physically and import-wise separate from the runtime.

## Components (package = src/egre/<name>)
| Package | Responsibility | In -> Out |
|---|---|---|
| agent | single ReAct-style LLM loop; submits/revises/retracts typed claims | observation views + reason codes -> tool requests, claim objects |
| llm | LLM client abstraction: fake, record/replay, real providers | prompts -> responses |
| mediator | allowlisted, schema-validated tool calls; resource limits; no raw shell, no network | tool requests -> tool calls, handles |
| sandbox | no-network execution wrapper (sandbox-exec) + resource limits around native RE tools (Ghidra, radare2, Unicorn, lldb) | calls -> raw output |
| ledger | immutable observation records written by the runtime only | tool/experiment output -> records (handle, anchor, reachability, derivation links, origin tag) |
| claims | typed claim schema, registry, revision history | agent submissions -> claims |
| contracts | deterministic per-claim-type evidence rules; provenance grouping | claim + ledger -> entailed / insufficient + reason code |
| runner | builds and executes experiments (emulation, tracing, symbolic) | claim + params -> confirmed / refuted / inconclusive (logged to ledger) |
| controller | combines verdicts into claim status; reason-code feedback | verdicts -> statuses, feedback |
| report | renders report ONLY from the claim registry | registry -> annotated report |
| corpus | program generator, build matrix, truth oracle facts | seeds -> binaries + truth |
| evaluation | claim normalizer, metrics, gold-label tooling | reports + truth -> results |

## Invariants (each should be enforced by a test)
I1 The agent cannot write the ledger; unknown handles fail closed.
I2 No LLM decides contract results, experiment verdicts or truth.
I3 Harness failure => `inconclusive`, never `refuted`.
I4 Report text is rendered only from the claim registry (no free-text claim leakage).
I5 Runtime packages never import corpus or evaluation.
I6 Support (evidence-based) and truth (oracle-based) are computed independently.

## Flow
agent -> mediator -> toolchain -> ledger -> (agent sees compact views)
agent -> claim registry -> contract checker (+ ledger) -> experiment runner -> ledger
status controller -> reason codes -> agent ; status controller -> report renderer
offline: truth oracle + claim normalizer + metrics read report, ledger, truth.
