from typing import cast

import pytest

from egre.agent.loop import AgentLoop
from egre.agent.replay import ReplayError, reconstruct_context, step_at
from egre.ledger.store import Anchor, Ledger
from egre.llm.base import Message
from egre.llm.fake import FakeLLM
from egre.mediator.tools import MediatorTools, ToolResult


class _FakeTools:
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


def _run(client: FakeLLM):
    task = {"function_addr": 0x1000, "function_size": 16, "binary": "unused"}
    tools = cast(MediatorTools, _FakeTools())
    loop = AgentLoop(task, tools, client)
    return loop.run_detailed()


def _document_from_steps(result) -> dict[str, object]:
    return {
        "steps": [
            {
                "index": step.index,
                "messages_sent": [dict(message) for message in step.messages_sent],
                "raw_response": step.raw_response,
                "action": step.action,
            }
            for step in result.steps
        ]
    }


def test_reconstruct_context_matches_the_original_conversation_at_each_step() -> None:
    client = FakeLLM(['{"action":"disassemble","addr":4096,"count":4}', '{"action":"finish"}'])
    result = _run(client)
    document = _document_from_steps(result)

    for step, call in zip(result.steps, client.calls, strict=True):
        replayed = reconstruct_context(document, step.index)
        assert replayed == call
        expected: tuple[Message, ...] = call
        assert replayed == expected


def test_step_at_returns_the_full_recorded_step() -> None:
    client = FakeLLM(['{"action":"disassemble","addr":4096,"count":4}', '{"action":"finish"}'])
    document = _document_from_steps(_run(client))

    step = step_at(document, 2)

    assert step["action"] == {"action": "finish"}


def test_replay_errors_on_missing_step_or_document() -> None:
    client = FakeLLM(['{"action":"finish"}'])
    document = _document_from_steps(_run(client))

    with pytest.raises(ReplayError, match="no step 99"):
        step_at(document, 99)
    with pytest.raises(ReplayError, match="no 'steps' list"):
        reconstruct_context({}, 1)
