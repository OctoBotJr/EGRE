"""Per-claim Mermaid evidence subgraph for the v2 report.

Walks only the nodes reachable from one claim's own citations (claim -> obs
-> anchored fn/bb -> defines_constant -> k), so the rendered explanation
never shows more than what that claim actually cites.
"""

from __future__ import annotations

import re

import networkx as nx

from egre.claims.schema import Claim

_UNSAFE = re.compile(r"[^A-Za-z0-9_]")


def _mermaid_id(node: str) -> str:
    return _UNSAFE.sub("_", node)


def claim_subgraph_mermaid(claim: Claim, graph: nx.DiGraph) -> str:
    """Render ``flowchart LR`` Mermaid text for one claim's cited evidence."""
    claim_node = _mermaid_id(f"claim_{claim.id}")
    lines = ["flowchart LR", f'  {claim_node}["{claim.id}: {claim.primitive}"]']
    seen_edges: set[tuple[str, str]] = set()

    def edge(source: str, target: str, label: str) -> None:
        key = (source, target)
        if key in seen_edges:
            return
        seen_edges.add(key)
        safe_target = _mermaid_id(target)
        lines.append(f'  {_mermaid_id(source)} -->|{label}| {safe_target}["{target}"]')

    for handle in claim.cited_handles:
        observation_node = f"obs:{handle}"
        if observation_node not in graph:
            continue
        edge(claim_node, observation_node, "cites")
        for _, target, data in graph.out_edges(observation_node, data=True):
            edge(observation_node, target, str(data.get("type", "")))
            if graph.nodes[target].get("type") != "block":
                continue
            for _, constant, constant_data in graph.out_edges(target, data=True):
                if constant_data.get("type") == "defines_constant":
                    edge(target, constant, "defines_constant")

    return "\n".join(lines) + "\n"
