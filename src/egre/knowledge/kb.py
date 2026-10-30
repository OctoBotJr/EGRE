"""Loader and lexical lookup for kb/algorithms.json (V2_SPEC.md section 5.2, V-11/V-12).

Lexical retrieval is deliberate (V2_SPEC.md section 4.3): the KB is small
and exact constants matter more than semantic similarity, so an embedding
index would be overkill. ``lookup_knowledge`` never touches
corpus/held_out_vectors.json (I10) -- it only ever reads this file's own
``public_vectors`` field, and the held-out file is never imported here.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

_PUBLIC_FIELDS = (
    "id",
    "family",
    "aliases",
    "description",
    "parameters",
    "signature_constants",
    "public_vectors",
)


def load_kb_entries(root: str | os.PathLike[str] = ".") -> tuple[dict[str, Any], ...]:
    """Every entry in kb/algorithms.json, or an empty tuple if the file doesn't exist yet."""
    path = Path(root) / "kb" / "algorithms.json"
    if not path.exists():
        return ()
    return tuple(json.loads(path.read_text()))


def _public_view(entry: dict[str, Any]) -> dict[str, Any]:
    view = {field: entry[field] for field in _PUBLIC_FIELDS if field in entry}
    view["handle"] = f"K-{entry['id']}"
    return view


def _parse_constant(query: str) -> int | None:
    try:
        return int(query, 16) if query.lower().startswith("0x") else int(query)
    except ValueError:
        return None


def _constant_values(entry: dict[str, Any]) -> set[int]:
    values = set()
    for constant in entry.get("signature_constants", ()):
        try:
            values.add(int(constant["value"], 16))
        except (KeyError, TypeError, ValueError):
            continue
    return values


def _keyword_matches(entry: dict[str, Any], needle: str) -> bool:
    haystack = " ".join(
        [
            str(entry.get("id", "")),
            str(entry.get("family", "")),
            " ".join(entry.get("aliases", ())),
            str(entry.get("description", "")),
        ]
    ).lower()
    return needle in haystack


def open_world_candidates(entries: tuple[dict[str, Any], ...]) -> tuple[str, ...]:
    """The open-world hypothesis set (V2_SPEC.md section 3.1, V-16): every KB entry id."""
    return tuple(entry["id"] for entry in entries)


def open_world_signatures(entries: tuple[dict[str, Any], ...]) -> dict[str, frozenset[int]]:
    """Signature-constant map for every KB entry, in the shape ``egre.support.engine.rel`` expects."""
    return {entry["id"]: frozenset(_constant_values(entry)) for entry in entries}


def lookup_knowledge(query: str, entries: tuple[dict[str, Any], ...]) -> tuple[dict[str, Any], ...]:
    """Exact constant-value match if ``query`` parses as a number, else a keyword match."""
    stripped = query.strip()
    constant = _parse_constant(stripped)
    if constant is not None:
        matches = [entry for entry in entries if constant in _constant_values(entry)]
    else:
        needle = stripped.lower()
        matches = [entry for entry in entries if needle and _keyword_matches(entry, needle)]
    return tuple(_public_view(entry) for entry in matches)
