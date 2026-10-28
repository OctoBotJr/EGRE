from collections.abc import Iterable, Mapping

import pytest

from egre.claims.schema import Claim
from egre.contracts.t2 import Support, check
from egre.ledger.store import Anchor, Ledger, ObservationKind, ObservationValue

FUNCTION_ADDR = 0x1000
FUNCTION_SIZE = 0x100
TASK: dict[str, object] = {
    "function_addr": FUNCTION_ADDR,
    "function_size": FUNCTION_SIZE,
}


def _claim(primitive: str, handles: Iterable[str]) -> Claim:
    return Claim(
        id=f"claim-{primitive}",
        function_addr=FUNCTION_ADDR,
        primitive=primitive,
        cited_handles=list(handles),
        confidence=0.8,
    )


def _record(
    ledger: Ledger,
    *,
    kind: ObservationKind = "disasm",
    args: Mapping[str, ObservationValue] | None = None,
    anchor: Anchor | None = None,
    payload: str | int = "instructions",
    facts: Iterable[int] = (),
) -> str:
    observation = ledger.record(
        kind=kind,
        tool="test",
        args=args or {},
        anchor=anchor or Anchor(FUNCTION_ADDR, FUNCTION_ADDR + 4),
        payload=payload,
        facts=facts,
    )
    return observation.handle


@pytest.mark.parametrize(
    ("primitive", "facts"),
    [
        ("crc32", {0xEDB88320}),
        ("fnv1a32", {0x811C9DC5}),
        ("fnv1a32", {0x01000193}),
        ("adler32", {65521}),
        ("djb2", {5381}),
    ],
)
@pytest.mark.parametrize("kind", ["disasm", "memory"])
def test_rule_a_entails_signature_constant_in_target(
    primitive: str, facts: set[int], kind: ObservationKind
) -> None:
    ledger = Ledger()
    handle = _record(ledger, kind=kind, facts=facts)

    assert check(_claim(primitive, [handle]), ledger.reader(), TASK) == Support(
        "entailed", None
    )


def test_rule_a_is_syntactic_so_a_decoy_constant_entails_the_claim() -> None:
    ledger = Ledger()
    handle = _record(ledger, facts={0xEDB88320})

    support = check(_claim("crc32", [handle]), ledger.reader(), TASK)

    assert support.support == "entailed"


def test_rule_b_entails_two_distinct_non_empty_matching_runs() -> None:
    ledger = Ledger()
    fixed_outputs = {"00": 177573, "616263": 193485963}
    handles = [
        _record(
            ledger,
            kind="run",
            args={"input_hex": input_hex},
            anchor=Anchor(FUNCTION_ADDR, FUNCTION_ADDR + FUNCTION_SIZE),
            payload=fixed_outputs[input_hex],
        )
        for input_hex in ("00", "616263")
    ]

    assert check(_claim("djb2", handles), ledger.reader(), TASK).support == "entailed"


def test_rule_b_accepts_uppercase_hex_and_counts_distinct_byte_inputs() -> None:
    ledger = Ledger()
    first = _record(ledger, kind="run", args={"input_hex": "AA"}, payload=177743)
    second = _record(ledger, kind="run", args={"input_hex": "01"}, payload=177574)

    assert check(_claim("djb2", [first, second]), ledger.reader(), TASK).support == "entailed"


def test_rule_b_does_not_count_hex_case_variants_as_distinct_inputs() -> None:
    ledger = Ledger()
    first = _record(ledger, kind="run", args={"input_hex": "aa"}, payload=177743)
    second = _record(ledger, kind="run", args={"input_hex": "AA"}, payload=177743)

    assert check(_claim("djb2", [first, second]), ledger.reader(), TASK).reason == (
        "NO_SIGNATURE_EVIDENCE"
    )


@pytest.mark.parametrize(
    ("handles", "expected_reason"),
    [([], "NO_CITATION"), (["invented"], "UNKNOWN_HANDLE")],
)
def test_citation_failure_reasons(handles: list[str], expected_reason: str) -> None:
    support = check(_claim("crc32", handles), Ledger().reader(), TASK)

    assert support == Support("insufficient", expected_reason)


def test_anchor_mismatch_reason_when_no_citation_is_inside_target() -> None:
    ledger = Ledger()
    handle = _record(ledger, anchor=Anchor(0x2000, 0x2004), facts={0xEDB88320})

    assert check(_claim("crc32", [handle]), ledger.reader(), TASK) == Support(
        "insufficient", "ANCHOR_MISMATCH"
    )


def test_static_observation_must_be_fully_contained_in_target() -> None:
    ledger = Ledger()
    handle = _record(
        ledger,
        anchor=Anchor(FUNCTION_ADDR + FUNCTION_SIZE - 4, FUNCTION_ADDR + FUNCTION_SIZE + 4),
        facts={0xEDB88320},
    )

    assert check(_claim("crc32", [handle]), ledger.reader(), TASK).reason == "ANCHOR_MISMATCH"


@pytest.mark.parametrize(
    "inputs",
    [
        ("00", "00"),
        ("", "00"),
    ],
)
def test_rule_b_requires_distinct_non_empty_inputs(inputs: tuple[str, str]) -> None:
    ledger = Ledger()
    handles = [
        _record(
            ledger,
            kind="run",
            args={"input_hex": input_hex},
            payload={"": 0, "00": 3523407757}[input_hex],
        )
        for input_hex in inputs
    ]

    assert check(_claim("crc32", handles), ledger.reader(), TASK) == Support(
        "insufficient", "NO_SIGNATURE_EVIDENCE"
    )


def test_rule_b_rejects_a_wrong_recorded_output() -> None:
    ledger = Ledger()
    first = _record(
        ledger,
        kind="run",
        args={"input_hex": "00"},
        payload=84696351,
    )
    second = _record(
        ledger,
        kind="run",
        args={"input_hex": "01"},
        payload=0,
    )

    assert check(_claim("fnv1a32", [first, second]), ledger.reader(), TASK).reason == (
        "NO_SIGNATURE_EVIDENCE"
    )


def test_unrelated_signature_constant_is_insufficient() -> None:
    ledger = Ledger()
    handle = _record(ledger, facts={0x811C9DC5, 0x01000193})

    assert check(_claim("djb2", [handle]), ledger.reader(), TASK) == Support(
        "insufficient", "NO_SIGNATURE_EVIDENCE"
    )
