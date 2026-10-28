"""Small provider-neutral interface used by the prototype agent loop."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal, Protocol, TypedDict


class Message(TypedDict):
    """One text message in an LLM conversation."""

    role: Literal["system", "user", "assistant"]
    content: str


class LLMClient(Protocol):
    """A client that returns one JSON action as text."""

    def complete(self, messages: Sequence[Message]) -> str:
        """Return the next assistant response for the supplied conversation."""

