"""V2 status, flags, reason codes, and the post-hoc proxy (V2_SPEC.md 3.6, 3.5, 3.8).

Status is now derived purely from the experiment verdict; evidence support
is reported separately via the support engine's cited/available tiers
(``egre.support.engine``), not folded into status as v1's
``egre.controller.status.derive_status`` did. That v1 function is untouched
and still drives the S0 evaluation path.

``UNEXECUTED_EVIDENCE`` and ``UNQUALIFIED_EVIDENCE`` (execution-qualification
reason codes) are not produced here: they require block-execution coverage
from the tracer, which does not exist until V-09.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal, TypeAlias

from egre.claims.schema import Claim
from egre.ledger.store import LedgerReader, Observation, UnknownHandleError
from egre.runner.verify import VerdictValue
from egre.support.engine import CLOSED_WORLD, ClaimSupport, rel, tier, tier_rank

StatusValueV2: TypeAlias = Literal["refuted", "verified", "unverified"]


def derive_status_v2(verdict: VerdictValue) -> StatusValueV2:
    """Status from the experiment verdict alone (V2_SPEC.md section 3.6)."""
    if verdict == "refuted":
        return "refuted"
    if verdict == "confirmed":
        return "verified"
    return "unverified"


@dataclass(frozen=True, slots=True)
class ClaimFlags:
    support_gap: bool
    citation_gap: bool
    self_contradicted: bool
    post_hoc: bool


def derive_flags(
    status: StatusValueV2, support: ClaimSupport, *, post_hoc: bool = False
) -> ClaimFlags:
    support_gap = status == "verified" and tier_rank(support.cited_tier) <= tier_rank("contested")
    return ClaimFlags(
        support_gap=support_gap,
        citation_gap=support.citation_gap,
        self_contradicted=support.self_contradicted,
        post_hoc=post_hoc,
    )


def _is_supported(evidence: Sequence[Observation], hypothesis: str) -> bool:
    return any(rel(observation, hypothesis) == "SUPPORTS" for observation in evidence)


def _is_contradicted(evidence: Sequence[Observation], hypothesis: str) -> bool:
    return any(rel(observation, hypothesis) == "CONTRADICTS" for observation in evidence)


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


def reason_codes(
    claim: Claim,
    ledger: LedgerReader,
    task: Mapping[str, object],
    *,
    candidates: Sequence[str] = CLOSED_WORLD,
) -> tuple[str, ...]:
    """Reason codes for a claim's cited evidence (V2_SPEC.md section 3.8).

    Returns an empty tuple when the cited evidence is already structural or
    behavioral, i.e. there is nothing to report back to the agent.
    """
    if not claim.cited_handles:
        return ("NO_CITATION",)
    try:
        cited = tuple(ledger.get(handle) for handle in claim.cited_handles)
    except UnknownHandleError:
        return ("UNKNOWN_HANDLE",)

    start, end = _task_range(task)
    anchored = tuple(observation for observation in cited if _inside_target(observation, start, end))
    if not anchored:
        return ("ANCHOR_MISMATCH",)

    cited_tier = tier(claim.primitive, anchored, candidates)
    available_tier = tier(claim.primitive, ledger.all(), candidates)
    rivals = tuple(candidate for candidate in candidates if candidate != claim.primitive)

    codes: list[str] = []
    if cited_tier == "contradicted":
        codes.extend(
            f"CONTRADICTED_BY:{observation.handle}"
            for observation in anchored
            if rel(observation, claim.primitive) == "CONTRADICTS"
        )
    elif cited_tier == "none":
        codes.append("NO_SUPPORTING_EVIDENCE")
    elif cited_tier == "contested":
        codes.extend(
            f"CONTESTED_BY:{rival}"
            for rival in rivals
            if _is_supported(anchored, rival) and not _is_contradicted(anchored, rival)
        )
    elif cited_tier == "structural":
        codes.append("STRUCTURAL_ONLY")

    if tier_rank(available_tier) > tier_rank(cited_tier):
        codes.append("EVIDENCE_AVAILABLE_NOT_CITED")

    return tuple(codes)


@dataclass(frozen=True, slots=True)
class HypothesisStep:
    """One agent step's declared hypothesis confidences (from R1's schema output)."""

    step: int
    confidences: Mapping[str, float]


def _top_hypothesis(confidences: Mapping[str, float]) -> tuple[str, float] | None:
    if not confidences:
        return None
    return max(confidences.items(), key=lambda item: item[1])


def detect_post_hoc(
    hypothesis: str,
    hypothesis_steps: Sequence[HypothesisStep],
    cited_handles: Sequence[str],
    observation_step: Mapping[str, int],
    ledger: LedgerReader,
    *,
    confidence_threshold: float = 0.7,
) -> bool:
    """Temporal post-hoc proxy (V2_SPEC.md section 3.5).

    True when ``hypothesis`` was already the agent's top, confident
    hypothesis before any observation in the ledger supported it, and the
    claim cites only evidence obtained after that step. A proxy, not proof.
    """
    top_step: int | None = None
    for hypothesis_step in hypothesis_steps:
        top = _top_hypothesis(hypothesis_step.confidences)
        if top is not None and top[0] == hypothesis and top[1] >= confidence_threshold:
            top_step = hypothesis_step.step
            break
    if top_step is None:
        return False

    earliest_support_step: int | None = None
    for observation in ledger.all():
        if rel(observation, hypothesis) != "SUPPORTS":
            continue
        step = observation_step.get(observation.handle)
        if step is not None and (earliest_support_step is None or step < earliest_support_step):
            earliest_support_step = step
    if earliest_support_step is not None and earliest_support_step <= top_step:
        return False

    if not cited_handles:
        return False
    cited_steps = [observation_step.get(handle) for handle in cited_handles]
    if any(step is None for step in cited_steps):
        return False
    return all(step is not None and step > top_step for step in cited_steps)
