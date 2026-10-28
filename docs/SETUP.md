# SETUP — native macOS (Apple Silicon), no Docker (human-run; task T-002)

Everything runs on the Mac. The corpus is Mach-O arm64 built with Apple clang (decision D-009).
Not available on macOS and therefore not used: gdb, strace, ltrace (D-012). angr is optional (D-011).

## 1. Prerequisites
    xcode-select --install                  # clang, strip, codesign, otool, lldb, make
    brew bundle                              # python@3.12, radare2, gradle, temurin@21 (see Brewfile)

## 2. Python environment
    python3.12 -m venv .venv && source .venv/bin/activate
    pip install --retries 10 --timeout 60 -e ".[dev,re]"
    ./scripts/verify.sh                      # expect: ruff, mypy, 13 tests pass
(Optional, experimental: `pip install -e ".[symbolic]"` for angr.)

## 3. Ghidra — SKIP for the prototype (D-016). Only follow this if you add Ghidra later (JDK 21+ required by Ghidra 12.1)
1. Copy the `.zip` link of the latest release from https://github.com/NationalSecurityAgency/ghidra/releases
2. `export GHIDRA_URL="<link>"`
3. `./scripts/setup_ghidra.sh`              # downloads to ~/tools, clears quarantine, tries to build the native decompiler
4. Add the two `export` lines it prints (GHIDRA_INSTALL_DIR, JAVA_HOME) to ~/.zshrc; open a new terminal.

## 4. Verify
    source .venv/bin/activate
    ./scripts/check_env.sh | tee docs/ENV_VERSIONS.md
    ./scripts/smoke_env.sh                   # expect: SMOKE PASSED

## 5. Close T-002
Set T-002 to `done` in docs/TASKS.md, remove it from `human_gates_pending` in docs/STATUS.md,
append a note to docs/PROGRESS.md, commit.

## Ghidra natives
Official 12.1.x releases may not ship a macOS arm64 native decompiler; it can be built locally
(needs Xcode CLT, make, JDK 21, Gradle 8.5+). setup_ghidra.sh tries `support/buildNatives`.
If check_env reports the decompiler missing: read the build error, check Ghidra's Getting Started ->
"Building Native Components". If it cannot be fixed quickly, continue without Ghidra (radare2 + Capstone +
Unicorn) and add it later as its own task (D-010). If macOS blocks the binary, clear quarantine:
`xattr -dr com.apple.quarantine <ghidra dir>`.

## Notes
- After `strip`, Mach-O binaries must be re-signed (`codesign --force --sign - <bin>`) or macOS kills them.
- `sandbox-exec` (no-network wrapper) is deprecated but present; smoke_env.sh tests that it blocks network.
- API keys: environment variables only; never committed. Set provider spend limits.
- Codex's own sandbox may not reach Ghidra/JDK paths outside the repo. Toolchain tests are therefore run by
  loop.sh from your shell: `VERIFY_CMD="./scripts/verify.sh --full" ./scripts/loop.sh`.
