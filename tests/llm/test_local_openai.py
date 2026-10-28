import json
from types import SimpleNamespace

import pytest

from egre.llm.base import LLMResponse, Message
from egre.llm.openai import LLMTimeoutError, OpenAIAdapter


def test_openai_adapter_honors_local_settings_and_extracts_full_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_BASE_URL", "http://localhost:11434/v1")
    captured_client: dict[str, object] = {}
    captured_request: dict[str, object] = {}

    class FakeCompletions:
        def create(self, **kwargs: object) -> object:
            captured_request.update(kwargs)
            message = SimpleNamespace(
                content='```json\n{"action":"finish"}\n```',
                reasoning_content="<think>local reasoning</think>",
            )
            usage = SimpleNamespace(prompt_tokens=11, completion_tokens=7, total_tokens=18)
            return SimpleNamespace(
                choices=[SimpleNamespace(message=message)],
                usage=usage,
                model_dump_json=lambda: json.dumps({"complete": "raw-response"}),
            )

    class FakeClient:
        def __init__(self) -> None:
            self.chat = SimpleNamespace(completions=FakeCompletions())

    def client_factory(**kwargs: object) -> FakeClient:
        captured_client.update(kwargs)
        return FakeClient()

    adapter = OpenAIAdapter(
        model="qwen3.5:4b",
        api_key="ollama",
        temperature=0.2,
        max_tokens=700,
        timeout=120.0,
        client_factory=client_factory,
    )
    messages: tuple[Message, ...] = ({"role": "user", "content": "next action"},)

    result = adapter.complete(messages)

    assert isinstance(result, LLMResponse)
    assert adapter.base_url == "http://localhost:11434/v1"
    assert captured_client == {
        "api_key": "ollama",
        "base_url": "http://localhost:11434/v1",
        "timeout": 120.0,
    }
    assert captured_request["model"] == "qwen3.5:4b"
    assert captured_request["temperature"] == 0.2
    assert captured_request["max_tokens"] == 700
    assert result.content.startswith("```json")
    assert result.reasoning == "<think>local reasoning</think>"
    assert json.loads(result.raw_response) == {"complete": "raw-response"}
    assert result.usage.prompt_tokens == 11
    assert result.usage.completion_tokens == 7
    assert result.usage.total_tokens == 18


def test_openai_adapter_explicit_base_url_overrides_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_BASE_URL", "http://localhost:9999/v1")
    adapter = OpenAIAdapter(
        model="qwen3.5:4b",
        base_url="http://localhost:11434/v1",
    )

    assert adapter.base_url == "http://localhost:11434/v1"


def test_openai_adapter_converts_transport_timeout_without_retry() -> None:
    calls = 0

    def transport(model: str, messages: tuple[Message, ...], api_key: str) -> str:
        del model, messages, api_key
        nonlocal calls
        calls += 1
        raise TimeoutError("local request timed out")

    adapter = OpenAIAdapter(
        model="qwen3.5:4b",
        api_key="ollama",
        transport=transport,
    )

    with pytest.raises(LLMTimeoutError, match="timed out"):
        adapter.complete(())
    assert calls == 1
