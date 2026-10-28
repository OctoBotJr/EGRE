import json
from pathlib import Path

import pytest

from egre.agent.loop import AgentLoop
from egre.agent.policies import EmulatorPolicy, GrepperPolicy, PriorGuesserPolicy
from egre.contracts.t2 import check
from egre.mediator.tools import MediatorTools

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
TRUTH = {
    "adler32_clean": "adler32",
    "crc32_clean": "crc32",
    "crc32_obfpoly": "crc32",
    "djb2_clean": "djb2",
    "djb2_fnvdecoy": "djb2",
    "fnv1a_clean": "fnv1a32",
    "fnv1a_crcdecoy": "fnv1a32",
}
GREPPER_CLAIMS = {
    "adler32_clean": ["adler32"],
    "crc32_clean": ["crc32"],
    "crc32_obfpoly": [],
    "djb2_clean": ["djb2"],
    "djb2_fnvdecoy": ["fnv1a32", "djb2"],
    "fnv1a_clean": ["fnv1a32"],
    "fnv1a_crcdecoy": ["crc32", "fnv1a32"],
}


def _task(name: str) -> dict[str, object]:
    return json.loads((ROOT / "corpus" / "tasks" / f"{name}.json").read_text())


def _run(name: str, policy: object):
    task = _task(name)
    tools = MediatorTools(task, root=ROOT)
    registry = AgentLoop(task, tools, policy).run()  # type: ignore[arg-type]
    return task, tools, registry


@pytest.mark.toolchain
@pytest.mark.parametrize("program", PROGRAMS)
def test_p1_grepper_claims_every_visible_signature(program: str) -> None:
    task, tools, registry = _run(program, GrepperPolicy())

    assert [claim.primitive for claim in registry] == GREPPER_CLAIMS[program]
    assert all(check(claim, tools.observations, task).support == "entailed" for claim in registry)
    assert {observation.kind for observation in tools.observations.all()} == {"disasm"}


@pytest.mark.toolchain
@pytest.mark.parametrize("program", PROGRAMS)
def test_p2_emulator_claims_unique_reference_match(program: str) -> None:
    task, tools, registry = _run(program, EmulatorPolicy())

    assert [claim.primitive for claim in registry] == [TRUTH[program]]
    assert check(registry.claims[0], tools.observations, task).support == "entailed"
    runs = tools.observations.all()
    assert len(runs) == 3
    assert all(observation.kind == "run" for observation in runs)
    assert len({observation.args["input_hex"] for observation in runs}) == 3


@pytest.mark.toolchain
@pytest.mark.parametrize("program", PROGRAMS)
def test_p3_prior_guesser_always_claims_crc32(program: str) -> None:
    _, tools, registry = _run(program, PriorGuesserPolicy())

    assert [claim.primitive for claim in registry] == ["crc32"]
    assert registry.claims[0].cited_handles == ("obs-000001",)
    assert len(tools.observations) == 1
    assert tools.observations.all()[0].kind == "disasm"
