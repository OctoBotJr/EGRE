"""Contrastive support tiers (V2_SPEC.md section 3): S1 scoring mode.

S0 is v1's two-rule contract (``egre.contracts.t2.check``), kept unchanged
for comparability and not reimplemented here. S1 instead asks, per
hypothesis, whether the cited/available evidence favours it over every
rival: a signature constant or a matching run only counts if no live rival
is equally or better supported. Execution-qualified S2 (does the
constant's block actually run?) needs the tracer and arrives in V-09.

Memory observations are always NEUTRAL here (v2 limitation: data-table
support needs cross-reference analysis not yet implemented).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal, TypeAlias

from egre.claims.schema import Claim
from egre.contracts.t2 import SIGNATURE_CONSTANTS
from egre.ledger.store import LedgerReader, Observation
from egre.runner.refs import REFERENCES

RelValue: TypeAlias = Literal["SUPPORTS", "CONTRADICTS", "NEUTRAL"]
Tier: TypeAlias = Literal["contradicted", "none", "contested", "structural", "behavioral"]

OTHER = "other"
CLOSED_WORLD: tuple[str, ...] = tuple(SIGNATURE_CONSTANTS)

_TIER_RANK: Mapping[Tier, int] = {
    "contradicted": 0,
    "none": 1,
    "contested": 2,
    "structural": 3,
    "behavioral": 4,
}


def tier_rank(value: Tier) -> int:
    return _TIER_RANK[value]


def _rel_run(observation: Observation, hypothesis: str) -> RelValue:
    reference = REFERENCES.get(hypothesis)
    if reference is None:
        return "NEUTRAL"
    input_hex = observation.args.get("input_hex")
    if not isinstance(input_hex, str):
        return "NEUTRAL"
    try:
        input_bytes = bytes.fromhex(input_hex)
    except ValueError:
        return "NEUTRAL"
    if isinstance(observation.payload, bool) or not isinstance(observation.payload, int):
        return "NEUTRAL"
    return "SUPPORTS" if observation.payload == reference(input_bytes) else "CONTRADICTS"


def _rel_disasm(observation: Observation, hypothesis: str) -> RelValue:
    signature = SIGNATURE_CONSTANTS.get(hypothesis, frozenset())
    return "NEUTRAL" if observation.facts.isdisjoint(signature) else "SUPPORTS"


def rel(observation: Observation, hypothesis: str) -> RelValue:
    """rel(o, h) under S1: contrastive, execution-unqualified (V2_SPEC.md section 3.2)."""
    if observation.kind == "run":
        return _rel_run(observation, hypothesis)
    if observation.kind == "disasm":
        return _rel_disasm(observation, hypothesis)
    return "NEUTRAL"


def _contradicted(evidence: Sequence[Observation], hypothesis: str) -> bool:
    return any(rel(observation, hypothesis) == "CONTRADICTS" for observation in evidence)


def _supported(evidence: Sequence[Observation], hypothesis: str) -> bool:
    return any(rel(observation, hypothesis) == "SUPPORTS" for observation in evidence)


def _supported_behaviorally(evidence: Sequence[Observation], hypothesis: str) -> bool:
    return any(
        observation.kind == "run" and rel(observation, hypothesis) == "SUPPORTS"
        for observation in evidence
    )


def _supported_structurally(evidence: Sequence[Observation], hypothesis: str) -> bool:
    return any(
        observation.kind == "disasm" and rel(observation, hypothesis) == "SUPPORTS"
        for observation in evidence
    )


def tier(
    hypothesis: str,
    evidence: Sequence[Observation],
    candidates: Sequence[str] = CLOSED_WORLD,
) -> Tier:
    """Support tier of ``hypothesis`` given ``evidence`` (V2_SPEC.md section 3.3).

    ``candidates`` is the closed-world hypothesis set excluding ``other``;
    ``other`` is handled by its own rule, not as a regular rival, since it
    has no reference implementation a run could support or contradict.
    """
    if hypothesis == OTHER:
        if candidates and all(_contradicted(evidence, candidate) for candidate in candidates):
            return "behavioral"
        return "none"

    if _contradicted(evidence, hypothesis):
        return "contradicted"

    rivals = tuple(candidate for candidate in candidates if candidate != hypothesis)
    live_rival_supported = any(
        _supported(evidence, rival) and not _contradicted(evidence, rival) for rival in rivals
    )

    if _supported_behaviorally(evidence, hypothesis) and all(
        _contradicted(evidence, rival) for rival in rivals
    ):
        return "behavioral"

    if _supported_structurally(evidence, hypothesis) and not live_rival_supported:
        return "structural"

    if _supported(evidence, hypothesis) and live_rival_supported:
        return "contested"

    return "none"


@dataclass(frozen=True, slots=True)
class ClaimSupport:
    """Cited vs. available support tier for one claim (V2_SPEC.md section 3.4)."""

    cited_tier: Tier
    available_tier: Tier
    citation_gap: bool
    self_contradicted: bool


def evaluate_claim(
    claim: Claim,
    ledger: LedgerReader,
    *,
    candidates: Sequence[str] = CLOSED_WORLD,
) -> ClaimSupport:
    """S1 cited-vs-available tiers for ``claim``.

    Raises ``UnknownHandleError`` if a cited handle was never issued by the
    ledger; callers decide how that becomes a reason code.
    """
    cited = tuple(ledger.get(handle) for handle in claim.cited_handles)
    available = ledger.all()
    cited_tier = tier(claim.primitive, cited, candidates)
    available_tier = tier(claim.primitive, available, candidates)
    return ClaimSupport(
        cited_tier=cited_tier,
        available_tier=available_tier,
        citation_gap=tier_rank(available_tier) > tier_rank(cited_tier),
        self_contradicted=available_tier == "contradicted",
    )
