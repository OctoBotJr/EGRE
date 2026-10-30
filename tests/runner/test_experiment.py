import json
from pathlib import Path

import pytest

from egre.knowledge.kb import load_kb_entries, open_world_candidates
from egre.knowledge.refs import KB_REFERENCES
from egre.runner.experiment import design_inputs, load_held_out_inputs, verdict_for
from egre.runner.refs import REFERENCES
from egre.support.engine import CLOSED_WORLD

ROOT = Path(__file__).resolve().parents[2]


def test_design_inputs_separates_every_pair_in_the_closed_world() -> None:
    design = design_inputs(tuple(REFERENCES), REFERENCES)

    assert design.indistinguishable_pairs == ()
    assert design.inputs  # at least one input was actually chosen


def test_design_inputs_separates_every_pair_in_the_open_world_kb() -> None:
    entries = load_kb_entries(ROOT)
    candidates = open_world_candidates(entries)

    design = design_inputs(candidates, KB_REFERENCES)

    assert design.indistinguishable_pairs == ()


def test_designed_inputs_are_never_copied_from_kb_public_vectors() -> None:
    entries = load_kb_entries(ROOT)
    candidates = open_world_candidates(entries)
    public_inputs = {vector["input_hex"] for entry in entries for vector in entry["public_vectors"]}

    design = design_inputs(candidates, KB_REFERENCES)

    assert set(design.inputs).isdisjoint(public_inputs)


def test_design_inputs_greedily_picks_the_input_covering_the_most_pairs() -> None:
    # a and b are identical everywhere in the pool (indistinguishable); c
    # differs from both, but only at 0x01 -- one input covers (a,c) and (b,c).
    references = {
        "a": lambda data: 1 if data == b"\x01" else 0,
        "b": lambda data: 1 if data == b"\x01" else 0,
        "c": lambda data: 0,
    }
    pool = (b"\x00", b"\x01", b"\x02")

    design = design_inputs(("a", "b", "c"), references, pool=pool)

    assert design.inputs == ("01",)  # one input separates both (a,c) and (b,c)
    assert design.indistinguishable_pairs == (("a", "b"),)  # a and b agree everywhere in the pool


def test_design_inputs_reports_pairs_the_pool_cannot_separate() -> None:
    references = {"a": lambda data: 0, "b": lambda data: 0}

    design = design_inputs(("a", "b"), references, pool=(b"\x00", b"\x01"))

    assert design.inputs == ()
    assert design.indistinguishable_pairs == (("a", "b"),)


def test_design_inputs_ignores_candidates_without_a_reference() -> None:
    design = design_inputs(("crc32", "no_such_primitive"), REFERENCES)

    assert all(
        "no_such_primitive" not in pair for pair in design.indistinguishable_pairs
    )


@pytest.mark.toolchain
def test_load_held_out_inputs_reads_the_real_file() -> None:
    inputs = load_held_out_inputs(ROOT)

    assert len(inputs) > 0
    public_inputs = set(
        json.loads((ROOT / "corpus" / "reference_vectors.json").read_text())["inputs_hex"]
    )
    assert set(inputs).isdisjoint(public_inputs)


def test_load_held_out_inputs_returns_empty_tuple_when_missing(tmp_path: Path) -> None:
    assert load_held_out_inputs(tmp_path) == ()


@pytest.mark.toolchain
def test_verdict_for_unknown_primitive_is_inconclusive() -> None:
    verdict = verdict_for(ROOT / "corpus" / "bin" / "crc32_clean", "nope", CLOSED_WORLD, REFERENCES)

    assert verdict.verdict == "inconclusive"
    assert verdict.evidence[0].error == "unknown primitive: nope"


@pytest.mark.toolchain
def test_verdict_for_confirms_the_true_closed_world_primitive() -> None:
    binary = ROOT / "corpus" / "bin" / "crc32_clean"

    verdict = verdict_for(binary, "crc32", CLOSED_WORLD, REFERENCES, root=ROOT)

    assert verdict.verdict == "confirmed"
    assert len(verdict.evidence) > len(load_held_out_inputs(ROOT))  # designed inputs were added too


@pytest.mark.toolchain
def test_verdict_for_refutes_a_wrong_closed_world_primitive() -> None:
    binary = ROOT / "corpus" / "bin" / "crc32_clean"

    verdict = verdict_for(binary, "djb2", CLOSED_WORLD, REFERENCES, root=ROOT)

    assert verdict.verdict == "refuted"


@pytest.mark.toolchain
def test_verdict_for_separates_jamcrc_from_crc32_in_open_world() -> None:
    """jamcrc_clean's real binary should confirm as jamcrc and refute as crc32,
    even though the two share the exact same polynomial constant."""
    entries = load_kb_entries(ROOT)
    candidates = open_world_candidates(entries)
    binary = ROOT / "corpus" / "bin" / "jamcrc_clean"

    confirmed = verdict_for(binary, "jamcrc", candidates, KB_REFERENCES, root=ROOT)
    refuted = verdict_for(binary, "crc32", candidates, KB_REFERENCES, root=ROOT)

    assert confirmed.verdict == "confirmed"
    assert refuted.verdict == "refuted"
