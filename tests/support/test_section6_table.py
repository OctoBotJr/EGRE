"""Scripted-policy S0/S1/S2 cells against the V2_SPEC.md section 6 table.

Rows needing V-18's full evaluation harness (per-program/per-variant rates
across all 22 binaries) are not here; this covers every row computable
directly from a scripted policy's claims, now that V-10 through V-16 exist.
"""

import json
from pathlib import Path

import pytest

from egre.agent.loop import AgentLoop
from egre.agent.policies import (
    EmulatorPolicy,
    GrepperPolicy,
    PriorGuesserPolicy,
    TraceQualifiedGrepperPolicy,
)
from egre.contracts.t2 import check
from egre.graph.cfg import build_function_cfg
from egre.graph.evidence import build_evidence_graph
from egre.knowledge.kb import load_kb_entries, open_world_candidates, open_world_signatures
from egre.knowledge.refs import KB_REFERENCES
from egre.mediator.tools import MediatorTools
from egre.support.engine import tier, tier_s2

ROOT = Path(__file__).parents[2]
PROGRAMS = (
    "adler32_clean",
    "crc32_clean",
    "crc32_obfpoly",
    "djb2_clean",
    "djb2_fnvdecoy",
    "fnv1a_clean",
    "fnv1a_crcdecoy",
)

pytestmark = pytest.mark.toolchain


def _task(name: str) -> dict[str, object]:
    return json.loads((ROOT / "corpus" / "tasks" / f"{name}.json").read_text())


def _run(name: str, policy: object, **loop_kwargs: object):
    task = _task(name)
    tools = MediatorTools(task, root=ROOT)
    registry = AgentLoop(task, tools, policy, **loop_kwargs).run()  # type: ignore[arg-type]
    return task, tools, registry


def _cited(tools: MediatorTools, claim) -> tuple:
    return tuple(tools.observations.get(handle) for handle in claim.cited_handles)


def _graph(task: dict[str, object], tools: MediatorTools):
    addr, size = task["function_addr"], task["function_size"]
    assert isinstance(addr, int) and isinstance(size, int)
    cfg = build_function_cfg(ROOT / str(task["binary"]), addr, size)
    return build_evidence_graph(cfg, tools.observations)


@pytest.mark.parametrize("program", PROGRAMS)
def test_p2_emulator_correct_match_is_entailed_and_behavioral(program: str) -> None:
    task, tools, registry = _run(program, EmulatorPolicy())

    assert len(registry.claims) == 1
    (claim,) = registry.claims
    cited = _cited(tools, claim)
    graph = _graph(task, tools)

    assert check(claim, tools.observations, task).support == "entailed"
    assert tier(claim.primitive, cited) == "behavioral"
    # run-based evidence is unaffected by execution qualification
    assert tier_s2(claim.primitive, cited, graph=graph) == "behavioral"


def test_p1_grepper_crc32_clean_is_entailed_structural_but_unqualified_under_s2() -> None:
    task, tools, registry = _run("crc32_clean", GrepperPolicy())

    (claim,) = registry.claims
    assert claim.primitive == "crc32"
    cited = _cited(tools, claim)
    graph = _graph(task, tools)

    assert check(claim, tools.observations, task).support == "entailed"
    assert tier(claim.primitive, cited) == "structural"
    # P1 never calls run(): nothing is traced, so S2 can't qualify the constant
    assert tier_s2(claim.primitive, cited, graph=graph) == "none"


def test_p1_grepper_fnv1a_crcdecoy_both_claims_are_entailed_but_contested() -> None:
    task, tools, registry = _run("fnv1a_crcdecoy", GrepperPolicy())

    assert {claim.primitive for claim in registry.claims} == {"crc32", "fnv1a32"}
    graph = _graph(task, tools)
    for claim in registry.claims:
        cited = _cited(tools, claim)
        assert check(claim, tools.observations, task).support == "entailed"
        assert tier(claim.primitive, cited) == "contested"
        assert tier_s2(claim.primitive, cited, graph=graph) == "none"


def test_p1_grepper_djb2_fnvdecoy_both_claims_are_entailed_but_contested() -> None:
    task, tools, registry = _run("djb2_fnvdecoy", GrepperPolicy())

    assert {claim.primitive for claim in registry.claims} == {"djb2", "fnv1a32"}
    graph = _graph(task, tools)
    for claim in registry.claims:
        cited = _cited(tools, claim)
        assert check(claim, tools.observations, task).support == "entailed"
        assert tier(claim.primitive, cited) == "contested"
        assert tier_s2(claim.primitive, cited, graph=graph) == "none"


