#!/usr/bin/env bash
# Fail if any protected path was modified, added or deleted in the working tree.
set -euo pipefail
cd "$(dirname "$0")/.."
[[ "${ALLOW_PROTECTED:-0}" == "1" ]] && { echo "[protected] override enabled"; exit 0; }
changed=$(git status --porcelain | sed -E 's/^.{3}//; s/.* -> //')
bad=0
while IFS= read -r pat; do
  [[ -z "$pat" || "$pat" == \#* ]] && continue
  while IFS= read -r f; do
    [[ -z "$f" ]] && continue
    if [[ "$f" == "$pat" || ( "$pat" == */ && "$f" == "$pat"* ) ]]; then
      echo "[protected] violation: $f"; bad=1
    fi
  done <<< "$changed"
done < scripts/protected_paths.txt
exit $bad
