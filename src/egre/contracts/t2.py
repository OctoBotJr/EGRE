"""Deterministic evidence contract for prototype T2 primitive claims."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal, TypeAlias

from egre.claims.schema import Claim
from egre.ledger.store import LedgerReader, Observation, UnknownHandleError
from egre.runner.refs import REFERENCES

SupportValue: TypeAlias = Literal["entailed", "insufficient"]
Reason: TypeAlias = Literal[
    "NO_CITATION",
    "UNKNOWN_HANDLE",
    "ANCHOR_MISMATCH",
    "NO_SIGNATURE_EVIDENCE",
]

SIGNATURE_CONSTANTS: Mapping[str, frozenset[int]] = {
    "crc32": frozenset({0xEDB88320}),
    "fnv1a32": frozenset({0x811C9DC5, 0x01000193}),
    "adler32": frozenset({65521}),
    "djb2": frozenset({5381}),
}
_NON_EMPTY_HEX = re.compile(r"(?:[0-9a-fA-F]{2})+")


@dataclass(frozen=True, slots=True)
class Support:
    """A deterministic evidence-support result, independent of claim truth."""

    support: SupportValue
    reason: Reason | None

    def __post_init__(self) -> None:
        if self.support == "entailed" and self.reason is not None:
            raise ValueError("entailed support cannot have a failure reason")
        if self.support == "insufficient" and self.reason is None:
            raise ValueError("insufficient support requires a reason")

def _task_range(task: Mapping[str, object]) -> tuple[int, int]:
    start = task.get("function_addr")
    size = task.get("function_size")
    if isinstance(start, bool) or not isinstance(start, int) or start < 0:
        raise ValueError("task function_addr must be a non-negative integer")
    if isinstance(size, bool) or not isinstance(size, int) or size <= 0:
        raise ValueError("task function_size must be a positive integer")
    return start, start + size


def _inside_target(observation: Observation, start: int, end: int) -> bool:
    return start <= observation.anchor.start and observation.anchor.end <= end


def _matching_run_inputs(observations: tuple[Observation, ...], primitive: str) -> set[bytes]:
    reference = REFERENCES.get(primitive)
    if reference is None:
        return set()

    matches: set[bytes] = set()
    for observation in observations:
        if observation.kind != "run":
            continue
        input_hex = observation.args.get("input_hex")
        if not isinstance(input_hex, str) or _NON_EMPTY_HEX.fullmatch(input_hex) is None:
            continue
        try:
            input_bytes = bytes.fromhex(input_hex)
        except ValueError:
            continue
        if isinstance(observation.payload, bool) or not isinstance(observation.payload, int):
            continue
        if observation.payload == reference(input_bytes):
            matches.add(input_bytes)
    return matches


def check(claim: Claim, ledger: LedgerReader, task: Mapping[str, object]) -> Support:
    """Check cited evidence using only the prototype's two mechanical support rules."""
    if not claim.cited_handles:
        return Support("insufficient", "NO_CITATION")

    observations: list[Observation] = []
    for handle in claim.cited_handles:
        try:
            observations.append(ledger.get(handle))
        except UnknownHandleError:
            return Support("insufficient", "UNKNOWN_HANDLE")

    start, end = _task_range(task)
    if claim.function_addr != start:
        return Support("insufficient", "ANCHOR_MISMATCH")

    anchored = tuple(
        observation
        for observation in observations
        if _inside_target(observation, start, end)
    )
    if not anchored:
        return Support("insufficient", "ANCHOR_MISMATCH")

    signature = SIGNATURE_CONSTANTS.get(claim.primitive, frozenset())
    if any(
        observation.kind in {"disasm", "memory"}
        and not observation.facts.isdisjoint(signature)
        for observation in anchored
    ):
        return Support("entailed", None)

    if len(_matching_run_inputs(anchored, claim.primitive)) >= 2:
        return Support("entailed", None)

    return Support("insufficient", "NO_SIGNATURE_EVIDENCE")
