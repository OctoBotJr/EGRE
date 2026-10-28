"""Append-only observation ledger and its read-only capability."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Literal, TypeAlias

ObservationKind: TypeAlias = Literal["disasm", "memory", "run"]
ObservationValue: TypeAlias = str | int | float | bool | None
ObservationPayload: TypeAlias = str | int


class UnknownHandleError(KeyError):
    """An observation handle was not issued by this ledger."""


@dataclass(frozen=True)
class Anchor:
    """Half-open virtual-address range associated with an observation."""

    start: int
    end: int

    def __post_init__(self) -> None:
        if self.start < 0 or self.end <= self.start:
            raise ValueError("anchor must be a non-empty non-negative range")


@dataclass(frozen=True)
class Observation:
    """Immutable evidence emitted by an allowlisted runtime tool."""

    handle: str
    kind: ObservationKind
    tool: str
    args: Mapping[str, ObservationValue]
    anchor: Anchor
    payload: ObservationPayload
    facts: frozenset[int]
    ts: str


class LedgerReader:
    """Read-only ledger capability suitable for agent-facing code."""

    __slots__ = ("__ledger",)

    def __init__(self, ledger: Ledger) -> None:
        self.__ledger = ledger

    def get(self, handle: str) -> Observation:
        return self.__ledger.get(handle)

    def all(self) -> tuple[Observation, ...]:
        return self.__ledger.all()

    def __len__(self) -> int:
        return len(self.__ledger)


class Ledger:
    """Runtime-owned append-only store for tool observations."""

    def __init__(self) -> None:
        self._observations: dict[str, Observation] = {}
        self._reader = LedgerReader(self)

    def record(
        self,
        *,
        kind: ObservationKind,
        tool: str,
        args: Mapping[str, ObservationValue],
        anchor: Anchor,
        payload: ObservationPayload,
        facts: Iterable[int] = (),
    ) -> Observation:
        handle = f"obs-{len(self._observations) + 1:06d}"
        observation = Observation(
            handle=handle,
            kind=kind,
            tool=tool,
            args=MappingProxyType(dict(args)),
            anchor=anchor,
            payload=payload,
            facts=frozenset(facts),
            ts=datetime.now(UTC).isoformat(),
        )
        self._observations[handle] = observation
        return observation

    def get(self, handle: str) -> Observation:
        try:
            return self._observations[handle]
        except KeyError as exc:
            raise UnknownHandleError(f"unknown observation handle: {handle}") from exc

    def all(self) -> tuple[Observation, ...]:
        return tuple(self._observations.values())

    def reader(self) -> LedgerReader:
        return self._reader

    def __len__(self) -> int:
        return len(self._observations)

