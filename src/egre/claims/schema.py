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


class Registry:
    """Insertion-ordered claim registry, capped at three claims per run."""

    MAX_CLAIMS = 3

    def __init__(self, claims: Iterable[Claim] = ()) -> None:
        self._claims: list[Claim] = []
        self._ids: set[str] = set()
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

    def __iter__(self) -> Iterator[Claim]:
        return iter(self._claims)

    def __len__(self) -> int:
        return len(self._claims)

