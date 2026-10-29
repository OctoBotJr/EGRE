import json
from pathlib import Path

import pytest

from egre.graph.cfg import build_function_cfg
from egre.runner.executor import run_program
from egre.runner.refs import REFERENCE_INPUTS
from egre.tracer.emulate import Tracer, TracerError, blocks_touched, trace_function

pytestmark = pytest.mark.toolchain

ROOT = Path(__file__).resolve().parents[2]
PROGRAMS = (
    "adler32_clean",
    "crc32_clean",
    "crc32_obfpoly",
    "djb2_clean",
    "djb2_fnvdecoy",
    "fnv1a_clean",
    "fnv1a_crcdecoy",
)


def _task(program: str) -> dict[str, object]:
    return json.loads((ROOT / "corpus" / "tasks" / f"{program}.json").read_text())


@pytest.mark.parametrize("program", PROGRAMS)
def test_trace_output_matches_native_on_every_reference_vector(program: str) -> None:
    task = _task(program)
    addr, size, binary = task["function_addr"], task["function_size"], task["binary"]
    assert isinstance(addr, int) and isinstance(size, int)
    tracer = Tracer(ROOT / str(binary), addr, size)

    for input_hex in REFERENCE_INPUTS:
        native = run_program(ROOT / str(binary), input_hex)
        result = tracer.trace(bytes.fromhex(input_hex))
        assert result.output == native, f"{program} {input_hex!r}: {result.output:#x} != {native:#x}"


@pytest.mark.parametrize("program", ["fnv1a_crcdecoy", "djb2_fnvdecoy"])
def test_dead_branch_block_is_never_covered_for_a_non_triggering_input(program: str) -> None:
    task = _task(program)
    addr, size, binary = task["function_addr"], task["function_size"], task["binary"]
    assert isinstance(addr, int) and isinstance(size, int)
    cfg = build_function_cfg(ROOT / str(binary), addr, size)
    tracer = Tracer(ROOT / str(binary), addr, size)

    result = tracer.trace(b"\x61")
    touched = blocks_touched(result, cfg)

    live_block_count = len(cfg.blocks) - 1
    assert len(touched) <= live_block_count
    assert touched != {block.start for block in cfg.blocks}


def test_trace_function_one_shot_matches_class_based_tracer() -> None:
    task = _task("crc32_clean")
    addr, size, binary = task["function_addr"], task["function_size"], task["binary"]
    assert isinstance(addr, int) and isinstance(size, int)

    result = trace_function(ROOT / str(binary), addr, size, b"abc")

    assert result.output == run_program(ROOT / str(binary), "616263")


def test_tracer_rejects_a_function_outside_every_mapped_segment() -> None:
    task = _task("crc32_clean")
    binary = task["binary"]

    with pytest.raises(TracerError, match="not inside any mapped segment"):
        Tracer(ROOT / str(binary), 0x999999000, 16)


def test_trace_raises_when_the_instruction_budget_is_exhausted() -> None:
    task = _task("crc32_clean")
    addr, size, binary = task["function_addr"], task["function_size"], task["binary"]
    assert isinstance(addr, int) and isinstance(size, int)
    tracer = Tracer(ROOT / str(binary), addr, size)

    with pytest.raises(TracerError, match="did not return"):
        tracer.trace(b"abc", max_instructions=1)
