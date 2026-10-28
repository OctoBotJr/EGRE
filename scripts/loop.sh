#!/usr/bin/env bash
# Outer loop: one fresh Codex session per iteration; commit only verified work.
# Usage: MAX_ITERS=1 ./scripts/loop.sh   (supervised)   |   MAX_ITERS=5 ./scripts/loop.sh
# Check `codex exec --help` for your version's flags (sandbox / approval mode). Set CODEX_CMD accordingly.
set -euo pipefail
cd "$(dirname "$0")/.."
MAX_ITERS="${MAX_ITERS:-3}"
CODEX_CMD="${CODEX_CMD:-codex exec}"
# Full verification incl. toolchain tests (native macOS):
#   VERIFY_CMD="./scripts/verify.sh --full" ./scripts/loop.sh   (needs GHIDRA_INSTALL_DIR etc.)
VERIFY_CMD="${VERIFY_CMD:-./scripts/verify.sh}"
PROMPT='Follow AGENTS.md and docs/LOOP.md. Execute exactly ONE iteration (orient, plan, build, verify, review, record, signal). Do not commit.'
mkdir -p runs/loop

for i in $(seq 1 "$MAX_ITERS"); do
  if [[ -n "$(git status --porcelain)" ]]; then echo "Dirty tree before iteration $i; commit or stash first."; exit 1; fi
  echo "== iteration $i/$MAX_ITERS =="
  # shellcheck disable=SC2086
  $CODEX_CMD "$PROMPT" | tee "runs/loop/iter-$(date +%Y%m%d-%H%M%S)-$i.log"
  ./scripts/check_protected.sh || { echo "Protected-path violation. Changes left for review."; exit 3; }
  $VERIFY_CMD                  || { echo "Verify failed. Changes left for review.";            exit 2; }
  signal=$(grep -m1 -E '^loop_signal:' docs/STATUS.md | awk '{print $2}')
  task=$(grep -m1 -E '^last_task:' docs/STATUS.md | awk '{print $2}')
  if [[ -n "$(git status --porcelain)" ]]; then git add -A && git commit -q -m "loop iter $i: ${task:-unknown}"; fi
  case "$signal" in
    CONTINUE) ;;
    *) echo "Stopping: ${signal:-no signal}"; exit 0 ;;
  esac
done
echo "Reached MAX_ITERS=$MAX_ITERS"
