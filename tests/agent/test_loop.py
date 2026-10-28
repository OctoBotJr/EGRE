import json
from pathlib import Path

import pytest

from egre.agent.loop import AgentLoop, AgentProtocolError, StepLimitError
from egre.llm.fake import FakeLLM
from egre.mediator.tools import MediatorTools

ROOT = Path(__file__).parents[2]


def _task(name: str = "crc32_clean") -> dict[str, object]:
    return json.loads((ROOT / "corpus" / "tasks" / f"{name}.json").read_text())


@pytest.mark.toolchain
def test_json_loop_dispatches_tools_and_registers_claims() -> None:
    task = _task()
    addr = task["function_addr"]
    assert isinstance(addr, int)
    client = FakeLLM(
        [
            json.dumps({"action": "disassemble", "addr": addr, "count": 48}),
            json.dumps(
                {
                    "action": "claim",
                    "claim": {
                        "id": "c1",
                        "function_addr": addr,
                        "primitive": "crc32",
                        "cited_handles": ["obs-000001"],
                        "confidence": 0.9,
                    },
                }
            ),
            '{"action":"finish"}',
        ]
    )
    tools = MediatorTools(task, root=ROOT)

    registry = AgentLoop(task, tools, client).run()

    assert [claim.id for claim in registry] == ["c1"]
    assert registry.claims[0].cited_handles == ("obs-000001",)
    assert len(tools.observations) == 1
    assert len(client.calls) == 3


@pytest.mark.toolchain
def test_json_loop_rejects_claim_with_unissued_handle() -> None:
    task = _task()
    addr = task["function_addr"]
    assert isinstance(addr, int)
    claim = {
        "action": "claim",
        "claim": {
            "id": "invented-evidence",
            "function_addr": addr,
            "primitive": "crc32",
            "cited_handles": ["obs-invented"],
            "confidence": 1.0,
        },
    }

    with pytest.raises(AgentProtocolError, match="unknown observation handle"):
        AgentLoop(
            task,
            MediatorTools(task, root=ROOT),
            FakeLLM([json.dumps(claim)]),
        ).run()


@pytest.mark.parametrize("response", ["not json", "[]", '{"action":"shell"}'])
@pytest.mark.toolchain
def test_json_loop_rejects_malformed_or_unallowlisted_actions(response: str) -> None:
    task = _task()
    loop = AgentLoop(task, MediatorTools(task, root=ROOT), FakeLLM([response]))

    with pytest.raises(AgentProtocolError):
        loop.run()


@pytest.mark.toolchain
def test_json_loop_enforces_twelve_step_limit() -> None:
    task = _task()
    addr = task["function_addr"]
    assert isinstance(addr, int)
    responses = [
        json.dumps({"action": "disassemble", "addr": addr, "count": 1})
        for _ in range(12)
    ]

    with pytest.raises(StepLimitError, match="12"):
        AgentLoop(task, MediatorTools(task, root=ROOT), FakeLLM(responses)).run()
