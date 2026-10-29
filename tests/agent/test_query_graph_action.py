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


def test_query_graph_disabled_by_default_is_an_unknown_action() -> None:
    task = _task()
    tools = MediatorTools(task, root=ROOT)
    client = FakeLLM(['{"action":"query_graph","query":"observations","args":{}}'])

    with pytest.raises(AgentProtocolError, match="unknown action"):
        AgentLoop(task, tools, client).run()


def test_query_graph_enabled_runs_and_returns_results_to_the_model() -> None:
    task = _task()
    addr = task["function_addr"]
    assert isinstance(addr, int)
    tools = MediatorTools(task, root=ROOT)
    client = FakeLLM(
        [
            json.dumps({"action": "disassemble", "addr": addr, "count": 48}),
            json.dumps({"action": "query_graph", "query": "constants_in", "args": {}}),
            '{"action":"finish"}',
        ]
    )

    loop = AgentLoop(task, tools, client, enable_query_graph=True)
    registry = loop.run()

    assert registry.claims == ()
    query_message = json.loads(client.calls[2][-1]["content"])
    assert "query_result" in query_message
    constants = query_message["query_result"]["constants"]
    assert any(entry["value"] == 0xEDB88320 for entry in constants)


def test_query_graph_rejects_non_object_args() -> None:
    task = _task()
    tools = MediatorTools(task, root=ROOT)
    client = FakeLLM(['{"action":"query_graph","query":"observations","args":"nope"}'])

    with pytest.raises(AgentProtocolError, match="args must be an object"):
        AgentLoop(task, tools, client, enable_query_graph=True).run()


def test_query_graph_unknown_query_name_is_an_agent_protocol_error() -> None:
    task = _task()
    tools = MediatorTools(task, root=ROOT)
    client = FakeLLM(['{"action":"query_graph","query":"bogus","args":{}}'])

    with pytest.raises(AgentProtocolError, match="unknown query"):
        AgentLoop(task, tools, client, enable_query_graph=True).run()
