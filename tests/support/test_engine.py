import json
from pathlib import Path
from types import MappingProxyType

import pytest

from egre.claims.schema import Claim
from egre.contracts.t2 import check
from egre.ledger.store import Anchor, Ledger, Observation
from egre.mediator.tools import MediatorTools
from egre.runner.refs import REFERENCES
from egre.support.engine import CLOSED_WORLD, ClaimSupport, evaluate_claim, rel, tier

ROOT = Path(__file__).resolve().parents[2]
_ANCHOR = Anchor(0x1000, 0x1010)


def _disasm(facts: frozenset[int], *, handle: str = "obs-000001") -> Observation:
    return Observation(
        handle=handle,
        kind="disasm",
        tool="disassemble",
        args=MappingProxyType({"addr": 0x1000, "count": 4}),
        anchor=_ANCHOR,
        payload="disasm",
        facts=facts,
        ts="2026-01-01T00:00:00+00:00",
    )


def _run(input_hex: str, output: int, *, handle: str = "obs-000001") -> Observation:
    return Observation(
        handle=handle,
        kind="run",
        tool="run",
        args=MappingProxyType({"input_hex": input_hex}),
        anchor=_ANCHOR,
        payload=output,
        facts=frozenset(),
        ts="2026-01-01T00:00:00+00:00",
    )


def _memory(facts: frozenset[int], *, handle: str = "obs-000001") -> Observation:
    return Observation(
        handle=handle,
        kind="memory",
        tool="read_memory",
        args=MappingProxyType({"addr": 0x1000, "n": 4}),
        anchor=_ANCHOR,
        payload="00",
        facts=facts,
        ts="2026-01-01T00:00:00+00:00",
    )


def test_tier_none_with_no_evidence() -> None:
    assert tier("crc32", ()) == "none"


def test_tier_contradicted_when_a_run_disagrees_with_the_reference() -> None:
    wrong_output = REFERENCES["crc32"](b"a")
    evidence = (_run("61", wrong_output),)

    assert tier("fnv1a32", evidence) == "contradicted"


def test_tier_structural_when_only_the_claimed_signature_constant_is_present() -> None:
    evidence = (_disasm(frozenset({0xEDB88320})),)

    assert tier("crc32", evidence) == "structural"


def test_tier_contested_when_a_rival_signature_constant_is_also_present() -> None:
    evidence = (_disasm(frozenset({0x811C9DC5, 0xEDB88320})),)

    assert tier("fnv1a32", evidence) == "contested"
    assert tier("crc32", evidence) == "contested"


def test_tier_behavioral_when_one_run_eliminates_every_rival() -> None:
    data = b"hello world"
    output = REFERENCES["crc32"](data)
    evidence = (_run(data.hex(), output),)

    assert tier("crc32", evidence) == "behavioral"


def test_tier_other_is_behavioral_only_once_every_candidate_is_contradicted() -> None:
    data = b"hello world"
    non_match = (REFERENCES["crc32"](data) + 1) % (2**32)
    while non_match in {REFERENCES[name](data) for name in CLOSED_WORLD}:
        non_match = (non_match + 1) % (2**32)
    evidence = (_run(data.hex(), non_match),)

    assert tier("other", evidence) == "behavioral"


def test_tier_other_stays_none_if_any_candidate_is_not_contradicted() -> None:
    data = b"hello world"
    evidence = (_run(data.hex(), REFERENCES["crc32"](data)),)

    assert tier("other", evidence) == "none"


def test_memory_observations_are_always_neutral() -> None:
    evidence = (_memory(frozenset({0xEDB88320})),)

    assert rel(evidence[0], "crc32") == "NEUTRAL"
    assert tier("crc32", evidence) == "none"


def test_absent_constant_is_neutral_not_contradicted() -> None:
    evidence = (_disasm(frozenset({0x12345678})),)

    assert tier("crc32", evidence) == "none"


def test_evaluate_claim_citation_gap_and_self_contradicted() -> None:
    ledger = Ledger()
    cited = ledger.record(
        kind="disasm",
        tool="disassemble",
        args={"addr": 0x1000, "count": 4},
        anchor=_ANCHOR,
        payload="disasm",
        facts=frozenset(),
    )
    wrong_output = REFERENCES["crc32"](b"a")
    ledger.record(
        kind="run", tool="run", args={"input_hex": "61"}, anchor=_ANCHOR, payload=wrong_output
    )
    claim = Claim(
        id="c1",
        function_addr=0x1000,
        primitive="fnv1a32",
        cited_handles=(cited.handle,),
        confidence=0.9,
    )

    result = evaluate_claim(claim, ledger.reader())

    assert result == ClaimSupport(
        cited_tier="none",
        available_tier="contradicted",
        citation_gap=False,
        self_contradicted=True,
    )


@pytest.mark.toolchain
@pytest.mark.parametrize(
    ("program", "primitive", "expect_entailed"),
    [
        ("crc32_clean", "crc32", True),
        ("crc32_obfpoly", "crc32", False),
        # v1's S0 rule is blind to dead code: the decoy's FNV constant is present
        # in the disassembly even though it never executes, so S0 marks it entailed
        # (the exact blind spot v2's structural/contested tiers are meant to fix).
        ("djb2_fnvdecoy", "fnv1a32", True),
    ],
)
def test_s0_still_matches_v1_exactly(program: str, primitive: str, expect_entailed: bool) -> None:
    task = json.loads((ROOT / "corpus" / "tasks" / f"{program}.json").read_text())
    addr = task["function_addr"]
    assert isinstance(addr, int)
    tools = MediatorTools(task, root=ROOT)
    observation = tools.disassemble(addr, 48)
    claim = Claim(
        id="c1",
        function_addr=addr,
        primitive=primitive,
        cited_handles=(observation.handle,),
        confidence=0.9,
    )

    support = check(claim, tools.observations, task)

    assert (support.support == "entailed") is expect_entailed

    if program == "djb2_fnvdecoy":
        # S1 catches what S0 misses: the FNV constant is contested by djb2's own,
        # live, uncontradicted signature constant in the same disassembly.
        recorded = tools.observations.get(observation.handle)
        assert tier(primitive, (recorded,)) == "contested"
