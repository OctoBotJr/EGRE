"""Deterministic replay client for tests and offline development."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from egre.llm.base import Message


class FakeLLM:
    """Replay fixed responses and retain an immutable view of every request."""

    def __init__(self, responses: Iterable[str]) -> None:
        self._responses = iter(responses)
        self._calls: list[tuple[Message, ...]] = []

    @property
    def calls(self) -> tuple[tuple[Message, ...], ...]:
        return tuple(self._calls)

    def complete(self, messages: Sequence[Message]) -> str:
        self._calls.append(tuple(messages))
        try:
            return next(self._responses)
        except StopIteration as exc:
            raise RuntimeError("fake LLM has no scripted response remaining") from exc

