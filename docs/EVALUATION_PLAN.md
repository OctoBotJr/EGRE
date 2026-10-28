# EVALUATION_PLAN (human-owned; protected)

## Corpus
Tier A ~60 generated programs (seeded templates; truth by construction). Tier B matched variants
with benign misleading evidence (dead code, decoy constants, unused tables, retained misleading
symbols). Tier C small open-source routines (ablation only; contamination caveat). Each program
built at -O0 and -O2, stripped and re-signed (ad hoc). The PROGRAM is the independent unit.

## Conditions (same tools, same budget)
C0 free-form agent, audited post hoc | C1 typed claims, ungated | C2 passive contract gate |
C3 full gate (contract + experiments + feedback) | C4 random-abstention control matched to C3's
removal rate | C5 optional LLM-judge verifier. Models: two frontier (+ optional open-weight).

## Metrics
support x truth matrix; unsupported-assertion rate; right-for-wrong-reason rate; verified-claim
precision; coverage; precision-coverage frontier; task success (executable checks).
Stats: clustered bootstrap by program; keep infra failures/malformed outputs in denominators.

## Gold set
>= 300 claims double-annotated for support; Cohen's kappa; compare contract checker and claim normalizer.

## Threats / controls
Judge circularity (no LLM judge in main pipeline) | contamination (generated + perturbed programs) |
format/architecture familiarity (corpus is Mach-O arm64; most prior RE-agent work uses ELF, models may know x86-64/ELF better; report as limitation) |
reproducibility on a host machine (mitigate: Brewfile, recorded versions in docs/ENV_VERSIONS.md, build hashes) |
abstention gaming (C4) | harness failure (inconclusive default) | tool nondeterminism (pinned versions, replay).

## Freeze protocol (T-101)
Before the main run freeze: prompts, contracts, tool and model versions, seeds, budgets, thresholds,
analysis code. Reproduce the pilot with one command from the frozen config.
