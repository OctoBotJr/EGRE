# EGRE — Evidence-Grounded Reverse Engineering

Claim-level evidence auditing and gating for LLM reverse-engineering agents.
Central question: *how often are an agent's conclusions entailed by the observations it
obtained, how does that differ from whether they are true, and can an evidence gate with
active verification improve it without collapsing coverage?*

## Quick start (native macOS, Apple Silicon)
```bash
xcode-select --install && brew bundle
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,re]"
./scripts/verify.sh
GHIDRA_URL=<release zip url> ./scripts/setup_ghidra.sh     # then add the exports it prints to ~/.zshrc
./scripts/check_env.sh && ./scripts/smoke_env.sh           # see docs/SETUP.md
```

## Developing with Codex (loop engineering)
- Loop protocol: docs/LOOP.md. Task queue: docs/TASKS.md. State: docs/STATUS.md, docs/PROGRESS.md.
- Supervised iteration:  `MAX_ITERS=1 ./scripts/loop.sh`
- Unattended batch:      `MAX_ITERS=5 ./scripts/loop.sh`
- With toolchain tests:  `VERIFY_CMD="./scripts/verify.sh --full" MAX_ITERS=1 ./scripts/loop.sh`
- The loop stops at human gates (design decisions, API spend, freeze). See docs/GUARDRAILS.md.

## Prototype demo

The offline demo runs three deterministic scripted policies over all seven corpus programs,
checks each claim against its cited observations, independently executes the binary on test
vectors, and prints the support/truth matrix plus three gate views. It needs no API key.

```bash
source .venv/bin/activate
python -m egre.demo
```

The verified prototype output is:

```text
Support x truth
support       true  false
entailed        14      3
insufficient     1      4

Gate views
view  claims  true  false  precision  coverage
C1        22    15      7      68.2%     71.4%
C2        17    14      3      82.4%     66.7%
C3        15    15      0     100.0%     71.4%
```

Here C1 includes every submitted claim, C2 keeps only evidence-supported claims, and C3
keeps only experimentally verified claims. The result demonstrates both intended failure
modes: evidence support can preserve false claims, while a correct claim can have an evidence
gap. The full verified-only gate removes all false claims in this corpus. The command also
writes the complete 21-run result to `runs/demo.json`.

Prototype limitations:

- The corpus contains seven benign synthetic programs compiled for native macOS arm64 at
  `-O0`; it is not representative of production reverse-engineering workloads.
- Only one typed claim is evaluated: “the function at address A implements hash primitive P,”
  where P is CRC-32, FNV-1a, Adler-32, djb2, or `other`.
- Experiments execute the program natively under a no-network wrapper. They are function-level
  evidence, but they are not Unicorn or instruction-level emulation.
- The demonstrated agents are deterministic scripted policies. The optional paid real-LLM
  experiment (P-08) has been deferred and no real-provider result is claimed here.
- Static support is intentionally syntactic: a signature constant in dead code can support a
  false claim, and an obfuscated implementation can lose evidence coverage.

## Docs
PROJECT_SPEC · ARCHITECTURE · CLAIM_TAXONOMY · EVALUATION_PLAN · RESEARCH_NOTES · DECISIONS · SETUP
