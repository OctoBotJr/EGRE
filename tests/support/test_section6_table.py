"""Scripted-policy S0/S1 cells against the V2_SPEC.md section 6 table.

Rows that need the tracer (S2) or the new corpus/KB (V-09 through V-16)
are not here yet; only rows computable with what exists through V-07.
"""

import json
from pathlib import Path

import pytest

from egre.agent.loop import AgentLoop
from egre.agent.policies import EmulatorPolicy, GrepperPolicy, PriorGuesserPolicy
from egre.contracts.t2 import check
from egre.mediator.tools import MediatorTools
from egre.support.engine import tier

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


@pytest.mark.parametrize("program", PROGRAMS)
def test_p2_emulator_correct_match_is_entailed_and_behavioral(program: str) -> None:
    task, tools, registry = _run(program, EmulatorPolicy())

    assert len(registry.claims) == 1
    (claim,) = registry.claims
    cited = _cited(tools, claim)

    assert check(claim, tools.observations, task).support == "entailed"
    assert tier(claim.primitive, cited) == "behavioral"


def test_p1_grepper_crc32_clean_is_entailed_and_structural() -> None:
    task, tools, registry = _run("crc32_clean", GrepperPolicy())

    (claim,) = registry.claims
    assert claim.primitive == "crc32"
    cited = _cited(tools, claim)

    assert check(claim, tools.observations, task).support == "entailed"
    assert tier(claim.primitive, cited) == "structural"


def test_p1_grepper_fnv1a_crcdecoy_both_claims_are_entailed_but_contested() -> None:
    task, tools, registry = _run("fnv1a_crcdecoy", GrepperPolicy())

    assert {claim.primitive for claim in registry.claims} == {"crc32", "fnv1a32"}
    for claim in registry.claims:
        cited = _cited(tools, claim)
        assert check(claim, tools.observations, task).support == "entailed"
        assert tier(claim.primitive, cited) == "contested"


def test_p1_grepper_djb2_fnvdecoy_both_claims_are_entailed_but_contested() -> None:
    task, tools, registry = _run("djb2_fnvdecoy", GrepperPolicy())

    assert {claim.primitive for claim in registry.claims} == {"djb2", "fnv1a32"}
    for claim in registry.claims:
        cited = _cited(tools, claim)
        assert check(claim, tools.observations, task).support == "entailed"
        assert tier(claim.primitive, cited) == "contested"


def test_p3_prior_guesser_obfpoly_is_insufficient_and_none() -> None:
    task, tools, registry = _run("crc32_obfpoly", PriorGuesserPolicy())

    (claim,) = registry.claims
    assert claim.primitive == "crc32"
    cited = _cited(tools, claim)

    assert check(claim, tools.observations, task).support == "insufficient"
    assert tier(claim.primitive, cited) == "none"
