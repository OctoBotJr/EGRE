import json
from pathlib import Path

import pytest

from egre.graph.cfg import CfgError, build_cfg, build_function_cfg
from egre.ledger.constants import extract_constants

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
def test_blocks_tile_the_function_with_no_gaps_or_overlaps(program: str) -> None:
    task = _task(program)
    addr = task["function_addr"]
    size = task["function_size"]
    assert isinstance(addr, int) and isinstance(size, int)

    cfg = build_function_cfg(ROOT / str(task["binary"]), addr, size)

    assert cfg.blocks[0].start == addr
    assert cfg.blocks[-1].end == addr + size
    for first, second in zip(cfg.blocks, cfg.blocks[1:]):
        assert first.end == second.start
    block_starts = {block.start for block in cfg.blocks}
    for block in cfg.blocks:
        for successor in block.successors:
            assert successor in block_starts


def test_dead_branch_constant_is_isolated_in_its_own_block() -> None:
    task = _task("fnv1a_crcdecoy")
    addr = task["function_addr"]
    size = task["function_size"]
    assert isinstance(addr, int) and isinstance(size, int)

    cfg = build_function_cfg(ROOT / str(task["binary"]), addr, size)

    dead_blocks = [
        block
        for block in cfg.blocks
        if 0xEDB88320 in extract_constants(block.disasm_lines())
    ]
    assert len(dead_blocks) == 1
    dead_block = dead_blocks[0]
    assert dead_block.start != cfg.function_addr
    assert len(dead_block.instructions) < sum(len(block.instructions) for block in cfg.blocks)
    assert len(cfg.blocks) > 1
    all_other_constants = {
        constant
        for block in cfg.blocks
        if block is not dead_block
        for constant in extract_constants(block.disasm_lines())
    }
    assert 0xEDB88320 not in all_other_constants


def test_build_cfg_raises_on_empty_content() -> None:
    with pytest.raises(CfgError):
        build_cfg(b"", 0x1000, 16)
