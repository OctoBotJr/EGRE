"""Typed T2 claims and the per-run claim registry."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Primitive = Literal["crc32", "fnv1a32", "adler32", "djb2", "other"]


class Claim(BaseModel):
    """A validated prototype claim submitted by an agent."""

    model_config = ConfigDict(frozen=True, strict=True)

    id: Annotated[str, Field(min_length=1)]
    function_addr: Annotated[int, Field(ge=0)]
    primitive: Primitive
    cited_handles: tuple[str, ...] = ()
    confidence: Annotated[float, Field(ge=0.0, le=1.0)]

    @field_validator("id")
    @classmethod
    def _id_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("claim id must not be blank")
        return value

    @field_validator("cited_handles", mode="before")
    @classmethod
    def _normalize_handles(cls, value: object) -> object:
        if not isinstance(value, (list, tuple)):
            return value
        unique: list[object] = []
        for handle in value:
            if handle not in unique:
                unique.append(handle)
        return tuple(unique)

    @field_validator("cited_handles")
    @classmethod
    def _handles_must_not_be_blank(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not handle.strip() for handle in value):
            raise ValueError("cited handles must not be blank")
        return value


class RegistryFullError(ValueError):
    """The prototype's per-run claim limit was exceeded."""


class RevisionLimitError(ValueError):
    """A claim has already been revised the maximum number of times (R3)."""


class Registry:
    """Insertion-ordered claim registry, capped at three claims per run."""

    MAX_CLAIMS = 3
    MAX_REVISIONS = 2

    def __init__(self, claims: Iterable[Claim] = ()) -> None:
        self._claims: list[Claim] = []
        self._ids: set[str] = set()
        self._revisions: dict[str, int] = {}
        for claim in claims:
            self.add(claim)

    @property
    def claims(self) -> tuple[Claim, ...]:
        return tuple(self._claims)

    def add(self, claim: Claim) -> None:
        if claim.id in self._ids:
            raise ValueError(f"duplicate claim id: {claim.id}")
        if len(self._claims) >= self.MAX_CLAIMS:
            raise RegistryFullError(f"a registry accepts at most {self.MAX_CLAIMS} claims")
        self._claims.append(claim)
        self._ids.add(claim.id)
        self._revisions[claim.id] = 0

    def revisions(self, claim_id: str) -> int:
        """How many times ``claim_id`` has been revised so far (R3)."""
        return self._revisions.get(claim_id, 0)

    def revise(self, claim_id: str, claim: Claim) -> None:
        """Replace an existing claim with a new version, up to MAX_REVISIONS times (R3)."""
        if claim_id not in self._ids:
            raise ValueError(f"no claim to revise: {claim_id}")
        if claim.id != claim_id:
            raise ValueError("a revised claim must keep the same id")
        if self._revisions[claim_id] >= self.MAX_REVISIONS:
            raise RevisionLimitError(
                f"claim {claim_id} has already been revised {self.MAX_REVISIONS} times"
            )
        index = next(i for i, existing in enumerate(self._claims) if existing.id == claim_id)
        self._claims[index] = claim
        self._revisions[claim_id] += 1

    def retract(self, claim_id: str) -> None:
        """Remove a claim entirely, freeing its slot for a new one (R3)."""
        if claim_id not in self._ids:
            raise ValueError(f"no claim to retract: {claim_id}")
        self._claims = [claim for claim in self._claims if claim.id != claim_id]
        self._ids.discard(claim_id)
        self._revisions.pop(claim_id, None)

    def __iter__(self) -> Iterator[Claim]:
        return iter(self._claims)

    def __len__(self) -> int:
        return len(self._claims)

