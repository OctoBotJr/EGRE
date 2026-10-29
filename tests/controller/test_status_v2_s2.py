import json
from pathlib import Path

import pytest

from egre.claims.schema import Claim
from egre.controller.status_v2 import reason_codes
from egre.graph.cfg import build_function_cfg
from egre.graph.evidence import build_evidence_graph
from egre.mediator.tools import MediatorTools

pytestmark = pytest.mark.toolchain

ROOT = Path(__file__).resolve().parents[2]


def _task(program: str) -> dict[str, object]:
    return json.loads((ROOT / "corpus" / "tasks" / f"{program}.json").read_text())


def test_reason_codes_unexecuted_evidence_once_a_trace_exists_and_block_did_not_run() -> None:
    task = _task("fnv1a_crcdecoy")
    addr, size, binary = task["function_addr"], task["function_size"], task["binary"]
    assert isinstance(addr, int) and isinstance(size, int)
    cfg = build_function_cfg(ROOT / str(binary), addr, size)
    tools = MediatorTools(task, root=ROOT)
    disasm = tools.disassemble(addr, 256)
    tools.run("61")  # normal input: traces the live FNV path, never the dead CRC branch
    graph = build_evidence_graph(cfg, tools.observations)
    claim = Claim(
        id="c1",
        function_addr=addr,
        primitive="crc32",
        cited_handles=(disasm.handle,),
        confidence=0.5,
    )

    codes = reason_codes(claim, tools.observations, task, graph=graph)

    assert "UNEXECUTED_EVIDENCE" in codes


def test_reason_codes_unqualified_evidence_when_no_trace_exists_at_all() -> None:
    task = _task("crc32_clean")
    addr, size, binary = task["function_addr"], task["function_size"], task["binary"]
    assert isinstance(addr, int) and isinstance(size, int)
    cfg = build_function_cfg(ROOT / str(binary), addr, size)
    tools = MediatorTools(task, root=ROOT)
    disasm = tools.disassemble(addr, 48)  # no run() call at all: nothing ever traced
    graph = build_evidence_graph(cfg, tools.observations)
    claim = Claim(
        id="c1",
        function_addr=addr,
        primitive="crc32",
        cited_handles=(disasm.handle,),
        confidence=0.9,
    )

    codes = reason_codes(claim, tools.observations, task, graph=graph)

    assert "UNQUALIFIED_EVIDENCE" in codes


def test_reason_codes_no_execution_codes_once_the_block_is_qualified() -> None:
    task = _task("crc32_clean")
    addr, size, binary = task["function_addr"], task["function_size"], task["binary"]
    assert isinstance(addr, int) and isinstance(size, int)
    cfg = build_function_cfg(ROOT / str(binary), addr, size)
    tools = MediatorTools(task, root=ROOT)
    disasm = tools.disassemble(addr, 48)
    tools.run("61")
    graph = build_evidence_graph(cfg, tools.observations)
    claim = Claim(
        id="c1",
        function_addr=addr,
        primitive="crc32",
        cited_handles=(disasm.handle,),
        confidence=0.9,
    )

    codes = reason_codes(claim, tools.observations, task, graph=graph)

    assert "UNEXECUTED_EVIDENCE" not in codes
    assert "UNQUALIFIED_EVIDENCE" not in codes


def test_reason_codes_without_graph_omits_execution_codes() -> None:
    task = _task("crc32_clean")
    addr, size, _binary = task["function_addr"], task["function_size"], task["binary"]
    assert isinstance(addr, int) and isinstance(size, int)
    tools = MediatorTools(task, root=ROOT)
    disasm = tools.disassemble(addr, 48)
    claim = Claim(
        id="c1",
        function_addr=addr,
        primitive="crc32",
        cited_handles=(disasm.handle,),
        confidence=0.9,
    )

    codes = reason_codes(claim, tools.observations, task)

    assert "UNEXECUTED_EVIDENCE" not in codes
    assert "UNQUALIFIED_EVIDENCE" not in codes
