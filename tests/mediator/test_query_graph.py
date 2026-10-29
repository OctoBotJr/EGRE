import json
from pathlib import Path

import pytest

from egre.mediator.tools import MediatorTools, ToolValidationError

pytestmark = pytest.mark.toolchain

ROOT = Path(__file__).resolve().parents[2]


def _task(program: str) -> dict[str, object]:
    return json.loads((ROOT / "corpus" / "tasks" / f"{program}.json").read_text())


def test_constants_in_is_empty_until_the_agent_disassembles() -> None:
    task = _task("crc32_clean")
    tools = MediatorTools(task, root=ROOT)

    assert tools.query_graph("constants_in", {}) == {"constants": []}


def test_constants_in_reports_only_what_was_actually_disassembled() -> None:
    task = _task("crc32_clean")
    addr = task["function_addr"]
    assert isinstance(addr, int)
    tools = MediatorTools(task, root=ROOT)
    observation = tools.disassemble(addr, 48)

    result = tools.query_graph("constants_in", {})

    constants = result["constants"]
    assert any(entry["value"] == 0xEDB88320 for entry in constants)
    entry = next(entry for entry in constants if entry["value"] == 0xEDB88320)
    assert entry["observation_handles"] == [observation.handle]
    assert entry["executed"] is False


def test_constants_in_marks_a_block_executed_once_a_run_covers_it() -> None:
    task = _task("crc32_clean")
    addr = task["function_addr"]
    assert isinstance(addr, int)
    tools = MediatorTools(task, root=ROOT)
    tools.disassemble(addr, 48)
    tools.run("61")

    result = tools.query_graph("constants_in", {})

    entry = next(entry for entry in result["constants"] if entry["value"] == 0xEDB88320)
    assert entry["executed"] is True


def test_executed_blocks_is_empty_until_a_run_happens_then_lists_the_run_handle() -> None:
    task = _task("crc32_clean")
    addr = task["function_addr"]
    assert isinstance(addr, int)
    tools = MediatorTools(task, root=ROOT)

    assert tools.query_graph("executed_blocks", {}) == {"blocks": []}

    run = tools.run("61")
    result = tools.query_graph("executed_blocks", {})

    assert result["blocks"]
    assert all(run.handle in entry["run_handles"] for entry in result["blocks"])


def test_observations_lists_every_recorded_observation_and_can_filter_by_kind() -> None:
    task = _task("crc32_clean")
    addr = task["function_addr"]
    assert isinstance(addr, int)
    tools = MediatorTools(task, root=ROOT)
    disasm = tools.disassemble(addr, 48)
    run = tools.run("61")

    everything = tools.query_graph("observations", {})
    assert {entry["handle"] for entry in everything["observations"]} == {disasm.handle, run.handle}

    only_runs = tools.query_graph("observations", {"kind": "run"})
    assert [entry["handle"] for entry in only_runs["observations"]] == [run.handle]


def test_unknown_query_name_is_rejected() -> None:
    task = _task("crc32_clean")
    tools = MediatorTools(task, root=ROOT)

    with pytest.raises(ToolValidationError, match="unknown query"):
        tools.query_graph("something_else", {})


def test_unknown_observation_kind_filter_is_rejected() -> None:
    task = _task("crc32_clean")
    tools = MediatorTools(task, root=ROOT)

    with pytest.raises(ToolValidationError, match="unknown observation kind"):
        tools.query_graph("observations", {"kind": "trace"})


def test_i8_query_graph_never_adds_or_changes_what_a_claim_cites() -> None:
    """I8: the system never cites for the agent."""
    task = _task("crc32_clean")
    addr = task["function_addr"]
    assert isinstance(addr, int)
    tools = MediatorTools(task, root=ROOT)
    tools.disassemble(addr, 48)
    tools.run("61")

    before = tools.query_graph("constants_in", {})
    tools.query_graph("executed_blocks", {})
    tools.query_graph("observations", {})
    after = tools.query_graph("constants_in", {})

    # calling every query repeatedly changes nothing about the ledger or
    # what it would take to cite something -- query_graph is read-only
    assert before == after
    assert len(tools.observations.all()) == 2
