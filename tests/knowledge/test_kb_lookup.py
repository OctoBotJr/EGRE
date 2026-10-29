from pathlib import Path

from egre.knowledge.kb import load_kb_entries, lookup_knowledge

ROOT = Path(__file__).resolve().parents[2]


def test_load_kb_entries_reads_the_real_file() -> None:
    entries = load_kb_entries(ROOT)

    ids = {entry["id"] for entry in entries}
    assert "crc32" in ids
    assert "elf_hash" not in ids  # excluded per V-11


def test_load_kb_entries_returns_empty_tuple_when_file_is_missing(tmp_path: Path) -> None:
    assert load_kb_entries(tmp_path) == ()


def test_exact_constant_match_finds_every_entry_sharing_that_value() -> None:
    entries = load_kb_entries(ROOT)

    matches = lookup_knowledge("0xEDB88320", entries)

    ids = {match["id"] for match in matches}
    assert ids == {"crc32", "jamcrc"}  # jamcrc shares CRC-32's polynomial by design
    assert all(match["handle"] == f"K-{match['id']}" for match in matches)


def test_exact_constant_match_accepts_decimal_too() -> None:
    entries = load_kb_entries(ROOT)

    hex_matches = lookup_knowledge("0xEDB88320", entries)
    decimal_matches = lookup_knowledge(str(0xEDB88320), entries)

    assert {m["id"] for m in hex_matches} == {m["id"] for m in decimal_matches}


def test_shared_fnv_constant_matches_both_fnv_variants() -> None:
    entries = load_kb_entries(ROOT)

    matches = lookup_knowledge("0x811C9DC5", entries)

    assert {match["id"] for match in matches} == {"fnv1a32", "fnv1_32"}


def test_keyword_match_is_case_insensitive_substring_over_id_family_and_description() -> None:
    entries = load_kb_entries(ROOT)

    matches = lookup_knowledge("CRC", entries)

    assert {match["id"] for match in matches} == {"crc32", "jamcrc", "crc32c"}


def test_unmatched_query_returns_no_results() -> None:
    entries = load_kb_entries(ROOT)

    assert lookup_knowledge("sha256", entries) == ()


def test_blank_query_matches_nothing_not_everything() -> None:
    entries = load_kb_entries(ROOT)

    assert lookup_knowledge("   ", entries) == ()


def test_public_view_excludes_internal_validation_bookkeeping() -> None:
    entries = load_kb_entries(ROOT)

    match = next(m for m in lookup_knowledge("0xEDB88320", entries) if m["id"] == "crc32")

    assert "validated" not in match
    assert "validation_note" not in match
    assert set(match) == {
        "id",
        "family",
        "aliases",
        "description",
        "parameters",
        "signature_constants",
        "public_vectors",
        "handle",
    }
