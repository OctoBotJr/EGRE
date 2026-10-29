"""Unicorn-based execution tracer for one target function (V2_SPEC.md section 4.1).

Emulates only the target function in isolation -- not the whole program --
to record which instruction addresses actually execute for one input. This
is the "executed" signal structural support needs under S2 (V2_SPEC.md
section 3.2): a cited constant only counts if the block holding it actually
ran in a traced run, not merely sits in the binary.

Calling convention: ``target(buf, len)`` takes its buffer in x0 and length
in x1 (AAPCS64), matches every v1/v2 corpus program's signature. LR is set
to an address no real `ret` could reach by chance; emulation stops the
instant PC reaches it, which is exactly when the function returns.

This module only emulates and reports. Comparing the result against the
real native executor and deciding what to do on a mismatch (record
tracer_mismatch, drop coverage, never change the output) is the auto-trace
wiring added in V-09, not here.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import lief
from unicorn import UC_ARCH_ARM64, UC_HOOK_CODE, UC_MODE_LITTLE_ENDIAN, UC_PROT_ALL, Uc, UcError
from unicorn.arm64_const import (
    UC_ARM64_REG_CPACR_EL1,
    UC_ARM64_REG_LR,
    UC_ARM64_REG_PC,
    UC_ARM64_REG_SP,
    UC_ARM64_REG_X0,
    UC_ARM64_REG_X1,
)

from egre.graph.cfg import ControlFlowGraph

_PAGE = 0x1000
_SKIP_SEGMENTS = frozenset({"__PAGEZERO", "__LINKEDIT"})
_SCRATCH_BASE = 0x500000000  # far above any realistic small Mach-O's mapped range
_SCRATCH_SIZE = 0x10000
_BUFFER_OFFSET = 0x1000
_STACK_TOP_OFFSET = 0x8000
_RETURN_SENTINEL = 0xFFFFFFFFFFFF0000
_FP_SIMD_ENABLE = 0x300000  # CPACR_EL1 FPEN = 0b11: full EL0/EL1 access to FP/SIMD
_DEFAULT_MAX_INSTRUCTIONS = 2_000_000


class TracerError(RuntimeError):
    """The emulator could not produce a trustworthy trace."""


def _align_up(value: int, boundary: int = _PAGE) -> int:
    return (value + boundary - 1) // boundary * boundary


@dataclass(frozen=True, slots=True)
class TraceResult:
    """One emulated run: its 32-bit output and the addresses it visited."""

    output: int
    executed_addresses: frozenset[int]


def blocks_touched(result: TraceResult, cfg: ControlFlowGraph) -> frozenset[int]:
    """Start addresses of ``cfg`` blocks that ``result`` actually entered."""
    return frozenset(
        block.start
        for block in cfg.blocks
        if any(block.start <= address < block.end for address in result.executed_addresses)
    )


class Tracer:
    """Parses a binary once; emulates its target function for many inputs."""

    def __init__(
        self, binary: str | os.PathLike[str], function_addr: int, function_size: int
    ) -> None:
        self._function_addr = function_addr
        binary_obj = lief.parse(Path(binary))
        if not isinstance(binary_obj, lief.MachO.Binary):
            raise TracerError(f"could not parse thin Mach-O binary: {binary}")

        self._segments: list[tuple[int, int, bytes]] = []
        for segment in binary_obj.segments:
            if str(segment.name) in _SKIP_SEGMENTS:
                continue
            start = segment.virtual_address
            size = _align_up(max(segment.virtual_size, 1))
            content = bytes(binary_obj.get_content_from_virtual_address(start, segment.virtual_size))
            self._segments.append((start, size, content.ljust(size, b"\x00")))

        function_end = function_addr + function_size
        if not any(start <= function_addr and function_end <= start + size for start, size, _ in self._segments):
            raise TracerError(f"function {function_addr:#x} is not inside any mapped segment")

    def trace(
        self, input_bytes: bytes, *, max_instructions: int = _DEFAULT_MAX_INSTRUCTIONS
    ) -> TraceResult:
        """Emulate the target function on ``input_bytes`` and return its trace."""
        engine = Uc(UC_ARCH_ARM64, UC_MODE_LITTLE_ENDIAN)
        for start, size, content in self._segments:
            engine.mem_map(start, size, UC_PROT_ALL)
            engine.mem_write(start, content)
        engine.mem_map(_SCRATCH_BASE, _SCRATCH_SIZE, UC_PROT_ALL)

        buffer_addr = _SCRATCH_BASE + _BUFFER_OFFSET
        engine.mem_write(buffer_addr, input_bytes if input_bytes else b"\x00")
        engine.reg_write(UC_ARM64_REG_X0, buffer_addr)
        engine.reg_write(UC_ARM64_REG_X1, len(input_bytes))
        engine.reg_write(UC_ARM64_REG_SP, _SCRATCH_BASE + _STACK_TOP_OFFSET)
        engine.reg_write(UC_ARM64_REG_LR, _RETURN_SENTINEL)
        engine.reg_write(UC_ARM64_REG_CPACR_EL1, _FP_SIMD_ENABLE)

        visited: list[int] = []
        engine.hook_add(UC_HOOK_CODE, lambda _engine, address, _size, _data: visited.append(address))

        try:
            engine.emu_start(self._function_addr, _RETURN_SENTINEL, timeout=0, count=max_instructions)
        except UcError as exc:
            raise TracerError(f"emulation faulted: {exc}") from exc

        if engine.reg_read(UC_ARM64_REG_PC) != _RETURN_SENTINEL:
            raise TracerError(f"function did not return within {max_instructions} instructions")

        output = engine.reg_read(UC_ARM64_REG_X0) & 0xFFFFFFFF
        return TraceResult(output=output, executed_addresses=frozenset(visited))


def trace_function(
    binary: str | os.PathLike[str],
    function_addr: int,
    function_size: int,
    input_bytes: bytes,
    *,
    max_instructions: int = _DEFAULT_MAX_INSTRUCTIONS,
) -> TraceResult:
    """One-shot convenience wrapper around :class:`Tracer`."""
    return Tracer(binary, function_addr, function_size).trace(
        input_bytes, max_instructions=max_instructions
    )
