import json
from pathlib import Path

import pytest

from egre.claims.schema import Claim
from egre.graph.cfg import build_function_cfg
from egre.graph.evidence import build_evidence_graph
from egre.mediator.tools import MediatorTools
from egre.report.subgraph import claim_subgraph_mermaid

pytestmark = pytest.mark.toolchain

ROOT = Path(__file__).resolve().parents[2]


def test_subgraph_shows_only_this_claims_cited_observation_and_its_constant() -> None:
    task = json.loads((ROOT / "corpus" / "tasks" / "crc32_clean.json").read_text())
    addr = task["function_addr"]
    size = task["function_size"]
    assert isinstance(addr, int) and isinstance(size, int)
    cfg = build_function_cfg(ROOT / str(task["binary"]), addr, size)
    tools = MediatorTools(task, root=ROOT)
    cited = tools.disassemble(addr, 48)
    uncited = tools.run("00")
    graph = build_evidence_graph(cfg, tools.observations)
    claim = Claim(
        id="c1",
        function_addr=addr,
        primitive="crc32",
        cited_handles=(cited.handle,),
        confidence=0.9,
    )

    mermaid = claim_subgraph_mermaid(claim, graph)

    assert mermaid.startswith("flowchart LR")
    assert "c1: crc32" in mermaid
    assert f"obs:{cited.handle}" in mermaid
    assert "0xedb88320" in mermaid.lower()
    assert f"obs:{uncited.handle}" not in mermaid


def test_subgraph_handles_a_claim_with_no_matching_graph_nodes() -> None:
    task = json.loads((ROOT / "corpus" / "tasks" / "crc32_clean.json").read_text())
    addr = task["function_addr"]
    size = task["function_size"]
    assert isinstance(addr, int) and isinstance(size, int)
    cfg = build_function_cfg(ROOT / str(task["binary"]), addr, size)
    tools = MediatorTools(task, root=ROOT)
    graph = build_evidence_graph(cfg, tools.observations)
    claim = Claim(
        id="c1",
        function_addr=addr,
        primitive="crc32",
        cited_handles=("obs-999999",),
        confidence=0.9,
    )

    mermaid = claim_subgraph_mermaid(claim, graph)

    assert mermaid == 'flowchart LR\n  claim_c1["c1: crc32"]\n'
