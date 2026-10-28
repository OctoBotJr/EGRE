"""Lazy, import-safe adapter for OpenAI chat completions."""

from __future__ import annotations

import os
from collections.abc import Callable, Sequence

from egre.llm.base import Message

Transport = Callable[[str, tuple[Message, ...], str], str]


class MissingAPIKeyError(RuntimeError):
    """The real provider was called without configured credentials."""


def _default_transport(model: str, messages: tuple[Message, ...], api_key: str) -> str:
    # Optional SDK import remains behind the actual paid call boundary.
    from openai import OpenAI

    response = OpenAI(api_key=api_key).chat.completions.create(
        model=model,
        messages=[dict(message) for message in messages],  # type: ignore[arg-type]
        response_format={"type": "json_object"},
    )
    content = response.choices[0].message.content
    if content is None:
        raise RuntimeError("OpenAI returned an empty response")
    return content


class OpenAIAdapter:
    """Real provider adapter whose SDK and credentials are resolved only on use."""

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        *,
        api_key: str | None = None,
        transport: Transport | None = None,
    ) -> None:
        if not model.strip():
            raise ValueError("model must not be blank")
        self.model = model
        self._api_key = api_key
        self._transport = transport or _default_transport

    def complete(self, messages: Sequence[Message]) -> str:
        api_key = self._api_key or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise MissingAPIKeyError("OPENAI_API_KEY is required for a real provider call")
        return self._transport(self.model, tuple(messages), api_key)


OpenAIClient = OpenAIAdapter

