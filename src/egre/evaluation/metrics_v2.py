"""V2 evaluation: gate views C1/C2s/C2b/C3/J and per-program/per-variant rates (V2_SPEC.md section 3.7/6, V-18).

S0's two-rule contract and v1's three views (C1/C2/C3 in
``egre.evaluation.metrics``) are untouched elsewhere for comparability.
This module scores the SAME kind of run with S1/S2 contrastive tiers
(``egre.support.engine``), v2 status/flags/reason codes
(``egre.controller.status_v2``), and the experiment designer's verdict
(``egre.runner.experiment``) instead of v1's fixed closed-world vectors.

Views (V2_SPEC.md section 3.7), computed on each claim's S2 cited tier and
v2 status:
- C1: every claim.
- C2s: cited tier >= structural (passive, structural evidence allowed).
- C2b: cited tier == behavioral (passive, behavioral only).
- C3: verified (status == "verified", i.e. the experiment confirmed it).
- J: justified and true -- verified AND cited tier >= structural.

post_hoc is only meaningful for runs with real hypothesis-step data (R1+,
V-13); scripted policies (P1-P4) never declare hypotheses, so their post_hoc
rate is reported as ``None`` (not computable), not silently omitted or
guessed as zero.
"""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TypeAlias

from egre.claims.schema import Registry
from egre.controller.status_v2 import ClaimFlags, StatusValueV2, derive_flags, derive_status_v2
from egre.controller.status_v2 import reason_codes as compute_reason_codes
from egre.graph.cfg import ControlFlowGraph
from egre.graph.evidence import build_evidence_graph
from egre.ledger.store import LedgerReader
from egre.runner.experiment import verdict_for
from egre.runner.refs import REFERENCES, Reference
from egre.runner.verify import VerdictValue
from egre.support.engine import CLOSED_WORLD, ClaimSupport, Tier, evaluate_claim, evaluate_claim_s2

JsonValue: TypeAlias = str | int | float | bool | None | list["JsonValue"] | dict[str, "JsonValue"]

VerdictCache = dict[tuple[str, str], VerdictValue]


@dataclass(frozen=True, slots=True)
class ClaimOutcomeV2:
    """One claim, scored under S1 and S2, with v2 status/flags/reason codes."""

    claim_id: str
    primitive: str
    cited_tier_s1: Tier
    cited_tier_s2: Tier
    available_tier_s1: Tier
    available_tier_s2: Tier
    reason_codes: tuple[str, ...]
    verdict: VerdictValue
    status: StatusValueV2
    flags: ClaimFlags
    is_true: bool

    def to_document(self) -> dict[str, JsonValue]:
        return {
            "claim_id": self.claim_id,
            "primitive": self.primitive,
            "cited_tier_s1": self.cited_tier_s1,
            "cited_tier_s2": self.cited_tier_s2,
            "available_tier_s1": self.available_tier_s1,
            "available_tier_s2": self.available_tier_s2,
            "reason_codes": list(self.reason_codes),
            "verdict": self.verdict,
            "status": self.status,
            "support_gap": self.flags.support_gap,
            "citation_gap": self.flags.citation_gap,
            "self_contradicted": self.flags.self_contradicted,
            "post_hoc": self.flags.post_hoc,
            "is_true": self.is_true,
        }


@dataclass(frozen=True, slots=True)
class RunOutcomeV2:
    """One (policy, program) opportunity, including no-claim runs."""

    policy: str
    program: str
    variant: str
    truth: str
    claims: tuple[ClaimOutcomeV2, ...]


def evaluate_run_v2(
    *,
    policy: str,
    program: str,
    variant: str,
    truth: str,
    task: Mapping[str, object],
    registry: Registry,
    ledger: LedgerReader,
    cfg: ControlFlowGraph,
    binary: str | os.PathLike[str],
    candidates: Sequence[str] = CLOSED_WORLD,
    references: Mapping[str, Reference] = REFERENCES,
    verdict_cache: VerdictCache | None = None,
) -> RunOutcomeV2:
    """Score every claim in ``registry`` under S1/S2 and the experiment verdict.

    ``verdict_cache`` is keyed by (str(binary), primitive): the same binary
    is scored against the same primitive by many policies, and each
    verdict re-executes the binary under every held-out and designed input,
    so callers evaluating many runs against the same corpus should share
    one cache across calls.
    """
    graph = build_evidence_graph(cfg, ledger)
    cache = verdict_cache if verdict_cache is not None else {}
    outcomes: list[ClaimOutcomeV2] = []
    for claim in registry:
        support_s1 = evaluate_claim(claim, ledger, candidates=candidates)
        support_s2: ClaimSupport = evaluate_claim_s2(claim, ledger, graph, candidates=candidates)
        codes = compute_reason_codes(claim, ledger, task, candidates=candidates, graph=graph)

        cache_key = (str(binary), claim.primitive)
        if cache_key not in cache:
            cache[cache_key] = verdict_for(binary, claim.primitive, candidates, references).verdict
        verdict = cache[cache_key]

        status = derive_status_v2(verdict)
        flags = derive_flags(status, support_s2)
        outcomes.append(
            ClaimOutcomeV2(
                claim_id=claim.id,
                primitive=claim.primitive,
                cited_tier_s1=support_s1.cited_tier,
                cited_tier_s2=support_s2.cited_tier,
                available_tier_s1=support_s1.available_tier,
                available_tier_s2=support_s2.available_tier,
                reason_codes=codes,
                verdict=verdict,
                status=status,
                flags=flags,
                is_true=claim.primitive == truth,
            )
        )
    return RunOutcomeV2(policy=policy, program=program, variant=variant, truth=truth, claims=tuple(outcomes))


