import pytest
from pydantic import ValidationError

from egre.claims.schema import Claim, Registry, RegistryFullError


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

