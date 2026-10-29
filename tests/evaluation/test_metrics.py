import json
from pathlib import Path

import pytest

from egre.demo import build_demo
from egre.evaluation.metrics import summarize

ROOT = Path(__file__).parents[2]

# S0-only outcomes for every (policy, program) in corpus/catalog.json. v1's 7
# programs x 3 policies = 21 combinations are unchanged from the prototype;
# the v2 additions (4 new programs + -O2 builds of all 11) are new since
# Phase D's corpus merge. A few notable, expected (not bugs) consequences:
#  - P2 (emulator) never matches any closed-world primitive against the 4
#    new algorithms (jamcrc/crc32c/fnv1_32/sdbm), so it makes no claim at
#    all for them -- EmulatorPolicy doesn't yet have the "claim other when
#    nothing matches" fallback V2_SPEC.md section 6 describes; that's a
#    real gap to pick up later (V-18 or a P4-era policies pass), not
#    something Phase D's corpus merge should silently paper over.
#  - djb2_fnvdecoy_O2 and fnv1a_crcdecoy_O2 only produce ONE claim each
#    (not two): at -O2 the compiler proves the dead decoy branch
#    unreachable and eliminates it outright, so P1/P3 never see the rival
#    constant at all. sdbm_execdecoy's dead branch survives at -O2 only
#    because it's marked `volatile` specifically to prevent this.
#  - fnv1_clean's P1 claim is fnv1a32, not fnv1_32: fnv1_32 shares both
#    signature constants with fnv1a32 (by design, V2_SPEC.md section 5.1),
#    so the S0 grepper can't tell them apart -- entailed, but refuted
#    since the actual execution doesn't match the fnv1a32 reference. This
#    is exactly the kind of shared-constant confusion H6 is about.
EXPECTED = {
    ("P1", "adler32_clean"): [("adler32", "entailed", "confirmed", "verified", True, False)],
    ("P1", "adler32_clean_O2"): [("adler32", "entailed", "confirmed", "verified", True, False)],
    ("P1", "crc32_clean"): [("crc32", "entailed", "confirmed", "verified", True, False)],
    ("P1", "crc32_clean_O2"): [("crc32", "entailed", "confirmed", "verified", True, False)],
    ("P1", "crc32_obfpoly"): [],
    ("P1", "crc32_obfpoly_O2"): [],
    ("P1", "crc32c_clean"): [],
    ("P1", "crc32c_clean_O2"): [],
    ("P1", "djb2_clean"): [("djb2", "entailed", "confirmed", "verified", True, False)],
    ("P1", "djb2_clean_O2"): [("djb2", "entailed", "confirmed", "verified", True, False)],
    ("P1", "djb2_fnvdecoy"): [
        ("fnv1a32", "entailed", "refuted", "refuted", False, False),
        ("djb2", "entailed", "confirmed", "verified", True, False),
    ],
    ("P1", "djb2_fnvdecoy_O2"): [("djb2", "entailed", "confirmed", "verified", True, False)],
    ("P1", "fnv1_clean"): [("fnv1a32", "entailed", "refuted", "refuted", False, False)],
    ("P1", "fnv1_clean_O2"): [("fnv1a32", "entailed", "refuted", "refuted", False, False)],
    ("P1", "fnv1a_clean"): [("fnv1a32", "entailed", "confirmed", "verified", True, False)],
    ("P1", "fnv1a_clean_O2"): [("fnv1a32", "entailed", "confirmed", "verified", True, False)],
    ("P1", "fnv1a_crcdecoy"): [
        ("crc32", "entailed", "refuted", "refuted", False, False),
        ("fnv1a32", "entailed", "confirmed", "verified", True, False),
    ],
    ("P1", "fnv1a_crcdecoy_O2"): [("fnv1a32", "entailed", "confirmed", "verified", True, False)],
    ("P1", "jamcrc_clean"): [("crc32", "entailed", "refuted", "refuted", False, False)],
    ("P1", "jamcrc_clean_O2"): [("crc32", "entailed", "refuted", "refuted", False, False)],
    ("P1", "sdbm_execdecoy"): [("crc32", "entailed", "refuted", "refuted", False, False)],
    ("P1", "sdbm_execdecoy_O2"): [("crc32", "entailed", "refuted", "refuted", False, False)],
    ("P2", "adler32_clean"): [("adler32", "entailed", "confirmed", "verified", True, False)],
    ("P2", "adler32_clean_O2"): [("adler32", "entailed", "confirmed", "verified", True, False)],
    ("P2", "crc32_clean"): [("crc32", "entailed", "confirmed", "verified", True, False)],
    ("P2", "crc32_clean_O2"): [("crc32", "entailed", "confirmed", "verified", True, False)],
    ("P2", "crc32_obfpoly"): [("crc32", "entailed", "confirmed", "verified", True, False)],
    ("P2", "crc32_obfpoly_O2"): [("crc32", "entailed", "confirmed", "verified", True, False)],
    ("P2", "crc32c_clean"): [],
    ("P2", "crc32c_clean_O2"): [],
    ("P2", "djb2_clean"): [("djb2", "entailed", "confirmed", "verified", True, False)],
    ("P2", "djb2_clean_O2"): [("djb2", "entailed", "confirmed", "verified", True, False)],
    ("P2", "djb2_fnvdecoy"): [("djb2", "entailed", "confirmed", "verified", True, False)],
    ("P2", "djb2_fnvdecoy_O2"): [("djb2", "entailed", "confirmed", "verified", True, False)],
    ("P2", "fnv1_clean"): [],
    ("P2", "fnv1_clean_O2"): [],
    ("P2", "fnv1a_clean"): [("fnv1a32", "entailed", "confirmed", "verified", True, False)],
    ("P2", "fnv1a_clean_O2"): [("fnv1a32", "entailed", "confirmed", "verified", True, False)],
    ("P2", "fnv1a_crcdecoy"): [("fnv1a32", "entailed", "confirmed", "verified", True, False)],
    ("P2", "fnv1a_crcdecoy_O2"): [("fnv1a32", "entailed", "confirmed", "verified", True, False)],
    ("P2", "jamcrc_clean"): [],
    ("P2", "jamcrc_clean_O2"): [],
    ("P2", "sdbm_execdecoy"): [],
    ("P2", "sdbm_execdecoy_O2"): [],
    ("P3", "adler32_clean"): [("crc32", "insufficient", "refuted", "refuted", False, False)],
    ("P3", "adler32_clean_O2"): [("crc32", "insufficient", "refuted", "refuted", False, False)],
    ("P3", "crc32_clean"): [("crc32", "entailed", "confirmed", "verified", True, False)],
    ("P3", "crc32_clean_O2"): [("crc32", "entailed", "confirmed", "verified", True, False)],
    ("P3", "crc32_obfpoly"): [("crc32", "insufficient", "confirmed", "verified", True, True)],
    ("P3", "crc32_obfpoly_O2"): [("crc32", "insufficient", "confirmed", "verified", True, True)],
    ("P3", "crc32c_clean"): [("crc32", "insufficient", "refuted", "refuted", False, False)],
    ("P3", "crc32c_clean_O2"): [("crc32", "insufficient", "refuted", "refuted", False, False)],
    ("P3", "djb2_clean"): [("crc32", "insufficient", "refuted", "refuted", False, False)],
    ("P3", "djb2_clean_O2"): [("crc32", "insufficient", "refuted", "refuted", False, False)],
    ("P3", "djb2_fnvdecoy"): [("crc32", "insufficient", "refuted", "refuted", False, False)],
    ("P3", "djb2_fnvdecoy_O2"): [("crc32", "insufficient", "refuted", "refuted", False, False)],
    ("P3", "fnv1_clean"): [("crc32", "insufficient", "refuted", "refuted", False, False)],
    ("P3", "fnv1_clean_O2"): [("crc32", "insufficient", "refuted", "refuted", False, False)],
    ("P3", "fnv1a_clean"): [("crc32", "insufficient", "refuted", "refuted", False, False)],
    ("P3", "fnv1a_clean_O2"): [("crc32", "insufficient", "refuted", "refuted", False, False)],
    ("P3", "fnv1a_crcdecoy"): [("crc32", "entailed", "refuted", "refuted", False, False)],
    ("P3", "fnv1a_crcdecoy_O2"): [("crc32", "insufficient", "refuted", "refuted", False, False)],
    ("P3", "jamcrc_clean"): [("crc32", "entailed", "refuted", "refuted", False, False)],
    ("P3", "jamcrc_clean_O2"): [("crc32", "entailed", "refuted", "refuted", False, False)],
    ("P3", "sdbm_execdecoy"): [("crc32", "entailed", "refuted", "refuted", False, False)],
    ("P3", "sdbm_execdecoy_O2"): [("crc32", "entailed", "refuted", "refuted", False, False)],
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
        "entailed_true": 28,
        "entailed_false": 13,
        "insufficient_true": 2,
        "insufficient_false": 13,
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
        ("C1", 56, 30, 26, pytest.approx(30 / 56), pytest.approx(30 / 66)),
        ("C2", 41, 28, 13, pytest.approx(28 / 41), pytest.approx(28 / 66)),
        ("C3", 30, 30, 0, pytest.approx(1.0), pytest.approx(30 / 66)),
    ]


@pytest.mark.toolchain
def test_demo_document_is_json_serializable(demo_runs) -> None:
    document = summarize(demo_runs).to_document(demo_runs)

    round_tripped = json.loads(json.dumps(document))
    assert len(round_tripped["runs"]) == 66
    assert round_tripped["views"][2]["false_claims"] == 0
