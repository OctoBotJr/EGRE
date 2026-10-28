"""Offline evaluation joins registered claims with corpus truth and gate views."""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TypeAlias, cast

from egre.claims.schema import Registry
from egre.contracts.t2 import Reason, SupportValue, check
from egre.controller.status import StatusValue, derive_status
from egre.ledger.store import LedgerReader
from egre.runner.verify import VerdictValue, verify_claim

JsonValue: TypeAlias = str | int | float | bool | None | list["JsonValue"] | dict[str, "JsonValue"]


@dataclass(frozen=True, slots=True)
class ClaimOutcome:
    """One registered claim annotated by independent support, experiment, and truth."""

    claim_id: str
    primitive: str
    support: SupportValue
    reason: Reason | None
    verdict: VerdictValue
    status: StatusValue
    support_gap: bool
    is_true: bool

    def to_document(self) -> dict[str, JsonValue]:
        return {
            "claim_id": self.claim_id,
            "primitive": self.primitive,
            "support": self.support,
            "reason": self.reason,
            "verdict": self.verdict,
            "status": self.status,
            "support_gap": self.support_gap,
            "is_true": self.is_true,
        }

    @classmethod
    def from_document(cls, document: Mapping[str, object]) -> ClaimOutcome:
        """Validate and load one claim outcome from a saved run document."""
        claim_id = document.get("claim_id")
        primitive = document.get("primitive")
        support = document.get("support")
        reason = document.get("reason")
        verdict = document.get("verdict")
        status = document.get("status")
        support_gap = document.get("support_gap")
        is_true = document.get("is_true")
        if not isinstance(claim_id, str) or not isinstance(primitive, str):
            raise TypeError("claim outcome requires string claim_id and primitive")
        if support not in {"entailed", "insufficient"}:
            raise ValueError(f"invalid support value: {support!r}")
        if reason not in {
            None,
            "NO_CITATION",
            "UNKNOWN_HANDLE",
            "ANCHOR_MISMATCH",
            "NO_SIGNATURE_EVIDENCE",
        }:
            raise ValueError(f"invalid support reason: {reason!r}")
        if verdict not in {"confirmed", "refuted", "inconclusive"}:
            raise ValueError(f"invalid verdict value: {verdict!r}")
        if status not in {"verified", "refuted", "supported", "hypothesis"}:
            raise ValueError(f"invalid status value: {status!r}")
        if not isinstance(support_gap, bool) or not isinstance(is_true, bool):
            raise TypeError("claim outcome support_gap and is_true must be booleans")
        return cls(
            claim_id=claim_id,
            primitive=primitive,
            support=cast(SupportValue, support),
            reason=cast(Reason | None, reason),
            verdict=cast(VerdictValue, verdict),
            status=cast(StatusValue, status),
            support_gap=support_gap,
            is_true=is_true,
        )


@dataclass(frozen=True, slots=True)
class RunOutcome:
    """Evaluation result for one policy/program opportunity, including no-claim runs."""

    policy: str
    program: str
    truth: str
    claims: tuple[ClaimOutcome, ...]

    def to_document(self) -> dict[str, JsonValue]:
        return {
            "policy": self.policy,
            "program": self.program,
            "truth": self.truth,
            "claims": [claim.to_document() for claim in self.claims],
        }

    @classmethod
    def from_document(cls, document: Mapping[str, object]) -> RunOutcome:
        """Validate and load one evaluation outcome embedded in a run file."""
        policy = document.get("policy")
        program = document.get("program")
        truth = document.get("truth")
        raw_claims = document.get("claims")
        if not all(isinstance(value, str) for value in (policy, program, truth)):
            raise TypeError("run outcome requires string policy, program, and truth")
        if not isinstance(raw_claims, list):
            raise TypeError("run outcome claims must be a list")
        claims: list[ClaimOutcome] = []
        for raw_claim in raw_claims:
            if not isinstance(raw_claim, dict):
                raise TypeError("each run outcome claim must be an object")
            claims.append(ClaimOutcome.from_document(raw_claim))
        return cls(
            policy=cast(str, policy),
            program=cast(str, program),
            truth=cast(str, truth),
            claims=tuple(claims),
        )


