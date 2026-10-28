"""Small provider-neutral interface used by the prototype agent loop."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, Protocol, TypedDict


class Message(TypedDict):
    """One text message in an LLM conversation."""

    role: Literal["system", "user", "assistant"]
    content: str


@dataclass(frozen=True, slots=True)
class TokenUsage:
    """Provider token counts when the endpoint reports them."""

    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None

    def plus(self, other: TokenUsage) -> TokenUsage:
        def add(left: int | None, right: int | None) -> int | None:
            if left is None and right is None:
                return None
            return (left or 0) + (right or 0)

        return TokenUsage(
            prompt_tokens=add(self.prompt_tokens, other.prompt_tokens),
            completion_tokens=add(self.completion_tokens, other.completion_tokens),
            total_tokens=add(self.total_tokens, other.total_tokens),
        )


@dataclass(frozen=True, slots=True)
class LLMResponse:
    """Normalized answer plus the complete provider response retained for audit."""

    content: str
    raw_response: str
    reasoning: str | None = None
    usage: TokenUsage = TokenUsage()


CompletionResult = str | LLMResponse


class LLMClient(Protocol):
    """A client that returns one action response."""

    def complete(self, messages: Sequence[Message]) -> CompletionResult:
        """Return the next assistant response for the supplied conversation."""

