"""Run P1-P4 over every corpus/catalog.json entry (V2_SPEC.md section 6, V-18)."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from egre.agent.loop import AgentLoop
from egre.agent.policies import (
    EmulatorPolicy,
    GrepperPolicy,
    PriorGuesserPolicy,
    TraceQualifiedGrepperPolicy,
)
from egre.evaluation.metrics_v2 import RunOutcomeV2, VerdictCache, evaluate_run_v2
from egre.graph.cfg import build_function_cfg
from egre.llm.base import LLMClient
from egre.mediator.tools import MediatorTools

ROOT = Path(__file__).resolve().parents[3]

PolicyFactory = Callable[[], tuple[LLMClient, dict[str, object]]]
POLICIES: tuple[tuple[str, PolicyFactory], ...] = (
    ("P1", lambda: (GrepperPolicy(), {})),
    ("P2", lambda: (EmulatorPolicy(), {})),
    ("P3", lambda: (PriorGuesserPolicy(), {})),
    ("P4", lambda: (TraceQualifiedGrepperPolicy(), {"enable_query_graph": True})),
)


def _load_object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise TypeError(f"expected a JSON object: {path}")
    return value


def build_demo_v2(root: Path = ROOT) -> tuple[RunOutcomeV2, ...]:
    """Run every scripted policy (P1-P4) against every catalog program, scored under S1/S2."""
    catalog = json.loads((root / "corpus" / "catalog.json").read_text())
    verdict_cache: VerdictCache = {}
    outcomes: list[RunOutcomeV2] = []
    for policy_name, make_policy in POLICIES:
        for entry in catalog:
            program = entry["name"]
            variant = entry["variant"]
            task = _load_object(root / "corpus" / "tasks" / f"{program}.json")
            binary = task.get("binary")
            addr = task.get("function_addr")
            size = task.get("function_size")
            if not isinstance(binary, str) or not isinstance(addr, int) or not isinstance(size, int):
                raise TypeError(f"task lacks a valid binary/function_addr/function_size: {program}")
            truth_data = _load_object(root / "corpus" / "truth" / f"{program}.json")
            truth = truth_data.get("primitive")
            if not isinstance(truth, str):
                raise TypeError(f"truth lacks a primitive string: {program}")

            tools = MediatorTools(task, root=root)
            policy, loop_kwargs = make_policy()
            registry = AgentLoop(task, tools, policy, **loop_kwargs).run()  # type: ignore[arg-type]
            cfg = build_function_cfg(root / binary, addr, size)
            outcomes.append(
                evaluate_run_v2(
                    policy=policy_name,
                    program=program,
                    variant=variant,
                    truth=truth,
                    task=task,
                    registry=registry,
                    ledger=tools.observations,
                    cfg=cfg,
                    binary=root / binary,
                    verdict_cache=verdict_cache,
                )
            )
    return tuple(outcomes)
