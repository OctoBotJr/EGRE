from collections.abc import Sequence
from typing import cast

from egre.agent.loop import AgentLoop
from egre.ledger.store import Anchor, Ledger
from egre.llm.base import LLMClient, LLMResponse, Message, TokenUsage
from egre.llm.fake import FakeLLM
from egre.llm.openai import LLMTimeoutError
from egre.mediator.tools import MediatorTools, ToolResult


class FakeTools:
    def __init__(self) -> None:
        self._ledger = Ledger()
        self.observations = self._ledger.reader()

    def disassemble(self, addr: int, count: int) -> ToolResult:
        observation = self._ledger.record(
            kind="disasm",
            tool="disassemble",
            args={"addr": addr, "count": count},
            anchor=Anchor(addr, addr + 4),
            payload="0x1000: mov w8, #0x8320",
            facts={0x8320},
        )
        return ToolResult(
            observation.handle,
            observation.kind,
            observation.anchor,
            observation.payload,
            observation.facts,
        )

    def read_memory(self, addr: int, n: int) -> ToolResult:
        raise AssertionError((addr, n))

    def run(self, input_hex: str) -> ToolResult:
        raise AssertionError(input_hex)


class TimeoutThenFinish:
    def __init__(self) -> None:
        self.calls = 0

    def complete(self, messages: Sequence[Message]) -> str:
        del messages
        self.calls += 1
        if self.calls == 1:
            raise LLMTimeoutError("timed out")
        return '{"action":"finish"}'


class SingleResponse:
    def __init__(self, response: LLMResponse) -> None:
        self.response = response

    def complete(self, messages: Sequence[Message]) -> LLMResponse:
        del messages
        return self.response


def _loop(client: LLMClient, *, max_steps: int = 12) -> AgentLoop:
    task = {"function_addr": 0x1000, "function_size": 16, "binary": "unused"}
    tools = cast(MediatorTools, FakeTools())
    return AgentLoop(task, tools, client, max_steps=max_steps)


def test_detailed_loop_strips_thinking_fences_and_extra_prose_but_logs_raw() -> None:
    raw = (
        "<think>choose to stop</think>\nHere is the action:\n"
        "```json\n{\"action\":\"finish\"}\n```\nDone."
    )

    result = _loop(FakeLLM([raw])).run_detailed()

    assert result.registry.claims == ()
    assert result.invalid_steps == 0
    assert result.stop_reason == "finish"
    assert result.steps[0].raw_response == raw
    assert result.steps[0].action == {"action": "finish"}


def test_detailed_loop_records_separate_reasoning_and_token_usage() -> None:
    response = LLMResponse(
        content='{"action":"finish"}',
        raw_response='{"full":"provider response"}',
        reasoning="private local reasoning",
        usage=TokenUsage(prompt_tokens=5, completion_tokens=3, total_tokens=8),
    )

    result = _loop(SingleResponse(response)).run_detailed()

    assert result.steps[0].raw_response == '{"full":"provider response"}'
    assert result.steps[0].reasoning == "private local reasoning"
    assert result.usage.total_tokens == 8


def test_unparseable_and_timeout_steps_are_counted_without_silent_retry() -> None:
    malformed = _loop(FakeLLM(["not JSON", '{"action":"finish"}'])).run_detailed()
    timeout_client = TimeoutThenFinish()
    timed_out = _loop(timeout_client).run_detailed()

    assert malformed.invalid_steps == 1
    assert len(malformed.steps) == 2
    assert malformed.steps[0].error == "assistant response did not contain a JSON action object"
    assert timed_out.invalid_steps == 1
    assert len(timed_out.steps) == 2
    assert timed_out.steps[0].error == "timed out"
    assert timeout_client.calls == 2


def test_detailed_loop_returns_zero_claim_result_at_step_limit() -> None:
    result = _loop(FakeLLM(["bad", "still bad"]), max_steps=2).run_detailed()

    assert result.registry.claims == ()
    assert result.invalid_steps == 2
    assert result.stop_reason == "max_steps"


def test_step_callback_receives_every_raw_model_response() -> None:
    seen: list[str | None] = []
    loop = _loop(FakeLLM(["bad", '{"action":"finish"}']))

    loop.run_detailed(on_step=lambda step: seen.append(step.raw_response))

    assert seen == ["bad", '{"action":"finish"}']


def test_step_records_exact_messages_sent_to_the_model() -> None:
    client = FakeLLM(
        ['{"action":"disassemble","addr":4096,"count":4}', '{"action":"finish"}']
    )

    result = _loop(client).run_detailed()

    assert len(result.steps) == 2 == len(client.calls)
    for step, call in zip(result.steps, client.calls, strict=True):
        assert step.messages_sent == call
    # the second call must carry the first step's action and tool observation
    assert result.steps[1].messages_sent[-2]["role"] == "assistant"
    assert result.steps[1].messages_sent[-1]["role"] == "user"
    assert "observation" in result.steps[1].messages_sent[-1]["content"]