_STRUCTURAL_OR_BETTER = {"structural", "behavioral"}


@dataclass(frozen=True, slots=True)
class ViewSummaryV2:
    name: str
    retained_claims: int
    true_claims: int
    false_claims: int
    precision: float | None
    coverage: float

    def to_document(self) -> dict[str, JsonValue]:
        return {
            "name": self.name,
            "retained_claims": self.retained_claims,
            "true_claims": self.true_claims,
            "false_claims": self.false_claims,
            "precision": self.precision,
            "coverage": self.coverage,
        }


def _retained(name: str, claim: ClaimOutcomeV2) -> bool:
    if name == "C1":
        return True
    if name == "C2s":
        return claim.cited_tier_s2 in _STRUCTURAL_OR_BETTER
    if name == "C2b":
        return claim.cited_tier_s2 == "behavioral"
    if name == "C3":
        return claim.status == "verified"
    if name == "J":
        return claim.status == "verified" and claim.cited_tier_s2 in _STRUCTURAL_OR_BETTER
    raise ValueError(f"unknown view: {name}")


def _view(name: str, runs: Sequence[RunOutcomeV2]) -> ViewSummaryV2:
    kept_by_run = [tuple(claim for claim in run.claims if _retained(name, claim)) for run in runs]
    kept = tuple(claim for claims in kept_by_run for claim in claims)
    true_claims = sum(claim.is_true for claim in kept)
    false_claims = len(kept) - true_claims
    covered = sum(any(claim.is_true for claim in claims) for claims in kept_by_run)
    return ViewSummaryV2(
        name=name,
        retained_claims=len(kept),
        true_claims=true_claims,
        false_claims=false_claims,
        precision=true_claims / len(kept) if kept else None,
        coverage=covered / len(runs) if runs else 0.0,
    )


@dataclass(frozen=True, slots=True)
class RateSummary:
    """Fractions of CLAIMS (not runs) with each flag, plus reason-code counts.

    ``post_hoc_rate`` is ``None`` when no claim in the group carries
    hypothesis-step data to compute it from (e.g. every scripted-policy
    run) -- never silently reported as 0.
    """

    claim_count: int
    citation_gap_rate: float
    self_contradicted_rate: float
    contested_rate: float
    post_hoc_rate: float | None
    reason_code_counts: Mapping[str, int]

    def to_document(self) -> dict[str, JsonValue]:
        return {
            "claim_count": self.claim_count,
            "citation_gap_rate": self.citation_gap_rate,
            "self_contradicted_rate": self.self_contradicted_rate,
            "contested_rate": self.contested_rate,
            "post_hoc_rate": self.post_hoc_rate,
            "reason_code_counts": dict(self.reason_code_counts),
        }


def _rates(claims: Sequence[ClaimOutcomeV2], *, post_hoc_applicable: bool) -> RateSummary:
    count = len(claims)
    reason_counts: dict[str, int] = {}
    for claim in claims:
        for code in claim.reason_codes:
            reason_counts[code] = reason_counts.get(code, 0) + 1
    return RateSummary(
        claim_count=count,
        citation_gap_rate=(sum(c.flags.citation_gap for c in claims) / count) if count else 0.0,
        self_contradicted_rate=(sum(c.flags.self_contradicted for c in claims) / count) if count else 0.0,
        contested_rate=(sum(c.cited_tier_s2 == "contested" for c in claims) / count) if count else 0.0,
        post_hoc_rate=((sum(c.flags.post_hoc for c in claims) / count) if count else 0.0)
        if post_hoc_applicable
        else None,
        reason_code_counts=reason_counts,
    )


@dataclass(frozen=True, slots=True)
class EvaluationSummaryV2:
    views: tuple[ViewSummaryV2, ...]
    overall: RateSummary
    by_program: Mapping[str, RateSummary]
    by_variant: Mapping[str, RateSummary]

    def to_document(self) -> dict[str, JsonValue]:
        return {
            "views": [view.to_document() for view in self.views],
            "overall": self.overall.to_document(),
            "by_program": {name: rate.to_document() for name, rate in self.by_program.items()},
            "by_variant": {name: rate.to_document() for name, rate in self.by_variant.items()},
        }


def summarize_v2(
    runs: Sequence[RunOutcomeV2], *, post_hoc_applicable: bool = False
) -> EvaluationSummaryV2:
    """Views C1/C2s/C2b/C3/J plus rate breakdowns per program and per variant.

    ``post_hoc_applicable`` should be True only when every run came from a
    condition with real hypothesis-step data (R1+); scripted-policy runs
    never have it, so it defaults to False there.
    """
    all_claims = tuple(claim for run in runs for claim in run.claims)
    by_program: dict[str, list[ClaimOutcomeV2]] = {}
    by_variant: dict[str, list[ClaimOutcomeV2]] = {}
    for run in runs:
        by_program.setdefault(run.program, []).extend(run.claims)
        by_variant.setdefault(run.variant, []).extend(run.claims)

    return EvaluationSummaryV2(
        views=tuple(_view(name, runs) for name in ("C1", "C2s", "C2b", "C3", "J")),
        overall=_rates(all_claims, post_hoc_applicable=post_hoc_applicable),
        by_program={
            name: _rates(claims, post_hoc_applicable=post_hoc_applicable)
            for name, claims in by_program.items()
        },
        by_variant={
            name: _rates(claims, post_hoc_applicable=post_hoc_applicable)
            for name, claims in by_variant.items()
        },
    )
