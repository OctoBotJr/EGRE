import pytest

from egre.claims.schema import Claim
from egre.controller.status_v2 import (
    ClaimFlags,
    HypothesisStep,
    derive_flags,
    derive_status_v2,
    detect_post_hoc,
    reason_codes,
)
from egre.ledger.store import Anchor, Ledger
from egre.runner.refs import REFERENCES
from egre.support.engine import ClaimSupport


@pytest.mark.parametrize(
    ("verdict", "expected"),
    [("refuted", "refuted"), ("confirmed", "verified"), ("inconclusive", "unverified")],
)
def test_derive_status_v2_is_verdict_only(verdict: str, expected: str) -> None:
    assert derive_status_v2(verdict) == expected  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("status", "cited_tier", "expect_gap"),
    [
        ("verified", "behavioral", False),
        ("verified", "structural", False),
        ("verified", "contested", True),
        ("verified", "none", True),
        ("unverified", "none", False),
        ("refuted", "none", False),
    ],
)
def test_support_gap_only_when_verified_and_cited_tier_at_most_contested(
    status: str, cited_tier: str, expect_gap: bool
) -> None:
    support = ClaimSupport(
        cited_tier=cited_tier,  # type: ignore[arg-type]
        available_tier=cited_tier,  # type: ignore[arg-type]
        citation_gap=False,
        self_contradicted=False,
    )

    flags = derive_flags(status, support)  # type: ignore[arg-type]

    assert flags.support_gap is expect_gap


def test_flags_pass_through_citation_gap_and_self_contradicted() -> None:
    support = ClaimSupport(
        cited_tier="none",
        available_tier="contradicted",
        citation_gap=False,
        self_contradicted=True,
    )

    flags = derive_flags("unverified", support)

    assert flags == ClaimFlags(
        support_gap=False, citation_gap=False, self_contradicted=True, post_hoc=False
    )


def _claim(primitive: str, cited_handles: tuple[str, ...] = ()) -> Claim:
    return Claim(
        id="c1", function_addr=0x1000, primitive=primitive, cited_handles=cited_handles, confidence=0.9
    )


_TASK = {"function_addr": 0x1000, "function_size": 0x20}


def test_reason_codes_no_citation() -> None:
    ledger = Ledger()
    assert reason_codes(_claim("crc32"), ledger.reader(), _TASK) == ("NO_CITATION",)


def test_reason_codes_unknown_handle() -> None:
    ledger = Ledger()
    claim = _claim("crc32", ("obs-000099",))
    assert reason_codes(claim, ledger.reader(), _TASK) == ("UNKNOWN_HANDLE",)


def test_reason_codes_anchor_mismatch() -> None:
    ledger = Ledger()
    observation = ledger.record(
        kind="disasm",
        tool="disassemble",
        args={"addr": 0x2000, "count": 4},
        anchor=Anchor(0x2000, 0x2010),
        payload="outside",
        facts=frozenset(),
    )
    claim = _claim("crc32", (observation.handle,))
    assert reason_codes(claim, ledger.reader(), _TASK) == ("ANCHOR_MISMATCH",)


def test_reason_codes_no_supporting_evidence() -> None:
    ledger = Ledger()
    observation = ledger.record(
        kind="disasm",
        tool="disassemble",
        args={"addr": 0x1000, "count": 4},
        anchor=Anchor(0x1000, 0x1010),
        payload="nothing interesting",
        facts=frozenset({0x1}),
    )
    claim = _claim("crc32", (observation.handle,))
    assert reason_codes(claim, ledger.reader(), _TASK) == ("NO_SUPPORTING_EVIDENCE",)


def test_reason_codes_structural_only_and_available_not_cited() -> None:
    ledger = Ledger()
    cited = ledger.record(
        kind="disasm",
        tool="disassemble",
        args={"addr": 0x1000, "count": 4},
        anchor=Anchor(0x1000, 0x1010),
        payload="crc constant",
        facts=frozenset({0xEDB88320}),
    )
    data = b"abc"
    ledger.record(
        kind="run",
        tool="run",
        args={"input_hex": data.hex()},
        anchor=Anchor(0x1000, 0x1020),
        payload=REFERENCES["crc32"](data),
    )
    claim = _claim("crc32", (cited.handle,))

    assert reason_codes(claim, ledger.reader(), _TASK) == (
        "STRUCTURAL_ONLY",
        "EVIDENCE_AVAILABLE_NOT_CITED",
    )


