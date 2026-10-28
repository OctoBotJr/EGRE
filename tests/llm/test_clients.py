import importlib
import json

import pytest

from egre.llm.base import Message
from egre.llm.fake import FakeLLM
from egre.llm.openai import MissingAPIKeyError, OpenAIAdapter


def test_fake_llm_replays_responses_and_records_messages() -> None:
    client = FakeLLM(['{"action":"finish"}'])
    messages: tuple[Message, ...] = ({"role": "user", "content": "start"},)

    assert json.loads(client.complete(messages)) == {"action": "finish"}
    assert client.calls == (messages,)


def test_fake_llm_rejects_exhausted_script() -> None:
    client = FakeLLM([])

    with pytest.raises(RuntimeError, match="no scripted response"):
        client.complete(())


def test_openai_adapter_imports_and_constructs_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    module = importlib.import_module("egre.llm.openai")

    adapter = module.OpenAIAdapter(model="test-model")

    assert adapter.model == "test-model"
    with pytest.raises(MissingAPIKeyError, match="OPENAI_API_KEY"):
        adapter.complete(({"role": "user", "content": "do not send"},))


def test_openai_adapter_uses_injected_transport_without_network() -> None:
    captured: list[tuple[str, tuple[Message, ...]]] = []

    def transport(model: str, messages: tuple[Message, ...], api_key: str) -> str:
        assert api_key == "local-test-key"
        captured.append((model, messages))
        return '{"action":"finish"}'

    adapter = OpenAIAdapter(model="test-model", api_key="local-test-key", transport=transport)
    messages: tuple[Message, ...] = ({"role": "user", "content": "hello"},)

    assert adapter.complete(messages) == '{"action":"finish"}'
    assert captured == [("test-model", messages)]
