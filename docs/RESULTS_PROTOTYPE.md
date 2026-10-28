# Prototype local-model results

These results come from 21 completed runs: seven corpus programs with three repeats each. The immutable working copy is `runs/ollama-qwen3.5-4b-final`.

## Run configuration

| Setting | Value |
| --- | --- |
| Model | `qwen3.5:4b` |
| Endpoint | `http://localhost:11434/v1` |
| Temperature | `0.2` |
| Maximum output tokens per response | `700` |
| Request timeout | `120.0` seconds |

All 21 run files report the same configuration. Across the batch, the endpoint reported 152,970 prompt tokens, 41,736 completion tokens and 194,706 total tokens.

## Evaluation

```text
Support x truth
support       true  false
entailed         6      0
insufficient    17      2

Gate views
view  claims  true  false  precision  coverage
C1        25    23      2      92.0%     90.5%
C2         6     6      0     100.0%     23.8%
C3        23    23      0     100.0%     90.5%

Total claims: 25
Zero-claim runs: 2
Total invalid steps: 46
```

C1 includes every registered claim. C2 retains only claims mechanically entailed by their cited evidence. C3 retains claims confirmed by the independent native experiment. On this small batch, C3 removed both false claims without reducing coverage relative to C1. C2 was also perfectly precise, but retained only six claims and had substantially lower coverage. These are prototype-corpus results, not a claim about general reverse-engineering performance.

## Manual run inspection

- `crc32_obfpoly-repeat-001`: the model correctly claimed `crc32`, citing `obs-000001`, a `read_memory` observation. It never called `run`. The cited bytes did not satisfy the signature-evidence rule, so support was `insufficient` with `NO_SIGNATURE_EVIDENCE`; the independent experiment confirmed the claim and assigned `verified` with `support_gap=true`.
- `fnv1a_crcdecoy-repeat-001`: the model correctly claimed `fnv1a32`, citing `obs-000001`, a `read_memory` observation. It never called `run`. The citation did not satisfy either support rule, so the claim was `insufficient` with `NO_SIGNATURE_EVIDENCE`; the independent experiment confirmed it and assigned `verified` with `support_gap=true`.
- `djb2_fnvdecoy-repeat-001`: the model made nine invalid oversized `read_memory` calls, then successfully disassembled the function as `obs-000001`. It tried to claim the out-of-taxonomy primitive `combined_hash`, so no claim was registered before the 12-step limit. It never called `run`. The disassembly contained both the real djb2 constant and dead-branch FNV constants, but the run ended with zero accepted claims and 11 invalid steps.
- False-claim check, `fnv1a_crcdecoy-repeat-002`: the registered `crc32` claim cited only `obs-000001`, a memory observation, and the model never called `run`. The claim was `insufficient` with `NO_SIGNATURE_EVIDENCE`, then the independent experiment refuted it. The same run also registered a false `adler32` claim with the same citation and outcome. Its true `fnv1a32` claim was independently confirmed.

The inspected traces show why the independent experiment matters: the local model often inferred a primitive from static bytes without collecting the two run observations required for behavioral support. The registry, evidence checker and experiment preserved those distinctions rather than treating model confidence as a verdict.
