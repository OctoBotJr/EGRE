"""Deterministic experimental verdicts for T2 primitive claims."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

from .executor import ExecError, run_program
from .refs import REFERENCE_INPUTS, REFERENCES

VerdictValue = Literal["confirmed", "refuted", "inconclusive"]


@dataclass(frozen=True, slots=True)
class VectorEvidence:
    input_hex: str
    expected: int | None
    actual: int | None
    error: str | None = None


@dataclass(frozen=True, slots=True)
class Verdict:
    verdict: VerdictValue
    evidence: tuple[VectorEvidence, ...]


def verify_claim(binary: str | os.PathLike[str], primitive: str) -> Verdict:
    """Compare a binary with a reference primitive across every fixed input vector.

    Any harness failure makes the whole verdict inconclusive, even when another vector
    already differed.  This is the fail-closed behavior required by invariant I3.
    """
    reference = REFERENCES.get(primitive)
    if reference is None:
        unknown_evidence = VectorEvidence(
            input_hex="", expected=None, actual=None, error=f"unknown primitive: {primitive}"
        )
        return Verdict("inconclusive", (unknown_evidence,))

    evidence_items: list[VectorEvidence] = []
    failed = False
    for input_hex in REFERENCE_INPUTS:
        expected = reference(bytes.fromhex(input_hex))
        try:
            actual = run_program(binary, input_hex)
        except ExecError as exc:
            evidence_items.append(
                VectorEvidence(input_hex, expected=expected, actual=None, error=str(exc))
            )
            failed = True
        else:
            evidence_items.append(VectorEvidence(input_hex, expected=expected, actual=actual))

    evidence = tuple(evidence_items)
    if failed:
        return Verdict("inconclusive", evidence)
    if any(item.actual != item.expected for item in evidence):
        return Verdict("refuted", evidence)
    return Verdict("confirmed", evidence)
