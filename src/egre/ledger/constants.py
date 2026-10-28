"""Constant facts extracted from textual ARM64 disassembly."""

from __future__ import annotations

import re
from collections.abc import Iterable

_MOV_IMMEDIATE = re.compile(
    r"\b(?P<mnemonic>mov|movz|movk)\s+"
    r"(?P<register>[wx](?:[12]?\d|3[01])),\s*"
    r"#(?P<immediate>-?(?:0x[0-9a-f]+|\d+))"
    r"(?:,\s*lsl\s*#(?P<shift>\d+))?",
    re.IGNORECASE,
)
_INSTRUCTION = re.compile(
    r"^\s*(?:(?:0x)?[0-9a-f]+:\s*)?"
    r"(?P<mnemonic>[a-z][a-z0-9.]*)\s*(?P<operands>.*)$",
    re.IGNORECASE,
)
_FIRST_REGISTER = re.compile(r"^(?P<register>[wx](?:[12]?\d|3[01]))\b", re.IGNORECASE)
_NO_DESTINATION = frozenset({"b", "bl", "blr", "br", "cmp", "cmn", "prfm", "ret", "tst"})
_NO_DESTINATION_PREFIX = ("b.", "cb", "st", "tb")


def _width(register: str) -> int:
    return 32 if register.lower().startswith("w") else 64


def _forget_register(register_values: dict[str, int], register: str) -> None:
    number = register[1:]
    register_values.pop(f"w{number}", None)
    register_values.pop(f"x{number}", None)


def _written_register(line: str) -> str | None:
    instruction = _INSTRUCTION.match(line)
    if instruction is None:
        return None
    mnemonic = instruction.group("mnemonic").lower()
    if mnemonic in _NO_DESTINATION or mnemonic.startswith(_NO_DESTINATION_PREFIX):
        return None
    first_operand = _FIRST_REGISTER.match(instruction.group("operands"))
    return first_operand.group("register").lower() if first_operand is not None else None


def extract_constants(disasm_lines: Iterable[str]) -> set[int]:
    """Extract immediate loads, reconstructing values patched by ARM64 ``movk``."""
    register_values: dict[str, int] = {}
    constants: set[int] = set()

    for line in disasm_lines:
        match = _MOV_IMMEDIATE.search(line)
        if match is None:
            written_register = _written_register(line)
            if written_register is not None:
                _forget_register(register_values, written_register)
            continue

        mnemonic = match.group("mnemonic").lower()
        register = match.group("register").lower()
        width = _width(register)
        mask = (1 << width) - 1
        immediate = int(match.group("immediate"), 0)
        shift_text = match.group("shift")
        shift = int(shift_text) if shift_text is not None else 0

        if mnemonic == "movk":
            previous = register_values.get(register, 0)
            halfword_mask = 0xFFFF << shift
            value = (previous & ~halfword_mask) | ((immediate & 0xFFFF) << shift)
        else:
            _forget_register(register_values, register)
            value = immediate << shift

        value &= mask
        register_values[register] = value
        constants.add(value)

    return constants

