import json
from pathlib import Path

import pytest

from egre.demo import build_demo
from egre.evaluation.metrics import summarize

ROOT = Path(__file__).parents[2]

EXPECTED = {
    ("P1", "adler32_clean"): [("adler32", "entailed", "confirmed", "verified", True, False)],
    ("P1", "crc32_clean"): [("crc32", "entailed", "confirmed", "verified", True, False)],
    ("P1", "crc32_obfpoly"): [],
    ("P1", "djb2_clean"): [("djb2", "entailed", "confirmed", "verified", True, False)],
    ("P1", "djb2_fnvdecoy"): [
        ("fnv1a32", "entailed", "refuted", "refuted", False, False),
        ("djb2", "entailed", "confirmed", "verified", True, False),
    ],
    ("P1", "fnv1a_clean"): [("fnv1a32", "entailed", "confirmed", "verified", True, False)],
    ("P1", "fnv1a_crcdecoy"): [
        ("crc32", "entailed", "refuted", "refuted", False, False),
        ("fnv1a32", "entailed", "confirmed", "verified", True, False),
    ],
    ("P2", "adler32_clean"): [("adler32", "entailed", "confirmed", "verified", True, False)],
    ("P2", "crc32_clean"): [("crc32", "entailed", "confirmed", "verified", True, False)],
    ("P2", "crc32_obfpoly"): [("crc32", "entailed", "confirmed", "verified", True, False)],
    ("P2", "djb2_clean"): [("djb2", "entailed", "confirmed", "verified", True, False)],
    ("P2", "djb2_fnvdecoy"): [("djb2", "entailed", "confirmed", "verified", True, False)],
    ("P2", "fnv1a_clean"): [("fnv1a32", "entailed", "confirmed", "verified", True, False)],
    ("P2", "fnv1a_crcdecoy"): [("fnv1a32", "entailed", "confirmed", "verified", True, False)],
    ("P3", "adler32_clean"): [("crc32", "insufficient", "refuted", "refuted", False, False)],
    ("P3", "crc32_clean"): [("crc32", "entailed", "confirmed", "verified", True, False)],
    ("P3", "crc32_obfpoly"): [("crc32", "insufficient", "confirmed", "verified", True, True)],
    ("P3", "djb2_clean"): [("crc32", "insufficient", "refuted", "refuted", False, False)],
    ("P3", "djb2_fnvdecoy"): [("crc32", "insufficient", "refuted", "refuted", False, False)],
    ("P3", "fnv1a_clean"): [("crc32", "insufficient", "refuted", "refuted", False, False)],
    ("P3", "fnv1a_crcdecoy"): [("crc32", "entailed", "refuted", "refuted", False, False)],
}


@pytest.fixture(scope="module")
def demo_runs():
    return build_demo(ROOT)


@pytest.mark.toolchain
def test_all_prototype_outcomes_are_exact(demo_runs) -> None:
    actual = {
        (run.policy, run.program): [
            (
                claim.primitive,
                claim.support,
                claim.verdict,
                claim.status,
                claim.is_true,
                claim.support_gap,
            )
            for claim in run.claims
        ]
        for run in demo_runs
    }

    assert actual == EXPECTED


@pytest.mark.toolchain
def test_support_truth_matrix_and_gate_views(demo_runs) -> None:
    result = summarize(demo_runs)

    assert result.support_truth == {
        "entailed_true": 14,
        "entailed_false": 3,
        "insufficient_true": 1,
        "insufficient_false": 4,
    }
    assert [
        (
            view.name,
            view.retained_claims,
            view.true_claims,
            view.false_claims,
            view.precision,
            view.coverage,
        )
        for view in result.views
    ] == [
        ("C1", 22, 15, 7, pytest.approx(15 / 22), pytest.approx(15 / 21)),
        ("C2", 17, 14, 3, pytest.approx(14 / 17), pytest.approx(14 / 21)),
        ("C3", 15, 15, 0, pytest.approx(1.0), pytest.approx(15 / 21)),
    ]


@pytest.mark.toolchain
def test_demo_document_is_json_serializable(demo_runs) -> None:
    document = summarize(demo_runs).to_document(demo_runs)

    round_tripped = json.loads(json.dumps(document))
    assert len(round_tripped["runs"]) == 21
    assert round_tripped["views"][2]["false_claims"] == 0
