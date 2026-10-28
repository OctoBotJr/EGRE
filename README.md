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

## Docs
PROJECT_SPEC · ARCHITECTURE · CLAIM_TAXONOMY · EVALUATION_PLAN · RESEARCH_NOTES · DECISIONS · SETUP
