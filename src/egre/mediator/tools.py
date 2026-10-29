"""Validated prototype reverse-engineering tools backed by the observation ledger."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import capstone
import lief

from egre.claims.schema import Claim
from egre.controller.status_v2 import reason_codes as _compute_reason_codes
from egre.graph.cfg import ControlFlowGraph, build_cfg
from egre.graph.evidence import bb_id, build_evidence_graph
from egre.knowledge.kb import load_kb_entries
from egre.knowledge.kb import lookup_knowledge as _lookup_knowledge
from egre.ledger.constants import extract_constants
from egre.ledger.store import Anchor, Ledger, LedgerReader, ObservationKind
from egre.runner.executor import run_program
from egre.support.engine import qualified_blocks
from egre.tracer.emulate import Tracer, TracerError, blocks_touched

_INPUT = re.compile(r"(?:[0-9a-fA-F]{2})*")
_MAX_INSTRUCTIONS = 256
_MAX_MEMORY_BYTES = 4096
_MAX_INPUT_BYTES = 4096
_QUERIES = frozenset({"constants_in", "executed_blocks", "observations"})


class ToolError(RuntimeError):
    """A validated tool could not produce an observation."""


class ToolValidationError(ToolError):
    """An agent tool request is malformed or outside the target function."""


@dataclass(frozen=True)
class ToolResult:
    """Compact agent-visible view of a recorded tool observation."""

    handle: str
    kind: ObservationKind
    anchor: Anchor
    content: str | int
    facts: frozenset[int]


def _required_int(task: Mapping[str, object], key: str) -> int:
    value = task.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ToolValidationError(f"task {key} must be an integer")
    return value


def _required_str(task: Mapping[str, object], key: str) -> str:
    value = task.get(key)
    if not isinstance(value, str) or not value:
        raise ToolValidationError(f"task {key} must be a non-empty string")
    return value


class MediatorTools:
    """Allowlisted tools; callers receive views, never ledger write access."""

    def __init__(
        self,
        task: Mapping[str, object],
        *,
        root: str | os.PathLike[str] = ".",
        ledger: Ledger | None = None,
    ) -> None:
        self._function_addr = _required_int(task, "function_addr")
        self._function_size = _required_int(task, "function_size")
        if self._function_addr < 0 or self._function_size <= 0:
            raise ToolValidationError("task function range must be non-empty and non-negative")

        self._root = Path(root)
        binary_value = _required_str(task, "binary")
        binary_path = Path(binary_value)
        self._binary_path = binary_path if binary_path.is_absolute() else self._root / binary_path
        self._ledger = ledger if ledger is not None else Ledger()
        self.observations: LedgerReader = self._ledger.reader()

        binary = lief.parse(self._binary_path)
        if not isinstance(binary, lief.MachO.Binary):
            raise ToolError(f"could not parse thin Mach-O binary: {self._binary_path}")
        self._binary = binary
        content = bytes(
            binary.get_content_from_virtual_address(self._function_addr, self._function_size)
        )
        self._cfg: ControlFlowGraph = build_cfg(content, self._function_addr, self._function_size)
        self._tracer: Tracer | None = None
        self._tracer_unavailable = False
        self._kb_entries: tuple[dict[str, object], ...] | None = None

    @property
    def _function_end(self) -> int:
        return self._function_addr + self._function_size

    def _validate_range(self, addr: int, size: int, *, max_size: int) -> None:
        if isinstance(addr, bool) or not isinstance(addr, int):
            raise ToolValidationError("address must be an integer")
        if isinstance(size, bool) or not isinstance(size, int) or not 1 <= size <= max_size:
            raise ToolValidationError(f"size must be between 1 and {max_size}")
        if addr < self._function_addr or addr + size > self._function_end:
            raise ToolValidationError("requested range is outside the target function")

    def disassemble(self, addr: int, count: int) -> ToolResult:
        if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= _MAX_INSTRUCTIONS:
            raise ToolValidationError(f"count must be between 1 and {_MAX_INSTRUCTIONS}")
        if isinstance(addr, bool) or not isinstance(addr, int) or addr % 4 != 0:
            raise ToolValidationError("address must be a four-byte-aligned integer")
        if not self._function_addr <= addr < self._function_end:
            raise ToolValidationError("address is outside the target function")

        available = self._function_end - addr
        content = bytes(self._binary.get_content_from_virtual_address(addr, available))
        disassembler = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_LITTLE_ENDIAN)
        instructions = tuple(disassembler.disasm(content, addr, count))
        if not instructions:
            raise ToolError("disassembler produced no instructions")

        lines = tuple(
            f"{instruction.address:#x}: {instruction.mnemonic} {instruction.op_str}".rstrip()
            for instruction in instructions
        )
        anchor = Anchor(start=addr, end=instructions[-1].address + instructions[-1].size)
        facts = frozenset(extract_constants(lines))
        payload = "\n".join(lines)
        observation = self._ledger.record(
            kind="disasm",
            tool="disassemble",
            args={"addr": addr, "count": count},
            anchor=anchor,
            payload=payload,
            facts=facts,
        )
        return ToolResult(observation.handle, observation.kind, anchor, payload, facts)

    def read_memory(self, addr: int, n: int) -> ToolResult:
        self._validate_range(addr, n, max_size=_MAX_MEMORY_BYTES)
        content = bytes(self._binary.get_content_from_virtual_address(addr, n))
        if len(content) != n:
            raise ToolError(f"binary returned {len(content)} bytes for a {n}-byte request")

        payload = content.hex()
        facts = frozenset(
            int.from_bytes(content[offset : offset + width], "little")
            for width in (2, 4, 8)
            for offset in range(0, len(content) - width + 1, width)
        )
        anchor = Anchor(start=addr, end=addr + n)
        observation = self._ledger.record(
            kind="memory",
            tool="read_memory",
            args={"addr": addr, "n": n},
            anchor=anchor,
            payload=payload,
            facts=facts,
        )
        return ToolResult(observation.handle, observation.kind, anchor, payload, facts)

    def run(self, input_hex: str) -> ToolResult:
        if not isinstance(input_hex, str) or _INPUT.fullmatch(input_hex) is None:
            raise ToolValidationError("input must be even-length hexadecimal")
        if len(input_hex) // 2 > _MAX_INPUT_BYTES:
            raise ToolValidationError(f"input must be at most {_MAX_INPUT_BYTES} bytes")

        output = run_program(self._binary_path, input_hex)
        coverage, tracer_mismatch = self._trace(input_hex, output)
        anchor = Anchor(start=self._function_addr, end=self._function_end)
        observation = self._ledger.record(
            kind="run",
            tool="run",
            args={"input_hex": input_hex},
            anchor=anchor,
            payload=output,
            coverage=coverage,
            tracer_mismatch=tracer_mismatch,
        )
        return ToolResult(
            observation.handle,
            observation.kind,
            anchor,
            output,
            frozenset(),
        )

    def _trace(self, input_hex: str, native_output: int) -> tuple[frozenset[int] | None, bool]:
        """Auto-trace a run (V2_SPEC.md section 4.1/4.4): coverage, or why there is none.

        Never raises and never changes ``native_output``: a tracer that
        fails or disagrees with the native executor is simply untrusted for
        this run (``tracer_mismatch=True``, no coverage), not a tool error.
        """
        if self._tracer_unavailable:
            return None, False
        if self._tracer is None:
            try:
                self._tracer = Tracer(self._binary_path, self._function_addr, self._function_size)
            except TracerError:
                self._tracer_unavailable = True
                return None, False
        try:
            result = self._tracer.trace(bytes.fromhex(input_hex))
        except TracerError:
            return None, True
        if result.output != native_output:
            return None, True
        return blocks_touched(result, self._cfg), False

    def query_graph(self, query: str, args: Mapping[str, object]) -> dict[str, object]:
        """Read-only evidence-graph lookups (V2_SPEC.md section 4.3, R2).

        Returns handles and facts the agent already has access to in digest
        form -- never a verdict, never a citation. Calling this never adds
        or changes what any claim cites (I8); the agent still has to cite
        handles itself in a later ``claim`` action. Every query is scoped to
        the task's one target function; there is no other function to ask
        about in this prototype.
        """
        if query not in _QUERIES:
            raise ToolValidationError(f"unknown query: {query}")
        if query == "constants_in":
            return self._query_constants_in()
        if query == "executed_blocks":
            return self._query_executed_blocks()
        return self._query_observations(args)

    def _query_constants_in(self) -> dict[str, object]:
        """Only constants the agent has already surfaced via disassemble().

        Deliberately not the full static binary: query_graph digests what is
        already in the ledger, it does not hand out structural evidence the
        agent never paid the cost of observing.
        """
        graph = build_evidence_graph(self._cfg, self._ledger.reader())
        executed = qualified_blocks(graph)
        observations = self._ledger.all()
        entries: list[dict[str, object]] = []
        for block in self._cfg.blocks:
            for value in sorted(extract_constants(block.disasm_lines())):
                observation_handles = sorted(
                    observation.handle
                    for observation in observations
                    if observation.kind == "disasm"
                    and value in observation.facts
                    and observation.anchor.start < block.end
                    and block.start < observation.anchor.end
                )
                if not observation_handles:
                    continue
                entries.append(
                    {
                        "value": value,
                        "block_addr": block.start,
                        "executed": bb_id(block.start) in executed,
                        "observation_handles": observation_handles,
                    }
                )
        return {"constants": entries}

    def _query_executed_blocks(self) -> dict[str, object]:
        graph = build_evidence_graph(self._cfg, self._ledger.reader())
        entries: list[dict[str, object]] = []
        for block in self._cfg.blocks:
            run_handles = sorted(
                source.removeprefix("obs:")
                for source, _target, edge in graph.in_edges(bb_id(block.start), data=True)
                if edge.get("type") == "executed"
            )
            if run_handles:
                entries.append({"block_addr": block.start, "run_handles": run_handles})
        return {"blocks": entries}

    def _query_observations(self, args: Mapping[str, object]) -> dict[str, object]:
        kind = args.get("kind")
        if kind is not None and kind not in ("disasm", "memory", "run"):
            raise ToolValidationError(f"unknown observation kind: {kind!r}")
        return {
            "observations": [
                {
                    "handle": observation.handle,
                    "kind": observation.kind,
                    "anchor": {"start": observation.anchor.start, "end": observation.anchor.end},
                }
                for observation in self._ledger.all()
                if kind is None or observation.kind == kind
            ]
        }

    def reason_codes(self, claim: Claim) -> tuple[str, ...]:
        """v2 reason codes for ``claim`` against the current ledger (V2_SPEC.md section 3.8, R3)."""
        task = {"function_addr": self._function_addr, "function_size": self._function_size}
        graph = build_evidence_graph(self._cfg, self._ledger.reader())
        return _compute_reason_codes(claim, self._ledger.reader(), task, graph=graph)

    def lookup_knowledge(self, query: str) -> dict[str, object]:
        """Lexical lookup into kb/algorithms.json (V2_SPEC.md section 4.3, R4).

        Not evidence (I7): this never touches the ledger, so a returned
        "K-<id>" handle is not a valid observation handle and can never be
        cited in a claim -- ``cited_handles`` resolution fails closed on it,
        same as any other unknown handle (I1). Never reads the held-out
        verdict vectors (I10); only this KB entry's own public fields (its
        publicly documented check values) are returned.
        """
        if self._kb_entries is None:
            self._kb_entries = load_kb_entries(self._root)
        matches = _lookup_knowledge(query, self._kb_entries)
        return {"matches": [dict(match) for match in matches]}

