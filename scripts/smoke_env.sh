#!/usr/bin/env bash
# Native macOS smoke test: ./scripts/smoke_env.sh  (T-003 later formalizes this as pytest tests)
set -euo pipefail
W=$(mktemp -d); trap 'rm -rf "$W"' EXIT
cat > "$W/toy.c" <<'C'
#include <stdio.h>
int check(int x) { return x * 3 == 12; }
int main(int argc, char **argv) { (void)argv; printf("%d\n", check(argc + 3)); return 0; }
C
echo "[1] compile, strip, re-sign"
clang -arch arm64 -O0 -o "$W/toy" "$W/toy.c"
cp "$W/toy" "$W/toy_stripped"; strip "$W/toy_stripped"; codesign --force --sign - "$W/toy_stripped"
file "$W/toy_stripped" | grep -q "Mach-O 64-bit executable arm64" && echo "    Mach-O arm64 OK"
echo "[2] run natively";   "$W/toy_stripped"
echo "[3] otool";          otool -tv "$W/toy_stripped" | head -n 3 >/dev/null && echo "    OK"
echo "[4] radare2 (optional)"; if command -v r2 >/dev/null; then r2 -qc 'aaa; afl' "$W/toy_stripped" | head -n 3; fi
echo "[6] no-network wrapper (sandbox-exec)"
if sandbox-exec -p '(version 1)(allow default)(deny network*)' curl -sS -m 5 -o /dev/null https://example.com 2>/dev/null; then
  echo "    FAIL: network was reachable inside sandbox-exec"; exit 1
else echo "    network blocked OK"; fi
echo "[7] unicorn (arm64) emulation"
python3 - <<'PY'
from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_PROT_ALL
from unicorn.arm64_const import UC_ARM64_REG_X0, UC_ARM64_REG_X1
code = bytes.fromhex("0000018b" "c0035fd6")          # add x0,x0,x1 ; ret
mu = Uc(UC_ARCH_ARM64, UC_MODE_ARM); mu.mem_map(0x1000, 0x1000, UC_PROT_ALL); mu.mem_write(0x1000, code)
mu.reg_write(UC_ARM64_REG_X0, 2); mu.reg_write(UC_ARM64_REG_X1, 3)
mu.emu_start(0x1000, 0x1004); assert mu.reg_read(UC_ARM64_REG_X0) == 5; print("    unicorn OK")
PY
echo "[8] lief parses the Mach-O"
python3 - <<PY
import lief
r = lief.parse("$W/toy_stripped"); b = r.at(0) if hasattr(r, "at") else r
assert b is not None and any(s.name == "__text" for s in b.sections)
print("    lief OK")
PY
echo "SMOKE PASSED"
