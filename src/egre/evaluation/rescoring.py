"""Offline re-scoring of a persisted run document under S0 and S1 (V2_SPEC.md section 6).

S0 is read straight from the run file's existing ``outcome`` (produced by
v1's ``egre.contracts.t2.check`` at run time) -- nothing to recompute, so S0
numbers never move. S1 is computed fresh from the claims and ledger the run
file already persisted, using ``egre.support.engine.tier``. Re-scoring never
re-runs the agent or the binary.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import cast

from egre.claims.schema import Claim
from egre.ledger.store import Anchor, Ledger, LedgerReader, ObservationKind, ObservationValue
from egre.support.engine import CLOSED_WORLD, Tier, tier


@dataclass(frozen=True, slots=True)
class RescoredClaim:
    """One claim's unchanged S0 outcome alongside a freshly computed S1 tier."""

    claim_id: str
    primitive: str
    s0_entailed: bool
    s1_tier: Tier
    is_true: bool


def ledger_from_document(document: Mapping[str, object]) -> LedgerReader:
    """Rebuild a read-only ledger from a run file's persisted ``ledger`` list.

    Observations are re-recorded in their original order, so handles come
    back identical to the ones the persisted claims already cite.
    """
    entries = document.get("ledger")
    if not isinstance(entries, list):
        raise TypeError("run document has no 'ledger' list")
    ledger = Ledger()
    for entry in entries:
        if not isinstance(entry, Mapping):
            raise TypeError("each ledger entry must be an object")
        anchor = entry["anchor"]
        if not isinstance(anchor, Mapping):
            raise TypeError("each ledger entry's anchor must be an object")
        ledger.record(
            kind=cast(ObservationKind, entry["kind"]),
            tool=cast(str, entry["tool"]),
            args=cast("Mapping[str, ObservationValue]", entry["args"]),
            anchor=Anchor(cast(int, anchor["start"]), cast(int, anchor["end"])),
            payload=cast("str | int", entry["payload"]),
            facts=cast("Sequence[int]", entry.get("facts", ())),
        )
    return ledger.reader()


def rescore_document(
    document: Mapping[str, object], *, candidates: Sequence[str] = CLOSED_WORLD
) -> tuple[RescoredClaim, ...]:
    """S0 (as already recorded) plus a fresh S1 tier for every claim in ``document``."""
    outcome = document.get("outcome")
    if not isinstance(outcome, Mapping):
        raise TypeError("run document has no 'outcome' to read S0 support from")
    truth = outcome.get("truth")
    raw_outcome_claims = outcome.get("claims")
    if not isinstance(raw_outcome_claims, list):
        raise TypeError("run document outcome has no 'claims' list")
    outcome_by_id = {
        entry["claim_id"]: entry for entry in raw_outcome_claims if isinstance(entry, Mapping)
    }

    raw_claims = document.get("claims")
    if not isinstance(raw_claims, list):
        raise TypeError("run document has no 'claims' list")
    ledger = ledger_from_document(document)

    results: list[RescoredClaim] = []
    for raw in raw_claims:
        claim = Claim.model_validate(raw)
        outcome_entry = outcome_by_id.get(claim.id)
        if outcome_entry is None:
            raise ValueError(f"no outcome entry recorded for claim {claim.id}")
        cited = tuple(ledger.get(handle) for handle in claim.cited_handles)
        results.append(
            RescoredClaim(
                claim_id=claim.id,
                primitive=claim.primitive,
                s0_entailed=outcome_entry.get("support") == "entailed",
                s1_tier=tier(claim.primitive, cited, candidates),
                is_true=claim.primitive == truth,
            )
        )
    return tuple(results)


def is_rescorable(document: Mapping[str, object]) -> bool:
    """Whether ``document`` carries enough raw state to re-score (claims + ledger)."""
    return isinstance(document.get("claims"), list) and isinstance(document.get("ledger"), list)
