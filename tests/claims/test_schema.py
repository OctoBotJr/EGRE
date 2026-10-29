import pytest
from pydantic import ValidationError

from egre.claims.schema import Claim, Registry, RegistryFullError, RevisionLimitError


def _claim(claim_id: str = "c1", **changes: object) -> Claim:
    values: dict[str, object] = {
        "id": claim_id,
        "function_addr": 0x1000,
        "primitive": "crc32",
        "cited_handles": ["obs-000001"],
        "confidence": 0.75,
    }
    values.update(changes)
    return Claim(**values)


def test_claim_is_validated_and_immutable() -> None:
    claim = _claim(cited_handles=["obs-1", "obs-1", "obs-2"])

    assert claim.cited_handles == ("obs-1", "obs-2")
    with pytest.raises(ValidationError):
        _claim(primitive="sha256")
    with pytest.raises(ValidationError):
        _claim(confidence=1.01)
    with pytest.raises(ValidationError):
        claim.confidence = 0.5


def test_registry_preserves_submission_order_and_caps_each_run_at_three() -> None:
    registry = Registry()
    claims = [_claim(f"c{number}") for number in range(1, 5)]

    for claim in claims[:3]:
        registry.add(claim)

    assert registry.claims == tuple(claims[:3])
    assert tuple(registry) == tuple(claims[:3])
    with pytest.raises(RegistryFullError, match="at most 3"):
        registry.add(claims[3])


def test_registry_rejects_duplicate_claim_ids() -> None:
    registry = Registry([_claim("same")])

    with pytest.raises(ValueError, match="duplicate claim id"):
        registry.add(_claim("same", primitive="djb2"))


def test_registry_revise_replaces_in_place_and_counts_revisions() -> None:
    registry = Registry([_claim("c1", primitive="crc32"), _claim("c2", primitive="djb2")])

    registry.revise("c1", _claim("c1", primitive="fnv1a32"))

    assert [claim.primitive for claim in registry.claims] == ["fnv1a32", "djb2"]
    assert registry.revisions("c1") == 1
    assert registry.revisions("c2") == 0


def test_registry_revise_caps_at_max_revisions() -> None:
    registry = Registry([_claim("c1")])

    registry.revise("c1", _claim("c1", confidence=0.6))
    registry.revise("c1", _claim("c1", confidence=0.7))

    with pytest.raises(RevisionLimitError, match="already been revised 2 times"):
        registry.revise("c1", _claim("c1", confidence=0.8))


def test_registry_revise_rejects_unknown_id_or_mismatched_claim_id() -> None:
    registry = Registry([_claim("c1")])

    with pytest.raises(ValueError, match="no claim to revise"):
        registry.revise("missing", _claim("missing"))
    with pytest.raises(ValueError, match="same id"):
        registry.revise("c1", _claim("c2"))


def test_registry_retract_removes_the_claim_and_frees_a_slot() -> None:
    registry = Registry([_claim(f"c{number}") for number in range(1, 4)])

    registry.retract("c2")

    assert [claim.id for claim in registry.claims] == ["c1", "c3"]
    registry.add(_claim("c4"))  # the freed slot accepts a new claim
    assert len(registry) == 3


def test_registry_retract_rejects_unknown_id() -> None:
    registry = Registry([_claim("c1")])

    with pytest.raises(ValueError, match="no claim to retract"):
        registry.retract("missing")

