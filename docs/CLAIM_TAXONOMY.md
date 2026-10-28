# CLAIM_TAXONOMY — DRAFT, human must review and complete (task T-020)

The agent may NOT edit this file. Everything marked TODO is a research decision.

## Status rules (draft)
- verified   : contract met AND experiment confirmed
- supported  : contract met, no experiment run or eligible
- hypothesis : contract not met (insufficient support)
- refuted    : experiment refuted the claim
- inconclusive experiment results never change status to refuted (invariant I3)

## Support ladder (adopted from RARE; see RESEARCH_NOTES)
present < referenced < reachable < executed

## Claim types
Each type needs: subject schema, predicate, required observation kinds, minimum ladder level,
provenance-grouped support count, verifiable? (Y/N), experiment template, reason codes.

### T1 Structure (function boundary, call edge, callee identity)
- verifiable by experiment: N (static contract only)  | min ladder: referenced
- required observations: TODO (e.g. disassembly anchored at the address; xref record for call edges)

### T2 Primitive identification (CRC32, XTEA, base64, RC4-like, ...)
- verifiable: Y (reference vectors in emulation) | min ladder for `supported`: referenced; for `verified`: executed
- required observations: TODO (constant/table or loop-structure observation anchored inside the function)
- experiment: run function on reference vectors; compare outputs

### T3 Data semantics (constant is a key / polynomial / table; buffer length)
- verifiable: N | min ladder: referenced | required observations: TODO

### T4 Input/output relation or accepted-input constraint
- verifiable: Y (differential run on boundary / generated inputs; optional symbolic solve)
- required observations: TODO

### T5 Conditional reachability / behavior
- verifiable: Y (trace coverage via emulation; symbolic reachability optional/experimental) | min ladder: reachable; `verified`: executed
- required observations: TODO

## Reason codes (draft vocabulary)
MISSING_HANDLE, ANCHOR_MISMATCH, TEXT_ONLY_SUPPORT, NO_EXECUTED_EVIDENCE, SHARED_PROVENANCE,
INSUFFICIENT_SUPPORT_COUNT, HARNESS_FAILED, EXPERIMENT_CONFIRMED, EXPERIMENT_REFUTED, NOT_ELIGIBLE.

## Worked examples (human to add >= 30 hand-labeled; see T-023)
TODO
