"""Registry-only JSON and Markdown report rendering."""

from __future__ import annotations

import json
from collections.abc import Mapping

import networkx as nx

from egre.claims.schema import Claim, Registry
from egre.controller.status import ClaimStatus
from egre.controller.status_v2 import ClaimFlags, StatusValueV2
from egre.report.subgraph import claim_subgraph_mermaid


def _report_entries(
    registry: Registry, statuses: Mapping[str, ClaimStatus]
) -> tuple[tuple[Claim, ClaimStatus], ...]:
    claims = registry.claims
    registry_ids = {claim.id for claim in claims}
    if set(statuses) != registry_ids:
        raise ValueError("status ids must exactly match registry ids")
    return tuple((claim, statuses[claim.id]) for claim in claims)


def render_json(registry: Registry, statuses: Mapping[str, ClaimStatus]) -> str:
    """Render claims in registry order, with annotations kept outside claim data."""
    entries = _report_entries(registry, statuses)
    document = {
        "claims": [
            {
                "claim": claim.model_dump(mode="json"),
                "status": status.status,
                "support_gap": status.support_gap,
            }
            for claim, status in entries
        ]
    }
    return json.dumps(document, indent=2, sort_keys=True)


def _markdown_text(value: object) -> str:
    return " ".join(str(value).split()).replace("|", "\\|")


def render_markdown(registry: Registry, statuses: Mapping[str, ClaimStatus]) -> str:
    """Render one Markdown table row for every and only registered claim."""
    entries = _report_entries(registry, statuses)
    lines = [
        "# Claim report",
        "",
        "| ID | Function | Primitive | Confidence | Cited handles | Status | Support gap |",
        "| --- | ---: | --- | ---: | --- | --- | --- |",
    ]
    for claim, status in entries:
        handles = ", ".join(_markdown_text(handle) for handle in claim.cited_handles) or "-"
        lines.append(
            "| "
            f"{_markdown_text(claim.id)} | {claim.function_addr:#x} | {claim.primitive} | "
            f"{claim.confidence:.3f} | {handles} | {status.status} | "
            f"{'yes' if status.support_gap else 'no'} |"
        )
    return "\n".join(lines) + "\n"


def _report_entries_v2(
    registry: Registry, annotations: Mapping[str, tuple[StatusValueV2, ClaimFlags]]
) -> tuple[tuple[Claim, StatusValueV2, ClaimFlags], ...]:
    claims = registry.claims
    registry_ids = {claim.id for claim in claims}
    if set(annotations) != registry_ids:
        raise ValueError("status ids must exactly match registry ids")
    return tuple((claim, *annotations[claim.id]) for claim in claims)


def render_markdown_v2(
    registry: Registry,
    annotations: Mapping[str, tuple[StatusValueV2, ClaimFlags]],
    graph: nx.DiGraph,
) -> str:
    """Render the v2 claim table plus one Mermaid evidence subgraph per claim."""
    entries = _report_entries_v2(registry, annotations)
    lines = [
        "# Claim report (v2)",
        "",
        (
            "| ID | Function | Primitive | Status | support_gap | citation_gap | "
            "self_contradicted | post_hoc |"
        ),
        "| --- | ---: | --- | --- | --- | --- | --- | --- |",
    ]
    for claim, status, flags in entries:
        lines.append(
            "| "
            f"{_markdown_text(claim.id)} | {claim.function_addr:#x} | {claim.primitive} | "
            f"{status} | {'yes' if flags.support_gap else 'no'} | "
            f"{'yes' if flags.citation_gap else 'no'} | "
            f"{'yes' if flags.self_contradicted else 'no'} | "
            f"{'yes' if flags.post_hoc else 'no'} |"
        )
    lines.append("")
    for claim, _status, _flags in entries:
        lines.append(f"## Evidence for {_markdown_text(claim.id)}")
        lines.append("")
        lines.append("```mermaid")
        lines.append(claim_subgraph_mermaid(claim, graph).rstrip("\n"))
        lines.append("```")
        lines.append("")
    return "\n".join(lines) + "\n"
