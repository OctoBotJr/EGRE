import json
from pathlib import Path

import pytest

from egre.agent.loop import AgentLoop, AgentProtocolError
from egre.llm.fake import FakeLLM
from egre.mediator.tools import MediatorTools

pytestmark = pytest.mark.toolchain

ROOT = Path(__file__).resolve().parents[2]


def _task(program: str = "crc32_clean") -> dict[str, object]:
    return json.loads((ROOT / "corpus" / "tasks" / f"{program}.json").read_text())


def test_lookup_knowledge_disabled_by_default_is_an_unknown_action() -> None:
    task = _task()
    tools = MediatorTools(task, root=ROOT)
    client = FakeLLM(['{"action":"lookup_knowledge","query":"crc"}'])

    with pytest.raises(AgentProtocolError, match="unknown action"):
        AgentLoop(task, tools, client).run()


def test_lookup_knowledge_enabled_returns_results_to_the_model() -> None:
    task = _task()
    tools = MediatorTools(task, root=ROOT)
    client = FakeLLM(
        [
            '{"action":"lookup_knowledge","query":"0xEDB88320"}',
            '{"action":"finish"}',
        ]
    )

    loop = AgentLoop(task, tools, client, enable_knowledge=True)
    registry = loop.run()

    assert registry.claims == ()
    knowledge_message = json.loads(client.calls[1][-1]["content"])
    ids = {match["id"] for match in knowledge_message["knowledge_result"]["matches"]}
    assert ids == {"crc32", "jamcrc"}


def test_citing_a_knowledge_handle_in_a_claim_fails_closed() -> None:
    """I7 at the protocol boundary: a K-<id> handle is not a valid citation."""
    task = _task()
    addr = task["function_addr"]
    assert isinstance(addr, int)
    tools = MediatorTools(task, root=ROOT)
    client = FakeLLM(
        [
            '{"action":"lookup_knowledge","query":"0xEDB88320"}',
            json.dumps(
                {
                    "action": "claim",
                    "claim": {
                        "id": "c1",
                        "function_addr": addr,
                        "primitive": "crc32",
                        "cited_handles": ["K-crc32"],
                        "confidence": 0.9,
                    },
                }
            ),
        ]
    )

    with pytest.raises(AgentProtocolError, match="K-crc32"):
        AgentLoop(task, tools, client, enable_knowledge=True).run()
