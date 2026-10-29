import json
from collections.abc import Callable, Mapping

import networkx as nx
import pytest

from egre.claims.schema import Claim, Registry
from egre.controller.status import ClaimStatus
from egre.controller.status_v2 import ClaimFlags
from egre.report.render import render_json, render_markdown, render_markdown_v2


def _claim(claim_id: str, primitive: str, confidence: float) -> Claim:
    return Claim(
        id=claim_id,
        function_addr=0x1000,
        primitive=primitive,
        cited_handles=[f"obs-{claim_id}"],
        confidence=confidence,
    )


def test_json_report_claims_exactly_equal_registry_claims() -> None:
    claims = (
        _claim("c1", "crc32", 0.8),
        _claim("c2", "djb2", 0.6),
    )
    registry = Registry(claims)
    statuses = {
        "c1": ClaimStatus("verified"),
        "c2": ClaimStatus("hypothesis"),
    }

    report = json.loads(render_json(registry, statuses))

    assert [item["claim"] for item in report["claims"]] == [
        claim.model_dump(mode="json") for claim in claims
    ]
    assert [item["status"] for item in report["claims"]] == [
        "verified",
        "hypothesis",
    ]
    assert all(item["support_gap"] is False for item in report["claims"])


def test_markdown_report_is_registry_ordered_and_contains_only_registry_claims() -> None:
    registry = Registry(
        [
            _claim("first", "fnv1a32", 0.75),
            _claim("second", "adler32", 0.5),
        ]
    )
    statuses = {
        "first": ClaimStatus("verified", support_gap=True),
        "second": ClaimStatus("supported"),
    }

    markdown = render_markdown(registry, statuses)

    assert markdown.index("first") < markdown.index("second")
    assert "fnv1a32" in markdown
    assert "adler32" in markdown
    assert "| verified | yes |" in markdown
    assert "| supported | no |" in markdown


@pytest.mark.parametrize(
    "statuses",
    [
        {},
        {"c1": ClaimStatus("verified"), "invented": ClaimStatus("refuted")},
    ],
)
@pytest.mark.parametrize("renderer", [render_json, render_markdown])
def test_report_rejects_status_sets_that_do_not_exactly_match_registry(
    statuses: dict[str, ClaimStatus],
    renderer: Callable[[Registry, Mapping[str, ClaimStatus]], str],
) -> None:
    registry = Registry([_claim("c1", "crc32", 0.8)])

    with pytest.raises(ValueError, match="status ids must exactly match registry ids"):
        renderer(registry, statuses)


def test_markdown_v2_report_has_one_table_row_and_one_mermaid_block_per_claim() -> None:
    registry = Registry(
        [
            _claim("first", "crc32", 0.9),
            _claim("second", "djb2", 0.4),
        ]
    )
    annotations = {
        "first": ("verified", ClaimFlags(False, False, False, False)),
        "second": (
            "unverified",
            ClaimFlags(support_gap=True, citation_gap=True, self_contradicted=False, post_hoc=True),
        ),
    }
    graph: nx.DiGraph = nx.DiGraph()

    markdown = render_markdown_v2(registry, annotations, graph)

    assert markdown.index("first") < markdown.index("second")
    assert markdown.count("```mermaid") == 2
    assert "| verified | no | no | no | no |" in markdown
    assert "| unverified | yes | yes | no | yes |" in markdown
    assert '  claim_first["first: crc32"]' in markdown
    assert '  claim_second["second: djb2"]' in markdown


def test_markdown_v2_report_rejects_annotation_sets_that_do_not_exactly_match_registry() -> None:
    registry = Registry([_claim("c1", "crc32", 0.8)])
    graph: nx.DiGraph = nx.DiGraph()

    with pytest.raises(ValueError, match="status ids must exactly match registry ids"):
        render_markdown_v2(registry, {}, graph)