def test_reason_codes_contested_by_rival() -> None:
    ledger = Ledger()
    observation = ledger.record(
        kind="disasm",
        tool="disassemble",
        args={"addr": 0x1000, "count": 4},
        anchor=Anchor(0x1000, 0x1010),
        payload="shared constants",
        facts=frozenset({0x811C9DC5, 0xEDB88320}),
    )
    claim = _claim("fnv1a32", (observation.handle,))

    assert reason_codes(claim, ledger.reader(), _TASK) == ("CONTESTED_BY:crc32",)


def test_reason_codes_contradicted_by_run() -> None:
    ledger = Ledger()
    data = b"abc"
    observation = ledger.record(
        kind="run",
        tool="run",
        args={"input_hex": data.hex()},
        anchor=Anchor(0x1000, 0x1020),
        payload=REFERENCES["crc32"](data),
    )
    claim = _claim("fnv1a32", (observation.handle,))

    assert reason_codes(claim, ledger.reader(), _TASK) == (f"CONTRADICTED_BY:{observation.handle}",)


def test_reason_codes_empty_when_fully_behavioral() -> None:
    ledger = Ledger()
    data = b"abc"
    observation = ledger.record(
        kind="run",
        tool="run",
        args={"input_hex": data.hex()},
        anchor=Anchor(0x1000, 0x1020),
        payload=REFERENCES["crc32"](data),
    )
    claim = _claim("crc32", (observation.handle,))

    assert reason_codes(claim, ledger.reader(), _TASK) == ()


def test_detect_post_hoc_true_when_confident_before_any_support_then_cites_later_evidence() -> None:
    ledger = Ledger()
    later = ledger.record(
        kind="disasm",
        tool="disassemble",
        args={"addr": 0x1000, "count": 4},
        anchor=Anchor(0x1000, 0x1010),
        payload="crc constant",
        facts=frozenset({0xEDB88320}),
    )
    steps = (HypothesisStep(step=1, confidences={"crc32": 0.9}),)
    observation_step = {later.handle: 2}

    assert detect_post_hoc("crc32", steps, (later.handle,), observation_step, ledger.reader()) is True


def test_detect_post_hoc_false_when_support_already_existed_before_the_confident_step() -> None:
    ledger = Ledger()
    early = ledger.record(
        kind="disasm",
        tool="disassemble",
        args={"addr": 0x1000, "count": 4},
        anchor=Anchor(0x1000, 0x1010),
        payload="crc constant",
        facts=frozenset({0xEDB88320}),
    )
    steps = (HypothesisStep(step=2, confidences={"crc32": 0.9}),)
    observation_step = {early.handle: 1}

    assert detect_post_hoc("crc32", steps, (early.handle,), observation_step, ledger.reader()) is False


def test_detect_post_hoc_false_when_below_confidence_threshold() -> None:
    ledger = Ledger()
    steps = (HypothesisStep(step=1, confidences={"crc32": 0.5}),)

    assert detect_post_hoc("crc32", steps, (), {}, ledger.reader()) is False


def test_detect_post_hoc_false_when_a_cited_handle_predates_the_confident_step() -> None:
    ledger = Ledger()
    before = ledger.record(
        kind="disasm",
        tool="disassemble",
        args={"addr": 0x1000, "count": 4},
        anchor=Anchor(0x1000, 0x1010),
        payload="no constant",
        facts=frozenset(),
    )
    steps = (HypothesisStep(step=5, confidences={"crc32": 0.9}),)
    observation_step = {before.handle: 1}

    assert detect_post_hoc("crc32", steps, (before.handle,), observation_step, ledger.reader()) is False
