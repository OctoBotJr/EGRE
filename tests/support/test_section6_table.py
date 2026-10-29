"""Scripted-policy S0/S1/S2 cells against the V2_SPEC.md section 6 table.

Rows that need the new corpus/KB or the P4 trace-qualified policy
(V-10 through V-16, V-18) are not here yet; only rows computable with the
existing P1-P3 policies and v1 corpus.
"""

import json
from pathlib import Path

import pytest

from egre.agent.loop import AgentLoop
from egre.agent.policies import EmulatorPolicy, GrepperPolicy, PriorGuesserPolicy
from egre.contracts.t2 import check
from egre.graph.cfg import build_function_cfg
from egre.graph.evidence import build_evidence_graph
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


def _run(name: str, policy: object):
    task = _task(name)
    tools = MediatorTools(task, root=ROOT)
    registry = AgentLoop(task, tools, policy).run()  # type: ignore[arg-type]
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
    """Not a section-6 row by itself, but the concrete P1+run combination shows
    S2 achieving what P4 (trace-qualified grepper, not yet implemented) is for:
    once a normal run exists, the live constant qualifies and the dead one does not."""
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
