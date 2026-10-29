"""Build the protected prototype corpus into stripped, signed arm64 executables."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

import lief

ROOT = Path(__file__).resolve().parents[3]
CORPUS = ROOT / "corpus"
CATALOG = CORPUS / "catalog.json"
BUILD_DIR = CORPUS / "build"
BIN_DIR = CORPUS / "bin"
TASK_DIR = CORPUS / "tasks"
PRIMITIVES = ["crc32", "fnv1a32", "adler32", "djb2", "other"]


class BuildError(RuntimeError):
    """Raised when a corpus executable cannot be built or inspected."""


def _run(*args: str) -> None:
    subprocess.run(args, cwd=ROOT, check=True)


def _target_range(binary_path: Path) -> tuple[int, int]:
    binary = lief.parse(binary_path)
    if not isinstance(binary, lief.MachO.Binary):
        raise BuildError(f"could not parse thin Mach-O binary: {binary_path}")

    text = binary.get_section("__text")
    if text is None:
        raise BuildError(f"binary has no __text section: {binary_path}")

    target = next((symbol for symbol in binary.symbols if symbol.name == "_target"), None)
    if target is None or target.value == 0:
        raise BuildError(f"binary has no _target symbol: {binary_path}")

    text_end = text.virtual_address + text.size
    boundaries = [
        symbol.value
        for symbol in binary.symbols
        if target.value < symbol.value <= text_end
    ]
    function_end = min(boundaries, default=text_end)
    function_size = function_end - target.value
    if function_size <= 0:
        raise BuildError(f"could not determine _target size: {binary_path}")
    return target.value, function_size


def _opt_flag(entry: dict[str, Any]) -> str:
    opt = entry.get("opt", "O0")
    if opt not in ("O0", "O2"):
        raise BuildError(f"unsupported optimization level {opt!r} for {entry.get('name')!r}")
    return opt


def _task(program: str, function_addr: int, function_size: int) -> dict[str, Any]:
    return {
        "program": program,
        "binary": f"corpus/bin/{program}",
        "function_addr": function_addr,
        "function_size": function_size,
        "signature": "u32 f(const u8*,size_t)",
        "primitives": PRIMITIVES,
    }


def build() -> None:
    catalog = json.loads(CATALOG.read_text())
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    BIN_DIR.mkdir(parents=True, exist_ok=True)
    TASK_DIR.mkdir(parents=True, exist_ok=True)

    for entry in catalog:
        program = entry["name"]
        source = ROOT / entry["source"]
        unstripped = BUILD_DIR / program
        destination = BIN_DIR / program
        opt = _opt_flag(entry)

        _run(
            "clang",
            "-arch",
            "arm64",
            f"-{opt}",
            f"-I{CORPUS / 'src'}",
            str(source),
            "-o",
            str(unstripped),
        )
        function_addr, function_size = _target_range(unstripped)
        _run("strip", str(unstripped))
        _run("codesign", "--force", "--sign", "-", str(unstripped))
        os.replace(unstripped, destination)

        task_path = TASK_DIR / f"{program}.json"
        task_path.write_text(
            json.dumps(_task(program, function_addr, function_size), indent=2) + "\n"
        )


if __name__ == "__main__":
    build()
