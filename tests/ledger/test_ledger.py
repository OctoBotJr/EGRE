from dataclasses import FrozenInstanceError

import pytest

from egre.ledger.constants import extract_constants
from egre.ledger.store import Anchor, Ledger, UnknownHandleError

pytestmark = pytest.mark.toolchain


def test_extract_constants_reconstructs_arm64_mov_sequences() -> None:
    lines = [
        "0x1000: mov w8, #0x8320",
        "0x1004: movk w8, #0xedb8, lsl #16",
        "0x1008: mov w9, #0x9dc5",
        "0x100c: movk w9, #0x811c, lsl #16",
        "0x1010: mov w10, #0x193",
        "0x1014: movk w10, #0x100, lsl #16",
        "0x1018: mov w11, #5381",
        "0x101c: mov w12, #65521",
    ]

    constants = extract_constants(lines)

    assert {0xEDB88320, 0x811C9DC5, 0x01000193, 5381, 65521} <= constants


def test_extract_constants_respects_register_overwrites() -> None:
    lines = [
        "mov w8, #0x8320",
        "mov w8, #7",
        "movk w8, #0xedb8, lsl #16",
        "mov w9, #-1",
    ]

    constants = extract_constants(lines)

    assert 0xEDB80007 in constants
    assert 0xEDB88320 not in constants
    assert 0xFFFFFFFF in constants


def test_extract_constants_does_not_join_across_other_register_writes() -> None:
    constants = extract_constants(
        [
            "mov w8, #0x8320",
            "add w8, w8, #1",
            "movk w8, #0xedb8, lsl #16",
        ]
    )

    assert 0xEDB88320 not in constants


def test_ledger_is_append_only_and_reader_has_no_write_capability() -> None:
    ledger = Ledger()
    observation = ledger.record(
        kind="disasm",
        tool="disassemble",
        args={"addr": 0x1000, "count": 2},
        anchor=Anchor(start=0x1000, end=0x1008),
        payload="0x1000: mov w8, #5381",
        facts={5381},
    )
    reader = ledger.reader()

    assert observation.handle == "obs-000001"
    assert reader.get(observation.handle) is observation
    assert reader.all() == (observation,)
    assert not hasattr(reader, "record")
    with pytest.raises(UnknownHandleError, match="unknown observation handle"):
        reader.get("obs-does-not-exist")
    with pytest.raises(FrozenInstanceError):
        observation.payload = "changed"  # type: ignore[misc]
    with pytest.raises(TypeError):
        observation.args["addr"] = 0  # type: ignore[index]

