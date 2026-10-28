#!/usr/bin/env bash
# Human-run. Installs Ghidra into ~/tools (or $1) and tries to build the macOS arm64 native decompiler.
# Usage: GHIDRA_URL=<release zip url> ./scripts/setup_ghidra.sh [dest_dir]
set -euo pipefail
: "${GHIDRA_URL:?Set GHIDRA_URL to the Ghidra release .zip link (GitHub releases page)}"
DEST="${1:-$HOME/tools}"; mkdir -p "$DEST"
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
echo "Downloading..."; curl -fL --retry 5 --retry-delay 3 -o "$tmp/ghidra.zip" "$GHIDRA_URL"
top=$(unzip -Z1 "$tmp/ghidra.zip" | head -n1 | cut -d/ -f1)
[[ -e "$DEST/$top" ]] && { echo "$DEST/$top already exists; remove it or pick another dir (do not extract over an existing install)."; exit 1; }
unzip -q "$tmp/ghidra.zip" -d "$DEST"
G="$DEST/$top"
xattr -dr com.apple.quarantine "$G" 2>/dev/null || true
echo "Installed: $G"

if find "$G/Ghidra/Features/Decompiler" -path '*os/mac_arm_64*' -name decompile 2>/dev/null | grep -q .; then
  echo "Native decompiler for mac_arm_64 already present."
else
  echo "Native decompiler missing for mac_arm_64; trying to build (needs Xcode CLT, JDK 21, gradle)..."
  export JAVA_HOME="$(/usr/libexec/java_home -v 21)"
  (cd "$G/support" && ./buildNatives) || echo "WARN: buildNatives failed. See docs/SETUP.md ('Ghidra natives')."
fi

cat <<MSG

Add these to ~/.zshrc, then open a new terminal:
  export GHIDRA_INSTALL_DIR="$G"
  export JAVA_HOME="\$(/usr/libexec/java_home -v 21)"
MSG
