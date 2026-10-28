"""Registry-only JSON and Markdown report rendering."""

from __future__ import annotations

import json
from collections.abc import Mapping

from egre.claims.schema import Claim, Registry
from egre.controller.status import ClaimStatus


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
