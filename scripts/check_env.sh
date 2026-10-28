#!/usr/bin/env bash
# Native macOS (Apple Silicon) environment check. Exit 1 if a required item is missing.
cd "$(dirname "$0")/.."
missing=0
ok()   { echo "OK       $*"; }
bad()  { echo "MISSING  $*"; missing=1; }
warn() { echo "warn     $*"; }
tool() { # name cmd required(req|opt)
  if command -v "$2" >/dev/null 2>&1; then ok "$1: $("$2" --version 2>&1 | head -n1)"
  elif [[ "$3" == req ]]; then bad "$1 (required)"; else warn "$1 (optional) not found"; fi
}

echo "os: $(uname -s) $(uname -m)   $(sw_vers -productVersion 2>/dev/null)"
[[ "$(uname -s)" == Darwin && "$(uname -m)" == arm64 ]] && ok "macOS arm64" || bad "expected macOS arm64"
xcode-select -p >/dev/null 2>&1 && ok "Xcode CLT: $(xcode-select -p)" || bad "Xcode Command Line Tools (xcode-select --install)"
for t in git clang strip codesign otool make; do tool "$t" "$t" req; done
tool lldb lldb opt; tool sandbox-exec sandbox-exec req; tool radare2 r2 opt; tool gradle gradle opt

python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)' \
  && ok "python $(python3 --version 2>&1) (must be the venv python)" || bad "python >= 3.11 (activate .venv)"
[[ -n "${VIRTUAL_ENV:-}" ]] && ok "venv: $VIRTUAL_ENV" || warn "no venv active (source .venv/bin/activate)"

JBIN=java; [[ -n "${JAVA_HOME:-}" ]] && JBIN="$JAVA_HOME/bin/java"
jv=$("$JBIN" -version 2>&1 | awk -F'"' '/version/{print $2}' | cut -d. -f1)
if [[ "${jv:-}" =~ ^[0-9]+$ && "$jv" -ge 21 ]]; then ok "java $jv ($JBIN)"; else warn "JDK 21+ not found (only needed for Ghidra; skipped for the prototype)"; fi

G="${GHIDRA_INSTALL_DIR:-}"
if [[ -n "$G" && -x "$G/support/analyzeHeadless" ]]; then ok "ghidra (optional): $G"
else warn "ghidra not configured (optional; skipped for the prototype)"; fi

python3 - <<'PY'
import importlib, sys
req = ["pydantic","yaml","capstone","unicorn","r2pipe","lief","pytest","ruff","mypy"]
opt = ["angr"]
bad = 0
for m in req:
    try: importlib.import_module(m); print(f"OK       python:{m}")
    except Exception as e: print(f"MISSING  python:{m} ({e.__class__.__name__})"); bad = 1
for m in opt:
    try: importlib.import_module(m); print(f"OK       python:{m} (optional)")
    except Exception: print(f"warn     python:{m} (optional; pip install -e '.[symbolic]')")
sys.exit(bad)
PY
[[ $? -ne 0 ]] && missing=1
exit $missing