def test_p3_prior_guesser_obfpoly_is_insufficient_and_none() -> None:
    task, tools, registry = _run("crc32_obfpoly", PriorGuesserPolicy())

    (claim,) = registry.claims
    assert claim.primitive == "crc32"
    cited = _cited(tools, claim)
    graph = _graph(task, tools)

    assert check(claim, tools.observations, task).support == "insufficient"
    assert tier(claim.primitive, cited) == "none"
    assert tier_s2(claim.primitive, cited, graph=graph) == "none"


def test_a_disassemble_then_run_grepper_s2_separates_live_from_dead_decoy_evidence() -> None:
    """A hand-driven version of what P4 automates below: once a normal run
    exists, the live constant qualifies under S2 and the dead one does not."""
    task = _task("fnv1a_crcdecoy")
    tools = MediatorTools(task, root=ROOT)
    addr = task["function_addr"]
    assert isinstance(addr, int)
    disasm = tools.disassemble(addr, 256)
    tools.run("61")
    graph = _graph(task, tools)
    cited = (tools.observations.get(disasm.handle),)

    assert tier_s2("fnv1a32", cited, graph=graph) == "structural"
    assert tier_s2("crc32", cited, graph=graph) == "none"


def _p4_run(name: str):
    return _run(name, TraceQualifiedGrepperPolicy(), enable_query_graph=True)


def test_p4_trace_qualified_grepper_crc32_clean_is_structural_both_scoring_modes() -> None:
    task, tools, registry = _p4_run("crc32_clean")

    (claim,) = registry.claims
    assert claim.primitive == "crc32"
    cited = _cited(tools, claim)
    graph = _graph(task, tools)

    assert tier(claim.primitive, cited) == "structural"
    assert tier_s2(claim.primitive, cited, graph=graph) == "structural"


def test_p4_trace_qualified_grepper_fnv1a_crcdecoy_resolves_to_structural_under_s2() -> None:
    """S1 can only call this contested (both constants textually present);
    S2 cleanly resolves it since the dead CRC-32 branch never executed."""
    task, tools, registry = _p4_run("fnv1a_crcdecoy")

    (claim,) = registry.claims
    assert claim.primitive == "fnv1a32"
    cited = _cited(tools, claim)
    graph = _graph(task, tools)

    assert tier(claim.primitive, cited) == "contested"
    assert tier_s2(claim.primitive, cited, graph=graph) == "structural"


def test_p4_trace_qualified_grepper_sdbm_execdecoy_is_structural_but_false() -> None:
    """H4b: an executed-but-irrelevant constant still yields structural-but-false
    -- S2 qualifies the dead-but-executed tag, which only an experiment can catch."""
    task, tools, registry = _p4_run("sdbm_execdecoy")

    (claim,) = registry.claims
    assert claim.primitive == "crc32"  # the volatile tag, not the real sdbm algorithm
    cited = _cited(tools, claim)
    graph = _graph(task, tools)

    assert tier_s2(claim.primitive, cited, graph=graph) == "structural"
    assert check(claim, tools.observations, task).support == "entailed"
    truth = json.loads((ROOT / "corpus" / "truth" / "sdbm_execdecoy.json").read_text())
    assert claim.primitive != truth["primitive"]  # structural-but-false: truth is sdbm, not crc32


@pytest.mark.parametrize("program", ["fnv1_clean", "jamcrc_clean"])
def test_p4_open_world_shared_constant_families_become_contested(program: str) -> None:
    """V-16 acceptance: in open world, fnv1_clean and jamcrc_clean's P4 claims
    become contested, because their shared-constant rival (fnv1_32 / jamcrc)
    is now a live candidate S1/S2 never saw under the closed world."""
    task, tools, registry = _p4_run(program)
    kb_entries = load_kb_entries(ROOT)
    candidates = open_world_candidates(kb_entries)
    signatures = open_world_signatures(kb_entries)

    (claim,) = registry.claims
    cited = _cited(tools, claim)
    graph = _graph(task, tools)

    closed_world_tier = tier_s2(claim.primitive, cited, graph=graph)
    open_world_tier = tier_s2(
        claim.primitive,
        cited,
        candidates=candidates,
        graph=graph,
        signatures=signatures,
        references=KB_REFERENCES,
    )

    assert closed_world_tier == "structural"
    assert open_world_tier == "contested"
