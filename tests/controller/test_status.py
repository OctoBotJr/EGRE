import pytest

from egre.contracts.t2 import SupportValue
from egre.controller.status import ClaimStatus, derive_status
from egre.runner.verify import VerdictValue


@pytest.mark.parametrize(
    ("support", "verdict", "expected"),
    [
        ("entailed", "confirmed", ClaimStatus("verified", support_gap=False)),
        ("insufficient", "confirmed", ClaimStatus("verified", support_gap=True)),
        ("entailed", "refuted", ClaimStatus("refuted", support_gap=False)),
        ("insufficient", "refuted", ClaimStatus("refuted", support_gap=False)),
        ("entailed", "inconclusive", ClaimStatus("supported", support_gap=False)),
        ("insufficient", "inconclusive", ClaimStatus("hypothesis", support_gap=False)),
    ],
)
def test_full_support_by_verdict_table(
    support: SupportValue, verdict: VerdictValue, expected: ClaimStatus
) -> None:
    assert derive_status(support, verdict) == expected


def test_support_gap_is_only_valid_for_verified_status() -> None:
    with pytest.raises(ValueError, match="verified"):
        ClaimStatus("hypothesis", support_gap=True)
