import json
from pathlib import Path

import pytest

from egre.ledger.store import UnknownHandleError
from egre.mediator.tools import MediatorTools, ToolValidationError
from egre.runner.refs import REFERENCES

pytestmark = pytest.mark.toolchain

ROOT = Path(__file__).resolve().parents[2]


def _task(program: str) -> dict[str, object]:
    return json.loads((ROOT / "corpus" / "tasks" / f"{program}.json").read_text())


@pytest.mark.parametrize(
    ("program", "present", "absent"),
    [
        ("crc32_clean", {0xEDB88320}, set()),
        ("crc32_obfpoly", set(), {0xEDB88320}),
        ("fnv1a_crcdecoy", {0xEDB88320}, set()),
        ("djb2_fnvdecoy", {5381, 0x811C9DC5, 0x01000193}, set()),
    ],
)
def test_disassembly_records_required_signature_facts(
    program: str, present: set[int], absent: set[int]
) -> None:
    task = _task(program)
    tools = MediatorTools(task, root=ROOT)
    addr = task["function_addr"]
    assert isinstance(addr, int)

    result = tools.disassemble(addr, 256)
    observation = tools.observations.get(result.handle)

    assert present <= result.facts
    assert result.facts.isdisjoint(absent)
    assert observation.facts == result.facts
    assert observation.kind == "disasm"
    assert observation.anchor.start == addr
    assert observation.anchor.end <= addr + task["function_size"]  # type: ignore[operator]
    assert result.content.startswith(f"{addr:#x}:")


def test_read_memory_and_run_are_validated_and_recorded() -> None:
    task = _task("djb2_clean")
    tools = MediatorTools(task, root=ROOT)
    addr = task["function_addr"]
    assert isinstance(addr, int)

    memory = tools.read_memory(addr, 8)
    run = tools.run("00")

    memory_observation = tools.observations.get(memory.handle)
    run_observation = tools.observations.get(run.handle)
    assert len(memory.content) == 16
    assert memory_observation.kind == "memory"
    assert memory_observation.anchor == memory.anchor
    assert run.content == REFERENCES["djb2"](b"\x00")
    assert run_observation.kind == "run"
    assert run_observation.args["input_hex"] == "00"
    assert run_observation.payload == run.content
    assert run_observation.anchor.start == addr


def test_agent_facing_surface_cannot_write_or_resolve_unknown_handles() -> None:
    tools = MediatorTools(_task("crc32_clean"), root=ROOT)

    assert not hasattr(tools, "ledger")
    assert not hasattr(tools.observations, "record")
    with pytest.raises(UnknownHandleError, match="unknown observation handle"):
        tools.observations.get("invented")


def test_tool_arguments_are_bounded_to_the_target_function() -> None:
    task = _task("crc32_clean")
    tools = MediatorTools(task, root=ROOT)
    addr = task["function_addr"]
    size = task["function_size"]
    assert isinstance(addr, int)
    assert isinstance(size, int)

    with pytest.raises(ToolValidationError):
        tools.disassemble(addr - 4, 1)
    with pytest.raises(ToolValidationError):
        tools.disassemble(addr, 0)
    with pytest.raises(ToolValidationError):
        tools.read_memory(addr + size - 1, 2)
    with pytest.raises(ToolValidationError):
        tools.run("not-hex")

