"""V-11 acceptance: every kb/algorithms.json entry is validated or excluded."""

import json
from pathlib import Path

from egre.knowledge.refs import KB_REFERENCES

ROOT = Path(__file__).resolve().parents[2]
ENTRIES = json.loads((ROOT / "kb" / "algorithms.json").read_text())
EXCLUDED = {"elf_hash", "sdbm", "djb2a"}


def test_every_kb_entry_is_marked_validated() -> None:
    unvalidated = [entry["id"] for entry in ENTRIES if not entry["validated"]]
    assert unvalidated == [], f"unvalidated entries must be excluded, not shipped: {unvalidated}"


def test_excluded_algorithms_are_not_present_in_the_kb_file() -> None:
    present_ids = {entry["id"] for entry in ENTRIES}
    assert present_ids.isdisjoint(EXCLUDED)


def test_every_kb_entry_has_a_reference_implementation() -> None:
    missing = [entry["id"] for entry in ENTRIES if entry["id"] not in KB_REFERENCES]
    assert missing == []


def test_every_public_vector_matches_its_reference_implementation() -> None:
    for entry in ENTRIES:
        reference = KB_REFERENCES[entry["id"]]
        for vector in entry["public_vectors"]:
            data = bytes.fromhex(vector["input_hex"])
            expected = int(vector["output_hex"], 16)
            actual = reference(data)
            assert actual == expected, (
                f"{entry['id']}({vector['input_hex']!r}): {actual:#010x} != {expected:#010x}"
            )


def test_kb_references_has_no_unvalidated_extras() -> None:
    """KB_REFERENCES should only serve algorithms the KB file actually lists."""
    entry_ids = {entry["id"] for entry in ENTRIES}
    assert set(KB_REFERENCES) == entry_ids
