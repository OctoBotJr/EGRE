"""Control-flow graph of one target function, from its full ARM64 disassembly.

System-side and deterministic: unlike the agent-facing ``disassemble`` tool,
this decodes the whole function up front, independent of what the agent
chooses to inspect. Used by the evidence graph builder (block membership of
constants) and the tracer (block coverage).
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

import capstone
import lief

_UNCONDITIONAL_BRANCH = frozenset({"b", "br"})
_CONDITIONAL_BRANCH_EXACT = frozenset({"cbz", "cbnz", "tbz", "tbnz"})
_RETURN = frozenset({"ret"})
_TARGET = re.compile(r"(0x[0-9a-fA-F]+)\s*$")


class CfgError(RuntimeError):
    """The function's bytes could not be decoded into a control-flow graph."""


def _is_conditional_branch(mnemonic: str) -> bool:
    return mnemonic in _CONDITIONAL_BRANCH_EXACT or mnemonic.startswith("b.")


def _branch_target(op_str: str) -> int | None:
    match = _TARGET.search(op_str)
    return int(match.group(1), 16) if match else None


@dataclass(frozen=True, slots=True)
class CfgInstruction:
    """One decoded instruction, independent of the agent-facing ledger."""

    address: int
    size: int
    mnemonic: str
    op_str: str

    def line(self) -> str:
        return f"{self.address:#x}: {self.mnemonic} {self.op_str}".rstrip()


@dataclass(frozen=True, slots=True)
class BasicBlock:
    """A maximal straight-line instruction run with one set of successors."""

    start: int
    end: int  # exclusive
    instructions: tuple[CfgInstruction, ...]
    successors: tuple[int, ...]  # successor block start addresses, within the function

    @property
    def id(self) -> str:
        return f"bb:{self.start:#x}"

    def contains(self, addr: int) -> bool:
        return self.start <= addr < self.end

    def disasm_lines(self) -> tuple[str, ...]:
        return tuple(instruction.line() for instruction in self.instructions)


@dataclass(frozen=True, slots=True)
class ControlFlowGraph:
    """The target function's basic blocks, covering [function_addr, function_end)."""

    function_addr: int
    function_end: int
    blocks: tuple[BasicBlock, ...]

    def block_containing(self, addr: int) -> BasicBlock | None:
        for block in self.blocks:
            if block.contains(addr):
                return block
        return None


def _decode(content: bytes, function_addr: int) -> tuple[CfgInstruction, ...]:
    disassembler = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_LITTLE_ENDIAN)
    instructions = tuple(disassembler.disasm(content, function_addr))
    if not instructions:
        raise CfgError(f"disassembler produced no instructions at {function_addr:#x}")
    return tuple(
        CfgInstruction(instruction.address, instruction.size, instruction.mnemonic, instruction.op_str)
        for instruction in instructions
    )


def _leaders(
    instructions: tuple[CfgInstruction, ...], function_addr: int, function_end: int
) -> list[int]:
    leaders = {function_addr}
    for instruction in instructions:
        mnemonic = instruction.mnemonic.lower()
        is_branch = mnemonic in _UNCONDITIONAL_BRANCH or _is_conditional_branch(mnemonic)
        is_terminator = is_branch or mnemonic in _RETURN
        if is_branch:
            target = _branch_target(instruction.op_str)
            if target is not None and function_addr <= target < function_end:
                leaders.add(target)
        if is_terminator:
            fallthrough = instruction.address + instruction.size
            if fallthrough < function_end:
                leaders.add(fallthrough)
    return sorted(leaders)


def _successors(
    instruction: CfgInstruction, function_addr: int, function_end: int
) -> tuple[int, ...]:
    mnemonic = instruction.mnemonic.lower()
    fallthrough = instruction.address + instruction.size
    if mnemonic in _RETURN or mnemonic == "br":
        return ()
    if mnemonic in _UNCONDITIONAL_BRANCH:
        target = _branch_target(instruction.op_str)
        if target is not None and function_addr <= target < function_end:
            return (target,)
        return ()
    if _is_conditional_branch(mnemonic):
        successors = [
            target
            for target in (_branch_target(instruction.op_str),)
            if target is not None and function_addr <= target < function_end
        ]
        if fallthrough < function_end:
            successors.append(fallthrough)
        return tuple(successors)
    return (fallthrough,) if fallthrough < function_end else ()


def build_cfg(content: bytes, function_addr: int, function_size: int) -> ControlFlowGraph:
    """Build a CFG for one function from its raw bytes.

    ``content`` must be exactly the function's bytes, starting at ``function_addr``.
    """
    function_end = function_addr + function_size
    instructions = _decode(content, function_addr)
    leaders = _leaders(instructions, function_addr, function_end)

    blocks: list[BasicBlock] = []
    leader_index = 0
    current: list[CfgInstruction] = []
    for instruction in instructions:
        if (
            leader_index + 1 < len(leaders)
            and instruction.address == leaders[leader_index + 1]
        ):
            blocks.append(_finish_block(leaders[leader_index], current, function_addr, function_end))
            leader_index += 1
            current = []
        current.append(instruction)
    if current:
        blocks.append(_finish_block(leaders[leader_index], current, function_addr, function_end))

    return ControlFlowGraph(
        function_addr=function_addr, function_end=function_end, blocks=tuple(blocks)
    )


def _finish_block(
    start: int, instructions: list[CfgInstruction], function_addr: int, function_end: int
) -> BasicBlock:
    end = instructions[-1].address + instructions[-1].size
    successors = _successors(instructions[-1], function_addr, function_end)
    return BasicBlock(
        start=start, end=end, instructions=tuple(instructions), successors=successors
    )


def build_function_cfg(
    binary_path: str | os.PathLike[str], function_addr: int, function_size: int
) -> ControlFlowGraph:
    """Build a CFG for the target function directly from a stripped Mach-O binary."""
    binary = lief.parse(Path(binary_path))
    if not isinstance(binary, lief.MachO.Binary):
        raise CfgError(f"could not parse thin Mach-O binary: {binary_path}")
    content = bytes(binary.get_content_from_virtual_address(function_addr, function_size))
    return build_cfg(content, function_addr, function_size)
