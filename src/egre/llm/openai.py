"""Lazy, import-safe adapter for OpenAI chat completions."""

from __future__ import annotations

import os
from collections.abc import Callable, Sequence
from functools import partial
from typing import Any

from egre.llm.base import CompletionResult, LLMResponse, Message, TokenUsage

Transport = Callable[[str, tuple[Message, ...], str], CompletionResult]
ClientFactory = Callable[..., Any]


class MissingAPIKeyError(RuntimeError):
    """The real provider was called without configured credentials."""


class LLMTimeoutError(TimeoutError):
    """One provider request exceeded its configured deadline."""


def _optional_int(value: object, name: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"provider usage {name} must be an integer or null")
    return value


def _default_transport(
    model: str,
    messages: tuple[Message, ...],
    api_key: str,
    *,
    base_url: str | None,
    temperature: float,
    max_tokens: int,
    timeout: float,
    client_factory: ClientFactory | None,
    response_format: dict[str, object] | None = None,
) -> LLMResponse:
    factory: Any = client_factory
    if client_factory is None:
        # The optional SDK remains behind the actual provider-call boundary.
        from openai import OpenAI

        factory = OpenAI

    client_kwargs: dict[str, object] = {"api_key": api_key, "timeout": timeout}
    if base_url is not None:
        client_kwargs["base_url"] = base_url
    client = factory(**client_kwargs)
    request_messages: Any = [dict(message) for message in messages]
    request_kwargs: dict[str, object] = {
        "model": model,
        "messages": request_messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if response_format is not None:
        request_kwargs["response_format"] = response_format
    response = client.chat.completions.create(**request_kwargs)
    message = response.choices[0].message
    content = message.content
    if content is None:
        raise RuntimeError("OpenAI returned an empty response")
    reasoning = getattr(message, "reasoning_content", None)
    if reasoning is None:
        reasoning = getattr(message, "reasoning", None)
    if reasoning is not None and not isinstance(reasoning, str):
        reasoning = str(reasoning)
    raw_response = (
        response.model_dump_json()
        if callable(getattr(response, "model_dump_json", None))
        else repr(response)
    )
    usage = getattr(response, "usage", None)
    return LLMResponse(
        content=content,
        raw_response=raw_response,
        reasoning=reasoning,
        usage=TokenUsage(
            prompt_tokens=_optional_int(getattr(usage, "prompt_tokens", None), "prompt_tokens"),
            completion_tokens=_optional_int(
                getattr(usage, "completion_tokens", None), "completion_tokens"
            ),
            total_tokens=_optional_int(getattr(usage, "total_tokens", None), "total_tokens"),
        ),
    )


class OpenAIAdapter:
    """Real provider adapter whose SDK and credentials are resolved only on use."""

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 700,
        timeout: float = 120.0,
        transport: Transport | None = None,
        client_factory: ClientFactory | None = None,
        response_format: dict[str, object] | None = None,
    ) -> None:
        if not model.strip():
            raise ValueError("model must not be blank")
        resolved_base_url = base_url or os.environ.get("OPENAI_BASE_URL")
        if resolved_base_url is not None and not resolved_base_url.strip():
            raise ValueError("base_url must not be blank")
        if isinstance(max_tokens, bool) or not isinstance(max_tokens, int) or max_tokens <= 0:
            raise ValueError("max_tokens must be a positive integer")
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or timeout <= 0:
            raise ValueError("timeout must be positive")
        if isinstance(temperature, bool) or not isinstance(temperature, (int, float)):
            raise TypeError("temperature must be numeric")
        self.model = model
        self.base_url = resolved_base_url
        self.temperature = float(temperature)
        self.max_tokens = max_tokens
        self.timeout = float(timeout)
        self._api_key = api_key
        self.response_format = response_format
        self._transport = transport or partial(
            _default_transport,
            base_url=self.base_url,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            timeout=self.timeout,
            client_factory=client_factory,
            response_format=response_format,
        )

    def complete(self, messages: Sequence[Message]) -> CompletionResult:
        api_key = self._api_key or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise MissingAPIKeyError("OPENAI_API_KEY is required for a real provider call")
        try:
            return self._transport(self.model, tuple(messages), api_key)
        except TimeoutError as exc:
            raise LLMTimeoutError(str(exc) or "provider request timed out") from exc
        except Exception as exc:
            if type(exc).__name__ in {"APITimeoutError", "ReadTimeout", "ConnectTimeout"}:
                raise LLMTimeoutError(str(exc) or "provider request timed out") from exc
            raise


OpenAIClient = OpenAIAdapter

