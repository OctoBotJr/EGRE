"""V-18 acceptance: the deterministic P1-P4 table against every V2_SPEC.md
section 6 row computable today, plus the C1/C2s/C2b/C3/J views and rates.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from egre.evaluation.demo_v2 import build_demo_v2
from egre.evaluation.metrics_v2 import summarize_v2

ROOT = Path(__file__).resolve().parents[2]

# (policy, program, claimed primitive) -> (cited_tier_s1, cited_tier_s2, verdict, status, is_true)
#
# Notable, expected (not bugs) patterns here:
#  - P1/P3 never call run(): nothing is ever traced, so S2 can never qualify
#    a disasm constant -- every P1/P3 cell is S2="none", even where S1 found
#    structural or contested support. This is exactly the point of S2.
#  - P2 (behavioral, run-based) and P4 (run once + query_graph) are
#    completely unaffected by, or actively resolve, the S1/S2 gap --
#    P4 upgrades every contested S1 case (fnv1a_crcdecoy, djb2_fnvdecoy) to
#    S2 structural, since the dead rival branch never executed.
#  - At -O2, djb2_fnvdecoy and fnv1a_crcdecoy's dead branches are optimized
#    away entirely, so P1/P3 only see ONE claim there (not two) and that
#    claim's constant is absent at -O2 for fnv1a_crcdecoy/P3 (S1 drops to
#    "none"). sdbm_execdecoy's dead tag is `volatile` specifically so it
#    survives at -O2 too.
EXPECTED = {
    ("P1", "crc32_clean", "crc32"): ("structural", "none", "confirmed", "verified", True),
    ("P1", "fnv1a_clean", "fnv1a32"): ("structural", "none", "confirmed", "verified", True),
    ("P1", "adler32_clean", "adler32"): ("structural", "none", "confirmed", "verified", True),
    ("P1", "djb2_clean", "djb2"): ("structural", "none", "confirmed", "verified", True),
    ("P1", "fnv1a_crcdecoy", "crc32"): ("contested", "none", "refuted", "refuted", False),
    ("P1", "fnv1a_crcdecoy", "fnv1a32"): ("contested", "none", "confirmed", "verified", True),
    ("P1", "djb2_fnvdecoy", "fnv1a32"): ("contested", "none", "refuted", "refuted", False),
    ("P1", "djb2_fnvdecoy", "djb2"): ("contested", "none", "confirmed", "verified", True),
    ("P1", "fnv1_clean", "fnv1a32"): ("structural", "none", "refuted", "refuted", False),
    ("P1", "jamcrc_clean", "crc32"): ("structural", "none", "refuted", "refuted", False),
    ("P1", "sdbm_execdecoy", "crc32"): ("structural", "none", "refuted", "refuted", False),
    ("P1", "crc32_clean_O2", "crc32"): ("structural", "none", "confirmed", "verified", True),
    ("P1", "fnv1a_clean_O2", "fnv1a32"): ("structural", "none", "confirmed", "verified", True),
    ("P1", "adler32_clean_O2", "adler32"): ("structural", "none", "confirmed", "verified", True),
    ("P1", "djb2_clean_O2", "djb2"): ("structural", "none", "confirmed", "verified", True),
    ("P1", "fnv1a_crcdecoy_O2", "fnv1a32"): ("structural", "none", "confirmed", "verified", True),
    ("P1", "djb2_fnvdecoy_O2", "djb2"): ("structural", "none", "confirmed", "verified", True),
    ("P1", "fnv1_clean_O2", "fnv1a32"): ("structural", "none", "refuted", "refuted", False),
    ("P1", "jamcrc_clean_O2", "crc32"): ("structural", "none", "refuted", "refuted", False),
    ("P1", "sdbm_execdecoy_O2", "crc32"): ("structural", "none", "refuted", "refuted", False),
    ("P2", "crc32_clean", "crc32"): ("behavioral", "behavioral", "confirmed", "verified", True),
    ("P2", "fnv1a_clean", "fnv1a32"): ("behavioral", "behavioral", "confirmed", "verified", True),
    ("P2", "adler32_clean", "adler32"): ("behavioral", "behavioral", "confirmed", "verified", True),
    ("P2", "djb2_clean", "djb2"): ("behavioral", "behavioral", "confirmed", "verified", True),
    ("P2", "fnv1a_crcdecoy", "fnv1a32"): ("behavioral", "behavioral", "confirmed", "verified", True),
    ("P2", "crc32_obfpoly", "crc32"): ("behavioral", "behavioral", "confirmed", "verified", True),
    ("P2", "djb2_fnvdecoy", "djb2"): ("behavioral", "behavioral", "confirmed", "verified", True),
    ("P2", "crc32_clean_O2", "crc32"): ("behavioral", "behavioral", "confirmed", "verified", True),
    ("P2", "fnv1a_clean_O2", "fnv1a32"): ("behavioral", "behavioral", "confirmed", "verified", True),
    ("P2", "adler32_clean_O2", "adler32"): ("behavioral", "behavioral", "confirmed", "verified", True),
    ("P2", "djb2_clean_O2", "djb2"): ("behavioral", "behavioral", "confirmed", "verified", True),
    ("P2", "fnv1a_crcdecoy_O2", "fnv1a32"): ("behavioral", "behavioral", "confirmed", "verified", True),
    ("P2", "crc32_obfpoly_O2", "crc32"): ("behavioral", "behavioral", "confirmed", "verified", True),
    ("P2", "djb2_fnvdecoy_O2", "djb2"): ("behavioral", "behavioral", "confirmed", "verified", True),
    ("P3", "crc32_clean", "crc32"): ("structural", "none", "confirmed", "verified", True),
    ("P3", "fnv1a_clean", "crc32"): ("none", "none", "refuted", "refuted", False),
    ("P3", "adler32_clean", "crc32"): ("none", "none", "refuted", "refuted", False),
    ("P3", "djb2_clean", "crc32"): ("none", "none", "refuted", "refuted", False),
    ("P3", "fnv1a_crcdecoy", "crc32"): ("contested", "none", "refuted", "refuted", False),
    ("P3", "crc32_obfpoly", "crc32"): ("none", "none", "confirmed", "verified", True),
    ("P3", "djb2_fnvdecoy", "crc32"): ("none", "none", "refuted", "refuted", False),
    ("P3", "fnv1_clean", "crc32"): ("none", "none", "refuted", "refuted", False),
    ("P3", "jamcrc_clean", "crc32"): ("structural", "none", "refuted", "refuted", False),
    ("P3", "crc32c_clean", "crc32"): ("none", "none", "refuted", "refuted", False),
    ("P3", "sdbm_execdecoy", "crc32"): ("structural", "none", "refuted", "refuted", False),
    ("P3", "crc32_clean_O2", "crc32"): ("structural", "none", "confirmed", "verified", True),
    ("P3", "fnv1a_clean_O2", "crc32"): ("none", "none", "refuted", "refuted", False),
    ("P3", "adler32_clean_O2", "crc32"): ("none", "none", "refuted", "refuted", False),
    ("P3", "djb2_clean_O2", "crc32"): ("none", "none", "refuted", "refuted", False),
    ("P3", "fnv1a_crcdecoy_O2", "crc32"): ("none", "none", "refuted", "refuted", False),
    ("P3", "crc32_obfpoly_O2", "crc32"): ("none", "none", "confirmed", "verified", True),
    ("P3", "djb2_fnvdecoy_O2", "crc32"): ("none", "none", "refuted", "refuted", False),
    ("P3", "fnv1_clean_O2", "crc32"): ("none", "none", "refuted", "refuted", False),
    ("P3", "jamcrc_clean_O2", "crc32"): ("structural", "none", "refuted", "refuted", False),
    ("P3", "crc32c_clean_O2", "crc32"): ("none", "none", "refuted", "refuted", False),
    ("P3", "sdbm_execdecoy_O2", "crc32"): ("structural", "none", "refuted", "refuted", False),
    ("P4", "crc32_clean", "crc32"): ("structural", "structural", "confirmed", "verified", True),
    ("P4", "fnv1a_clean", "fnv1a32"): ("structural", "structural", "confirmed", "verified", True),
    ("P4", "adler32_clean", "adler32"): ("structural", "structural", "confirmed", "verified", True),
    ("P4", "djb2_clean", "djb2"): ("structural", "structural", "confirmed", "verified", True),
    ("P4", "fnv1a_crcdecoy", "fnv1a32"): ("contested", "structural", "confirmed", "verified", True),
    ("P4", "djb2_fnvdecoy", "djb2"): ("contested", "structural", "confirmed", "verified", True),
    ("P4", "fnv1_clean", "fnv1a32"): ("structural", "structural", "refuted", "refuted", False),
    ("P4", "jamcrc_clean", "crc32"): ("structural", "structural", "refuted", "refuted", False),
    ("P4", "sdbm_execdecoy", "crc32"): ("structural", "structural", "refuted", "refuted", False),
    ("P4", "crc32_clean_O2", "crc32"): ("structural", "structural", "confirmed", "verified", True),
    ("P4", "fnv1a_clean_O2", "fnv1a32"): ("structural", "structural", "confirmed", "verified", True),
    ("P4", "adler32_clean_O2", "adler32"): ("structural", "structural", "confirmed", "verified", True),
    ("P4", "djb2_clean_O2", "djb2"): ("structural", "structural", "confirmed", "verified", True),
    ("P4", "fnv1a_crcdecoy_O2", "fnv1a32"): ("structural", "structural", "confirmed", "verified", True),
    ("P4", "djb2_fnvdecoy_O2", "djb2"): ("structural", "structural", "confirmed", "verified", True),
    ("P4", "fnv1_clean_O2", "fnv1a32"): ("structural", "structural", "refuted", "refuted", False),
    ("P4", "jamcrc_clean_O2", "crc32"): ("structural", "structural", "refuted", "refuted", False),
    ("P4", "sdbm_execdecoy_O2", "crc32"): ("structural", "structural", "refuted", "refuted", False),
}


@pytest.fixture(scope="module")
def demo_runs_v2():
    return build_demo_v2(ROOT)


@pytest.mark.toolchain
def test_p1_p4_table_matches_section_6_on_all_22_binaries(demo_runs_v2) -> None:
    actual = {
        (run.policy, run.program, claim.primitive): (
            claim.cited_tier_s1,
            claim.cited_tier_s2,
            claim.verdict,
            claim.status,
            claim.is_true,
        )
        for run in demo_runs_v2
        for claim in run.claims
    }

    assert actual == EXPECTED


@pytest.mark.toolchain
def test_s2_never_leaves_a_claim_contested_in_this_corpus(demo_runs_v2) -> None:
    """S2 either fully resolves ambiguity (P4) or finds nothing qualified at
    all (P1/P3, dropping to "none") -- it never produces a genuinely
    contested cited tier for any scripted policy on this corpus."""
    assert all(
        claim.cited_tier_s2 != "contested" for run in demo_runs_v2 for claim in run.claims
    )


@pytest.mark.toolchain
def test_views_c3_and_j_have_perfect_precision(demo_runs_v2) -> None:
    summary = summarize_v2(demo_runs_v2)
    views = {view.name: view for view in summary.views}

    assert views["C1"].retained_claims == 74
    assert views["C2s"].retained_claims == 32
    assert views["C2b"].retained_claims == 14
    assert views["C3"].retained_claims == 42
    assert views["J"].retained_claims == 26

    # the experiment verdict and the J view's structural-or-better floor are
    # each, independently, a strong enough guarantee to have zero false
    # claims on this corpus
    assert views["C3"].false_claims == 0
    assert views["C3"].precision == 1.0
    assert views["J"].false_claims == 0
    assert views["J"].precision == 1.0
    # J is a strict subset of C3: justified-and-true claims are also verified
    assert views["J"].retained_claims <= views["C3"].retained_claims


@pytest.mark.toolchain
def test_overall_rates_and_reason_code_counts(demo_runs_v2) -> None:
    summary = summarize_v2(demo_runs_v2)

    assert summary.overall.claim_count == 74
    assert summary.overall.contested_rate == 0.0
    assert summary.overall.post_hoc_rate is None  # scripted policies have no hypothesis data
    assert summary.overall.reason_code_counts["NO_SUPPORTING_EVIDENCE"] == 42
    assert summary.overall.reason_code_counts["UNQUALIFIED_EVIDENCE"] == 27
    assert summary.overall.reason_code_counts["STRUCTURAL_ONLY"] == 18


@pytest.mark.toolchain
def test_per_program_and_per_variant_breakdowns_cover_every_group(demo_runs_v2) -> None:
    summary = summarize_v2(demo_runs_v2)

    assert set(summary.by_program) == {run.program for run in demo_runs_v2}
    assert set(summary.by_variant) == {"clean", "decoy", "obfuscated"}
    # every program's claim_count matches how many claims it actually produced
    for program, rate in summary.by_program.items():
        expected_count = sum(
            len(run.claims) for run in demo_runs_v2 if run.program == program
        )
        assert rate.claim_count == expected_count
