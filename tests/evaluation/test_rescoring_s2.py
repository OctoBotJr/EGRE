import json
from collections import Counter
from pathlib import Path

import pytest

from egre.evaluation.rescoring import rescore_document_with_s2, retrace_ledger
from egre.graph.cfg import build_function_cfg
from egre.ledger.store import Anchor, Ledger
from egre.runner.refs import REFERENCES
from egre.tracer.emulate import Tracer

pytestmark = pytest.mark.toolchain

ROOT = Path(__file__).resolve().parents[2]


def _task(program: str) -> dict[str, object]:
    return json.loads((ROOT / "corpus" / "tasks" / f"{program}.json").read_text())


def test_retrace_ledger_attaches_coverage_and_drops_it_on_mismatch() -> None:
    task = _task("crc32_clean")
    addr, size, binary = task["function_addr"], task["function_size"], task["binary"]
    assert isinstance(addr, int) and isinstance(size, int)
    cfg = build_function_cfg(ROOT / str(binary), addr, size)
    tracer = Tracer(ROOT / str(binary), addr, size)

    data = b"abc"
    ledger = Ledger()
    good = ledger.record(
        kind="run",
        tool="run",
        args={"input_hex": data.hex()},
        anchor=Anchor(addr, addr + size),
        payload=REFERENCES["crc32"](data),
    )
    bad = ledger.record(
        kind="run",
        tool="run",
        args={"input_hex": data.hex()},
        anchor=Anchor(addr, addr + size),
        payload=0xDEADBEEF,  # deliberately wrong, to force a mismatch
    )

    retraced = retrace_ledger(ledger.reader(), tracer, cfg)

    assert retraced.get(good.handle).coverage
    assert retraced.get(good.handle).tracer_mismatch is False
    assert retraced.get(bad.handle).coverage is None
    assert retraced.get(bad.handle).tracer_mismatch is True
    assert retraced.get(bad.handle).payload == 0xDEADBEEF  # mismatch never changes the output


def test_r0_re_scored_under_s2_closes_more_of_the_s0_blind_spot_than_s1(
) -> None:
    run_dir = ROOT / "runs" / "ollama-qwen3.5-4b-final"
    results = []
    for path in sorted(run_dir.glob("*.json")):
        document = json.loads(path.read_text())
        if document.get("state") != "completed":
            continue
        task = _task(document["program"])
        addr, size, binary = task["function_addr"], task["function_size"], task["binary"]
        assert isinstance(addr, int) and isinstance(size, int)
        results.extend(rescore_document_with_s2(document, ROOT / str(binary), addr, size))

    assert len(results) == 25
    tier_counts = Counter((claim.s2_tier, claim.is_true) for claim in results)
    assert tier_counts[("behavioral", True)] == 2
    assert tier_counts[("structural", True)] == 1
    assert tier_counts[("none", True)] == 20
    assert tier_counts[("none", False)] == 2

    s0_entailed_but_s2_weak = sum(
        claim.s0_entailed and claim.s2_tier in {"none", "contested", "contradicted"}
        for claim in results
    )
    s1_strong_but_s2_weak = sum(
        claim.s1_tier in {"structural", "behavioral"}
        and claim.s2_tier in {"none", "contested", "contradicted"}
        for claim in results
    )
    assert s0_entailed_but_s2_weak == 4
    # S2's execution qualification finds claims S1 could not: three citations
    # that were structurally unique (no rival constant) turn out to sit in a
    # block that this model's own runs never actually executed.
    assert s1_strong_but_s2_weak == 3
