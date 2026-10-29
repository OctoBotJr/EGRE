"""Contrastive support tiers (V2_SPEC.md section 3): S1 and S2 scoring modes.

S0 is v1's two-rule contract (``egre.contracts.t2.check``), kept unchanged
for comparability and not reimplemented here. S1 asks, per hypothesis,
whether the cited/available evidence favours it over every rival: a
signature constant or a matching run only counts if no live rival is
equally or better supported, regardless of whether that constant's code
ever ran. S2 adds execution qualification: a disassembly constant counts as
SUPPORTS only if the block holding it was actually entered by some traced
run in the evidence graph (V-08's tracer, V-09's "executed" edges) — a
constant sitting in dead code no longer counts at all.

Memory observations are always NEUTRAL here (v2 limitation: data-table
support needs cross-reference analysis not yet implemented).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Literal, TypeAlias

import networkx as nx

from egre.claims.schema import Claim
from egre.contracts.t2 import SIGNATURE_CONSTANTS
from egre.graph.evidence import obs_id
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


def qualified_blocks(graph: nx.DiGraph) -> frozenset[str]:
    """Block node ids reached by an "executed" edge from any run observation."""
    return frozenset(
        target for _source, target, data in graph.edges(data=True) if data.get("type") == "executed"
    )


def rel_s2(
    observation: Observation,
    hypothesis: str,
    *,
    graph: nx.DiGraph,
    executed: frozenset[str],
) -> RelValue:
    """rel(o, h) under S2: a disasm constant SUPPORTS only if its block ran.

    Run observations are unaffected by execution qualification -- their
    relation is purely output-vs-reference, same as S1.
    """
    if observation.kind == "run":
        return _rel_run(observation, hypothesis)
    if observation.kind != "disasm":
        return "NEUTRAL"
    signature = SIGNATURE_CONSTANTS.get(hypothesis, frozenset())
    if observation.facts.isdisjoint(signature):
        return "NEUTRAL"

    observation_node = obs_id(observation.handle)
    if observation_node not in graph:
        return "NEUTRAL"
    for _source, block_node, anchor_edge in graph.out_edges(observation_node, data=True):
        if anchor_edge.get("type") != "anchored_in" or graph.nodes[block_node].get("type") != "block":
            continue
        block_constants = {
            graph.nodes[constant_node]["value"]
            for _bsource, constant_node, constant_edge in graph.out_edges(block_node, data=True)
            if constant_edge.get("type") == "defines_constant"
        }
        if block_constants & signature and block_node in executed:
            return "SUPPORTS"
    return "NEUTRAL"


RelFn: TypeAlias = Callable[[Observation, str], RelValue]


def _contradicted(evidence: Sequence[Observation], hypothesis: str, rel_fn: RelFn) -> bool:
    return any(rel_fn(observation, hypothesis) == "CONTRADICTS" for observation in evidence)


def _supported(evidence: Sequence[Observation], hypothesis: str, rel_fn: RelFn) -> bool:
    return any(rel_fn(observation, hypothesis) == "SUPPORTS" for observation in evidence)


def _supported_behaviorally(evidence: Sequence[Observation], hypothesis: str, rel_fn: RelFn) -> bool:
    return any(
        observation.kind == "run" and rel_fn(observation, hypothesis) == "SUPPORTS"
        for observation in evidence
    )


def _supported_structurally(evidence: Sequence[Observation], hypothesis: str, rel_fn: RelFn) -> bool:
    return any(
        observation.kind == "disasm" and rel_fn(observation, hypothesis) == "SUPPORTS"
        for observation in evidence
    )


def tier(
    hypothesis: str,
    evidence: Sequence[Observation],
    candidates: Sequence[str] = CLOSED_WORLD,
    *,
    rel_fn: RelFn = rel,
) -> Tier:
    """Support tier of ``hypothesis`` given ``evidence`` (V2_SPEC.md section 3.3).

    ``candidates`` is the closed-world hypothesis set excluding ``other``;
    ``other`` is handled by its own rule, not as a regular rival, since it
    has no reference implementation a run could support or contradict.
    ``rel_fn`` defaults to S1's :func:`rel`; pass a closure over :func:`rel_s2`
    (see :func:`tier_s2`) to compute the execution-qualified tier instead.
    """
    if hypothesis == OTHER:
        if candidates and all(_contradicted(evidence, candidate, rel_fn) for candidate in candidates):
            return "behavioral"
        return "none"

    if _contradicted(evidence, hypothesis, rel_fn):
        return "contradicted"

    rivals = tuple(candidate for candidate in candidates if candidate != hypothesis)
    live_rival_supported = any(
        _supported(evidence, rival, rel_fn) and not _contradicted(evidence, rival, rel_fn)
        for rival in rivals
    )

    if _supported_behaviorally(evidence, hypothesis, rel_fn) and all(
        _contradicted(evidence, rival, rel_fn) for rival in rivals
    ):
        return "behavioral"

    if _supported_structurally(evidence, hypothesis, rel_fn) and not live_rival_supported:
        return "structural"

    if _supported(evidence, hypothesis, rel_fn) and live_rival_supported:
        return "contested"

    return "none"


def tier_s2(
    hypothesis: str,
    evidence: Sequence[Observation],
    candidates: Sequence[str] = CLOSED_WORLD,
    *,
    graph: nx.DiGraph,
) -> Tier:
    """S2 tier: :func:`tier` with execution-qualified disassembly support."""
    executed = qualified_blocks(graph)

    def rel_fn(observation: Observation, h: str) -> RelValue:
        return rel_s2(observation, h, graph=graph, executed=executed)

    return tier(hypothesis, evidence, candidates, rel_fn=rel_fn)


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


def evaluate_claim_s2(
    claim: Claim,
    ledger: LedgerReader,
    graph: nx.DiGraph,
    *,
    candidates: Sequence[str] = CLOSED_WORLD,
) -> ClaimSupport:
    """S2 cited-vs-available tiers for ``claim``, execution-qualified via ``graph``.

    ``graph`` must be built from the same ``ledger`` (egre.graph.evidence),
    so its "executed" edges reflect every run's tracer coverage.
    """
    cited = tuple(ledger.get(handle) for handle in claim.cited_handles)
    available = ledger.all()
    cited_tier = tier_s2(claim.primitive, cited, candidates, graph=graph)
    available_tier = tier_s2(claim.primitive, available, candidates, graph=graph)
    return ClaimSupport(
        cited_tier=cited_tier,
        available_tier=available_tier,
        citation_gap=tier_rank(available_tier) > tier_rank(cited_tier),
        self_contradicted=available_tier == "contradicted",
    )
