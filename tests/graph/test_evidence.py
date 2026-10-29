import json
from pathlib import Path

import pytest

from egre.graph.cfg import build_function_cfg
from egre.graph.evidence import (
    bb_id,
    build_evidence_graph,
    fn_id,
    from_json_document,
    to_json_document,
)
from egre.mediator.tools import MediatorTools

pytestmark = pytest.mark.toolchain

ROOT = Path(__file__).resolve().parents[2]


def _task(program: str) -> dict[str, object]:
    return json.loads((ROOT / "corpus" / "tasks" / f"{program}.json").read_text())


def _cfg_and_tools(program: str) -> tuple[object, MediatorTools, int, int]:
    task = _task(program)
    addr = task["function_addr"]
    size = task["function_size"]
    assert isinstance(addr, int) and isinstance(size, int)
    cfg = build_function_cfg(ROOT / str(task["binary"]), addr, size)
    tools = MediatorTools(task, root=ROOT)
    return cfg, tools, addr, size


def test_rebuild_from_the_same_ledger_is_identical_i9() -> None:
    cfg, tools, addr, _ = _cfg_and_tools("crc32_clean")
    tools.disassemble(addr, 48)
    tools.run("00")

    first = to_json_document(build_evidence_graph(cfg, tools.observations))
    second = to_json_document(build_evidence_graph(cfg, tools.observations))

    assert first == second


def test_program_layer_has_constant_node_reachable_from_a_block() -> None:
    cfg, _tools, _addr, _size = _cfg_and_tools("crc32_clean")

    graph = build_evidence_graph(cfg, _tools.observations)

    constant_nodes = [
        node for node, data in graph.nodes(data=True) if data.get("value") == 0xEDB88320
    ]
    assert len(constant_nodes) == 1
    (constant_node,) = constant_nodes
    predecessors = list(graph.predecessors(constant_node))
    assert len(predecessors) == 1
    assert graph.edges[predecessors[0], constant_node]["type"] == "defines_constant"
    assert graph.nodes[predecessors[0]]["type"] == "block"


def test_program_layer_blocks_chain_by_cfg_next_and_function_contains_them() -> None:
    cfg, tools, addr, _ = _cfg_and_tools("fnv1a_crcdecoy")
    graph = build_evidence_graph(cfg, tools.observations)
    function_node = fn_id(addr)

    for block in cfg.blocks:
        block_node = bb_id(block.start)
        assert graph.edges[function_node, block_node]["type"] == "contains"
        for successor in block.successors:
            assert graph.edges[block_node, bb_id(successor)]["type"] == "cfg_next"


def test_disasm_observation_anchors_to_overlapping_blocks_run_gets_executed_edges() -> None:
    cfg, tools, addr, _size = _cfg_and_tools("crc32_clean")
    disasm = tools.disassemble(addr, 48)
    run = tools.run("00")

    graph = build_evidence_graph(cfg, tools.observations)

    disasm_node = f"obs:{disasm.handle}"
    run_node = f"obs:{run.handle}"
    disasm_edges = {(v, data["type"]) for _, v, data in graph.out_edges(disasm_node, data=True)}
    run_edges = {(v, data["type"]) for _, v, data in graph.out_edges(run_node, data=True)}

    assert (fn_id(addr), "anchored_in") in disasm_edges
    assert any(target.startswith("bb:") and kind == "anchored_in" for target, kind in disasm_edges)

    assert (fn_id(addr), "anchored_in") in run_edges
    assert all(kind == "executed" for target, kind in run_edges if target.startswith("bb:"))
    # the real tracer ran this input: at least one block is marked executed, not just anchored
    assert any(kind == "executed" for _target, kind in run_edges)


def test_json_round_trip_preserves_nodes_and_edges() -> None:
    cfg, tools, addr, _ = _cfg_and_tools("djb2_clean")
    tools.disassemble(addr, 32)
    graph = build_evidence_graph(cfg, tools.observations)

    document = to_json_document(graph)
    rebuilt = from_json_document(document)

    assert sorted(graph.nodes) == sorted(rebuilt.nodes)
    assert sorted(graph.edges) == sorted(rebuilt.edges)
    assert to_json_document(rebuilt) == document
