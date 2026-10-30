"""Deterministic experimental verdicts for T2 primitive claims."""

from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from .executor import ExecError, run_program
from .refs import REFERENCE_INPUTS, REFERENCES, Reference

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


def verify_with_inputs(
    binary: str | os.PathLike[str], reference: Reference, inputs: Sequence[str]
) -> Verdict:
    """V2_SPEC.md section 3.6: confirm/refute/inconclusive over an arbitrary
    reference and input set (V-17's held-out vectors plus designed
    discriminating inputs) instead of the fixed closed-world ones.

    Same fail-closed rule as :func:`verify_claim` (I3): any harness failure
    makes the whole verdict inconclusive, never refuted, even if another
    vector already differed.
    """
    evidence_items: list[VectorEvidence] = []
    failed = False
    for input_hex in inputs:
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
