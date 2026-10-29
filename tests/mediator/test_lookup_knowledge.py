import json
from pathlib import Path

import pytest

from egre.ledger.store import UnknownHandleError
from egre.mediator.tools import MediatorTools

pytestmark = pytest.mark.toolchain

ROOT = Path(__file__).resolve().parents[2]


def _task(program: str = "crc32_clean") -> dict[str, object]:
    return json.loads((ROOT / "corpus" / "tasks" / f"{program}.json").read_text())


def test_lookup_knowledge_returns_matches_with_k_handles() -> None:
    tools = MediatorTools(_task(), root=ROOT)

    result = tools.lookup_knowledge("0xEDB88320")

    ids = {match["id"] for match in result["matches"]}
    assert ids == {"crc32", "jamcrc"}
    assert all(match["handle"].startswith("K-") for match in result["matches"])


def test_lookup_knowledge_does_not_record_anything_in_the_ledger() -> None:
    tools = MediatorTools(_task(), root=ROOT)

    tools.lookup_knowledge("crc")
    tools.lookup_knowledge("0xEDB88320")

    assert tools.observations.all() == ()


def test_i7_a_knowledge_handle_cannot_be_resolved_as_an_observation() -> None:
    """I7: knowledge never counts as evidence -- a K-<id> handle fails closed
    exactly like any other unknown handle, so it can never be cited."""
    tools = MediatorTools(_task(), root=ROOT)
    result = tools.lookup_knowledge("0xEDB88320")
    handle = result["matches"][0]["handle"]

    with pytest.raises(UnknownHandleError):
        tools.observations.get(handle)


def test_i10_lookup_knowledge_never_exposes_held_out_content() -> None:
    """I10: only each entry's own public_vectors are ever returned."""
    tools = MediatorTools(_task(), root=ROOT)
    held_out = json.loads((ROOT / "corpus" / "held_out_vectors.json").read_text())
    held_out_inputs = set(held_out["inputs_hex"])

    result = tools.lookup_knowledge("crc")

    for match in result["matches"]:
        vector_inputs = {vector["input_hex"] for vector in match["public_vectors"]}
        assert vector_inputs.isdisjoint(held_out_inputs)
