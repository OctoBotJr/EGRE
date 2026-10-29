"""Evidence graph: the program's CFG plus the observations anchored to it.

Pure function of (CFG, ledger): rebuilding from the same inputs produces an
identical graph (invariant I9, V2_SPEC.md section 4.4). "executed" edges
(run observation -> block) appear once that run's ``coverage`` was set by
the tracer (V-09); a run with no coverage (no tracer, or tracer_mismatch)
gets no block edges at all, only anchored_in to the function. The knowledge
and claim layers from V2_SPEC.md section 4.2 are added by later tasks
(V-12 knowledge base, V-06/V-17 claims and experiments).
"""

from __future__ import annotations

from typing import Any

import networkx as nx
from networkx.readwrite import json_graph

from egre.graph.cfg import ControlFlowGraph
from egre.ledger.constants import extract_constants
from egre.ledger.store import LedgerReader


def fn_id(addr: int) -> str:
    return f"fn:{addr:#x}"


def bb_id(addr: int) -> str:
    return f"bb:{addr:#x}"


def ins_id(addr: int) -> str:
    return f"ins:{addr:#x}"


def constant_id(value: int, addr: int) -> str:
    return f"k:{value:#x}@{addr:#x}"


def obs_id(handle: str) -> str:
    return f"obs:{handle}"


def build_evidence_graph(cfg: ControlFlowGraph, ledger: LedgerReader) -> nx.DiGraph:
    """Build the program and observation layers of the evidence graph."""
    graph: nx.DiGraph = nx.DiGraph()
    function_node = fn_id(cfg.function_addr)
    graph.add_node(
        function_node,
        layer="program",
        type="function",
        addr=cfg.function_addr,
        end=cfg.function_end,
    )

    for block in cfg.blocks:
        block_node = bb_id(block.start)
        graph.add_node(block_node, layer="program", type="block", addr=block.start, end=block.end)
        graph.add_edge(function_node, block_node, type="contains")

        for instruction in block.instructions:
            instruction_node = ins_id(instruction.address)
            graph.add_node(
                instruction_node,
                layer="program",
                type="instruction",
                addr=instruction.address,
                mnemonic=instruction.mnemonic,
                op_str=instruction.op_str,
            )
            graph.add_edge(block_node, instruction_node, type="contains")

        for constant in sorted(extract_constants(block.disasm_lines())):
            constant_node = constant_id(constant, block.start)
            graph.add_node(
                constant_node, layer="program", type="constant", value=constant, addr=block.start
            )
            graph.add_edge(block_node, constant_node, type="defines_constant")

    for block in cfg.blocks:
        block_node = bb_id(block.start)
        for successor in block.successors:
            graph.add_edge(block_node, bb_id(successor), type="cfg_next")

    for observation in ledger.all():
        observation_node = obs_id(observation.handle)
        graph.add_node(
            observation_node,
            layer="observation",
            type="observation",
            kind=observation.kind,
            tool=observation.tool,
            anchor_start=observation.anchor.start,
            anchor_end=observation.anchor.end,
            ts=observation.ts,
        )
        graph.add_edge(observation_node, function_node, type="anchored_in")
        if observation.kind == "run":
            if observation.coverage:
                for block_addr in sorted(observation.coverage):
                    block_node = bb_id(block_addr)
                    if block_node in graph:
                        graph.add_edge(observation_node, block_node, type="executed")
            continue  # no anchored_in edges for runs; coverage (if any) is "executed" instead
        for block in cfg.blocks:
            if observation.anchor.start < block.end and block.start < observation.anchor.end:
                graph.add_edge(observation_node, bb_id(block.start), type="anchored_in")

    return graph


def to_json_document(graph: nx.DiGraph) -> dict[str, Any]:
    """Export the graph as a JSON-serializable node-link document."""
    return json_graph.node_link_data(graph, edges="edges")


def from_json_document(document: dict[str, Any]) -> nx.DiGraph:
    """Rebuild a graph from a document produced by :func:`to_json_document`."""
    return json_graph.node_link_graph(document, edges="edges", directed=True)
