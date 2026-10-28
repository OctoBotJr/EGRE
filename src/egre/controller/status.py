"""Deterministically combine evidence support with experimental verdicts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypeAlias

from egre.contracts.t2 import SupportValue
from egre.runner.verify import VerdictValue

StatusValue: TypeAlias = Literal["verified", "refuted", "supported", "hypothesis"]


@dataclass(frozen=True, slots=True)
class ClaimStatus:
    """The public status annotation for one registered claim."""

    status: StatusValue
    support_gap: bool = False

    def __post_init__(self) -> None:
        if self.support_gap and self.status != "verified":
            raise ValueError("support_gap is only valid for a verified status")


def derive_status(support: SupportValue, verdict: VerdictValue) -> ClaimStatus:
    """Apply the prototype's fixed support-by-verdict status table."""
    if verdict == "refuted":
        return ClaimStatus("refuted")
    if verdict == "confirmed":
        return ClaimStatus("verified", support_gap=support == "insufficient")
    if support == "entailed":
        return ClaimStatus("supported")
    return ClaimStatus("hypothesis")
