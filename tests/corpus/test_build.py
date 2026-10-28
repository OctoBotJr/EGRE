from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
CATALOG = json.loads((ROOT / "corpus/catalog.json").read_text())
VECTORS = json.loads((ROOT / "corpus/reference_vectors.json").read_text())
EXPECTED_PROGRAMS = {entry["name"] for entry in CATALOG}
PRIMITIVES = ["crc32", "fnv1a32", "adler32", "djb2", "other"]


def _all_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {key for child in value.values() for key in _all_keys(child)}
    if isinstance(value, list):
        return {key for child in value for key in _all_keys(child)}
    return set()


@pytest.mark.toolchain
def test_build_produces_signed_arm64_macho_binaries() -> None:
    binaries = sorted((ROOT / "corpus/bin").iterdir())
    assert {path.name for path in binaries} == EXPECTED_PROGRAMS

    for binary in binaries:
        assert binary.is_file()
        assert binary.stat().st_mode & 0o111
        description = subprocess.run(
            ["file", str(binary)], check=True, capture_output=True, text=True
        ).stdout
        assert "Mach-O 64-bit executable arm64" in description
        symbols = subprocess.run(
            ["nm", str(binary)], check=True, capture_output=True, text=True
        ).stdout
        assert "_target" not in symbols
        subprocess.run(["codesign", "--verify", "--strict", str(binary)], check=True)


@pytest.mark.toolchain
def test_native_outputs_match_independent_reference_vectors() -> None:
    truth_by_program = {
        entry["name"]: json.loads((ROOT / f"corpus/truth/{entry['name']}.json").read_text())[
            "primitive"
        ]
        for entry in CATALOG
    }

    for program, primitive in truth_by_program.items():
        binary = ROOT / "corpus/bin" / program
        for input_hex, expected in zip(
            VECTORS["inputs_hex"], VECTORS["expected"][primitive], strict=True
        ):
            result = subprocess.run(
                [str(binary), input_hex], check=True, capture_output=True, text=True, timeout=5
            )
            assert result.stdout.strip() == expected, (program, input_hex)


@pytest.mark.toolchain
def test_agent_tasks_have_fixed_schema_and_no_truth_fields() -> None:
    task_paths = sorted((ROOT / "corpus/tasks").glob("*.json"))
    assert {path.stem for path in task_paths} == EXPECTED_PROGRAMS

    forbidden = {"truth", "truth_primitive", "primitive", "variant", "function_symbol"}
    expected_keys = {
        "program",
        "binary",
        "function_addr",
        "function_size",
        "signature",
        "primitives",
    }
    for task_path in task_paths:
        task = json.loads(task_path.read_text())
        assert set(task) == expected_keys
        assert not (_all_keys(task) & forbidden)
        assert task["program"] == task_path.stem
        assert task["binary"] == f"corpus/bin/{task_path.stem}"
        assert isinstance(task["function_addr"], int) and task["function_addr"] > 0
        assert isinstance(task["function_size"], int) and task["function_size"] > 0
        assert task["signature"] == "u32 f(const u8*,size_t)"
        assert task["primitives"] == PRIMITIVES