@dataclass(frozen=True, slots=True)
class ViewSummary:
    """Precision is claim-level; coverage is policy/program opportunities recovered."""

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


@dataclass(frozen=True, slots=True)
class EvaluationSummary:
    support_truth: Mapping[str, int]
    views: tuple[ViewSummary, ...]

    def to_document(self, runs: Sequence[RunOutcome]) -> dict[str, JsonValue]:
        return {
            "support_truth": dict(self.support_truth),
            "views": [view.to_document() for view in self.views],
            "runs": [run.to_document() for run in runs],
        }


def evaluate_run(
    *,
    policy: str,
    program: str,
    truth: str,
    task: Mapping[str, object],
    registry: Registry,
    ledger: LedgerReader,
    binary: str | os.PathLike[str],
) -> RunOutcome:
    """Apply all deterministic annotations to one completed agent run."""
    outcomes: list[ClaimOutcome] = []
    for claim in registry:
        support = check(claim, ledger, task)
        verdict = verify_claim(binary, claim.primitive)
        status = derive_status(support.support, verdict.verdict)
        outcomes.append(
            ClaimOutcome(
                claim_id=claim.id,
                primitive=claim.primitive,
                support=support.support,
                reason=support.reason,
                verdict=verdict.verdict,
                status=status.status,
                support_gap=status.support_gap,
                is_true=claim.primitive == truth,
            )
        )
    return RunOutcome(policy=policy, program=program, truth=truth, claims=tuple(outcomes))


def _view(name: str, runs: Sequence[RunOutcome]) -> ViewSummary:
    def retained(claim: ClaimOutcome) -> bool:
        if name == "C1":
            return True
        if name == "C2":
            return claim.support == "entailed"
        if name == "C3":
            return claim.status == "verified"
        raise ValueError(f"unknown view: {name}")

    kept_by_run = [tuple(claim for claim in run.claims if retained(claim)) for run in runs]
    kept = tuple(claim for claims in kept_by_run for claim in claims)
    true_claims = sum(claim.is_true for claim in kept)
    false_claims = len(kept) - true_claims
    covered = sum(any(claim.is_true for claim in claims) for claims in kept_by_run)
    return ViewSummary(
        name=name,
        retained_claims=len(kept),
        true_claims=true_claims,
        false_claims=false_claims,
        precision=true_claims / len(kept) if kept else None,
        coverage=covered / len(runs) if runs else 0.0,
    )


def summarize(runs: Sequence[RunOutcome]) -> EvaluationSummary:
    """Build the support x truth matrix and the prototype's three report views."""
    matrix = {
        "entailed_true": 0,
        "entailed_false": 0,
        "insufficient_true": 0,
        "insufficient_false": 0,
    }
    for run in runs:
        for claim in run.claims:
            matrix[f"{claim.support}_{'true' if claim.is_true else 'false'}"] += 1
    return EvaluationSummary(
        support_truth=matrix,
        views=tuple(_view(name, runs) for name in ("C1", "C2", "C3")),
    )


def has_duplicate_primitives(run: RunOutcome) -> bool:
    """Return whether a run registered the same primitive more than once."""
    primitives = [claim.primitive for claim in run.claims]
    return len(primitives) != len(set(primitives))


def deduplicate_runs(runs: Sequence[RunOutcome]) -> tuple[RunOutcome, ...]:
    """Keep the first registered claim for each primitive within each run."""
    deduplicated: list[RunOutcome] = []
    for run in runs:
        seen: set[str] = set()
        claims: list[ClaimOutcome] = []
        for claim in run.claims:
            if claim.primitive in seen:
                continue
            seen.add(claim.primitive)
            claims.append(claim)
        deduplicated.append(
            RunOutcome(
                policy=run.policy,
                program=run.program,
                truth=run.truth,
                claims=tuple(claims),
            )
        )
    return tuple(deduplicated)
