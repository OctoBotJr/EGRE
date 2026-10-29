import json
from pathlib import Path

import pytest

from egre.claims.schema import Claim
from egre.graph.cfg import build_function_cfg
from egre.graph.evidence import build_evidence_graph
from egre.mediator.tools import MediatorTools
from egre.support.engine import evaluate_claim_s2, qualified_blocks, rel_s2, tier_s2

pytestmark = pytest.mark.toolchain

ROOT = Path(__file__).resolve().parents[2]


def _task(program: str) -> dict[str, object]:
    return json.loads((ROOT / "corpus" / "tasks" / f"{program}.json").read_text())


def test_s2_resolves_the_dead_branch_decoy_that_s1_could_only_contest() -> None:
    """The money-shot H4 case: S2 cleanly separates live from dead evidence."""
    task = _task("fnv1a_crcdecoy")
    addr, size, binary = task["function_addr"], task["function_size"], task["binary"]
    assert isinstance(addr, int) and isinstance(size, int)
    cfg = build_function_cfg(ROOT / str(binary), addr, size)
    tools = MediatorTools(task, root=ROOT)

    disasm = tools.disassemble(addr, 256)
    tools.run("61")  # a normal, non-triggering input (never len == SIZE_MAX)

    graph = build_evidence_graph(cfg, tools.observations)
    cited = (tools.observations.get(disasm.handle),)

    assert tier_s2("fnv1a32", cited, graph=graph) == "structural"
    assert tier_s2("crc32", cited, graph=graph) == "none"


def test_qualified_blocks_is_empty_before_any_run() -> None:
    task = _task("crc32_clean")
    addr, size, binary = task["function_addr"], task["function_size"], task["binary"]
    assert isinstance(addr, int) and isinstance(size, int)
    cfg = build_function_cfg(ROOT / str(binary), addr, size)
    tools = MediatorTools(task, root=ROOT)
    tools.disassemble(addr, 48)

    graph = build_evidence_graph(cfg, tools.observations)

    assert qualified_blocks(graph) == frozenset()


def test_rel_s2_is_neutral_for_an_unqualified_constant_supports_once_qualified() -> None:
    task = _task("crc32_clean")
    addr, size, binary = task["function_addr"], task["function_size"], task["binary"]
    assert isinstance(addr, int) and isinstance(size, int)
    cfg = build_function_cfg(ROOT / str(binary), addr, size)
    tools = MediatorTools(task, root=ROOT)
    disasm = tools.disassemble(addr, 48)

    graph_before = build_evidence_graph(cfg, tools.observations)
    observation = tools.observations.get(disasm.handle)
    assert rel_s2(observation, "crc32", graph=graph_before, executed=qualified_blocks(graph_before)) == "NEUTRAL"

    tools.run("61")
    graph_after = build_evidence_graph(cfg, tools.observations)
    observation = tools.observations.get(disasm.handle)
    assert rel_s2(observation, "crc32", graph=graph_after, executed=qualified_blocks(graph_after)) == "SUPPORTS"


def test_evaluate_claim_s2_matches_tier_s2_for_cited_and_available() -> None:
    task = _task("djb2_fnvdecoy")
    addr, size, binary = task["function_addr"], task["function_size"], task["binary"]
    assert isinstance(addr, int) and isinstance(size, int)
    cfg = build_function_cfg(ROOT / str(binary), addr, size)
    tools = MediatorTools(task, root=ROOT)
    disasm = tools.disassemble(addr, 256)
    tools.run("61")
    graph = build_evidence_graph(cfg, tools.observations)
    claim = Claim(
        id="c1",
        function_addr=addr,
        primitive="fnv1a32",
        cited_handles=(disasm.handle,),
        confidence=0.9,
    )

    result = evaluate_claim_s2(claim, tools.observations, graph)

    assert result.cited_tier == tier_s2("fnv1a32", (tools.observations.get(disasm.handle),), graph=graph)
    assert result.available_tier == tier_s2("fnv1a32", tools.observations.all(), graph=graph)
