import json
from pathlib import Path

import pytest

from egre.cli.run import LOCAL_OLLAMA_BASE_URL, main, sanitize_model
from egre.llm.fake import FakeLLM

ROOT = Path(__file__).parents[2]


def test_sanitize_model_replaces_colon_and_slash() -> None:
    assert sanitize_model("qwen3.5:4b/test") == "qwen3.5-4b-test"


@pytest.mark.toolchain
def test_run_cli_writes_settings_raw_steps_and_resumes_without_network(tmp_path: Path) -> None:
    out = tmp_path / "local-run"
    factory_calls = 0

    def adapter_factory(**kwargs: object) -> FakeLLM:
        nonlocal factory_calls
        factory_calls += 1
        assert kwargs["base_url"] == LOCAL_OLLAMA_BASE_URL
        assert kwargs["temperature"] == 0.2
        assert kwargs["max_tokens"] == 700
        assert kwargs["timeout"] == 120.0
        return FakeLLM(["local prose", '{"action":"finish"}'])

    argv = [
        "--llm",
        "openai",
        "--model",
        "qwen3.5:4b",
        "--base-url",
        LOCAL_OLLAMA_BASE_URL,
        "--programs",
        "crc32_clean",
        "--repeats",
        "1",
        "--out",
        str(out),
    ]

    assert main(argv, root=ROOT, adapter_factory=adapter_factory) == 0
    path = out / "crc32_clean-repeat-001.json"
    document = json.loads(path.read_text())
    assert document["model"] == "qwen3.5:4b"
    assert document["settings"] == {
        "base_url": LOCAL_OLLAMA_BASE_URL,
        "temperature": 0.2,
        "max_tokens": 700,
        "timeout": 120.0,
        "hypotheses": False,
        "query_graph": False,
        "revision": False,
        "knowledge": False,
    }
    assert document["invalid_steps"] == 1
    assert [step["raw_response"] for step in document["steps"]] == [
        "local prose",
        '{"action":"finish"}',
    ]
    first_step_messages = document["steps"][0]["messages_sent"]
    assert [message["role"] for message in first_step_messages] == ["system", "user"]
    second_step_messages = document["steps"][1]["messages_sent"]
    assert [message["role"] for message in second_step_messages] == [
        "system",
        "user",
        "user",
    ]
    assert document["tool_calls"] == []
    assert document["ledger"] == []
    assert document["claims"] == []
    assert document["state"] == "completed"

    assert main(argv, root=ROOT, adapter_factory=adapter_factory) == 0
    assert factory_calls == 1


@pytest.mark.toolchain
def test_run_cli_hypotheses_flag_requires_schema_and_sets_response_format(tmp_path: Path) -> None:
    out = tmp_path / "local-run"
    captured: dict[str, object] = {}

    def adapter_factory(**kwargs: object) -> FakeLLM:
        captured.update(kwargs)
        action_json = (
            '{"action":"finish","hypotheses":{"crc32":0.9,"fnv1a32":0.05,'
            '"adler32":0.03,"djb2":0.01,"other":0.01}}'
        )
        return FakeLLM([action_json])

    argv = [
        "--llm",
        "openai",
        "--model",
        "qwen3.5:4b",
        "--base-url",
        LOCAL_OLLAMA_BASE_URL,
        "--programs",
        "crc32_clean",
        "--repeats",
        "1",
        "--out",
        str(out),
        "--hypotheses",
    ]

    assert main(argv, root=ROOT, adapter_factory=adapter_factory) == 0
    document = json.loads((out / "crc32_clean-repeat-001.json").read_text())

    assert "response_format" in captured
    assert document["settings"]["hypotheses"] is True
    assert document["invalid_steps"] == 0
    assert document["steps"][0]["action"]["hypotheses"]["crc32"] == 0.9


def test_run_cli_rejects_nonlocal_base_url(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="local Ollama"):
        main(
            [
                "--model",
                "qwen3.5:4b",
                "--base-url",
                "https://api.example.test/v1",
                "--programs",
                "crc32_clean",
                "--repeats",
                "1",
                "--out",
                str(tmp_path),
            ],
            root=ROOT,
        )
