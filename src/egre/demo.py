"""Run the complete offline scripted prototype demonstration."""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from pathlib import Path

from egre.agent.loop import AgentLoop
from egre.agent.policies import EmulatorPolicy, GrepperPolicy, PriorGuesserPolicy
from egre.evaluation.cli import render_document
from egre.evaluation.metrics import RunOutcome, evaluate_run, summarize
from egre.llm.base import LLMClient
from egre.mediator.tools import MediatorTools

ROOT = Path(__file__).resolve().parents[2]
POLICIES: tuple[tuple[str, Callable[[], LLMClient]], ...] = (
    ("P1", GrepperPolicy),
    ("P2", EmulatorPolicy),
    ("P3", PriorGuesserPolicy),
)


def _load_object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise TypeError(f"expected a JSON object: {path}")
    return value


def build_demo(root: Path = ROOT) -> tuple[RunOutcome, ...]:
    """Run all three scripted policies over every generated corpus task."""
    outcomes: list[RunOutcome] = []
    task_paths = sorted((root / "corpus" / "tasks").glob("*.json"))
    for policy_name, policy_factory in POLICIES:
        for task_path in task_paths:
            task = _load_object(task_path)
            program = task.get("program")
            binary = task.get("binary")
            if not isinstance(program, str) or not isinstance(binary, str):
                raise TypeError(f"task lacks program/binary strings: {task_path}")
            truth_data = _load_object(root / "corpus" / "truth" / f"{program}.json")
            truth = truth_data.get("primitive")
            if not isinstance(truth, str):
                raise TypeError(f"truth lacks primitive string: {program}")

            tools = MediatorTools(task, root=root)
            registry = AgentLoop(task, tools, policy_factory()).run()
            outcomes.append(
                evaluate_run(
                    policy=policy_name,
                    program=program,
                    truth=truth,
                    task=task,
                    registry=registry,
                    ledger=tools.observations,
                    binary=root / binary,
                )
            )
    return tuple(outcomes)


def _render_runs(runs: Sequence[RunOutcome]) -> str:
    lines = ["Per-policy matrix", "policy  program             claims"]
    for run in runs:
        claims = ", ".join(
            f"{claim.primitive}:{claim.support}/{claim.verdict}/{claim.status}"
            + ("+support_gap" if claim.support_gap else "")
            for claim in run.claims
        )
        lines.append(f"{run.policy:<6}  {run.program:<18}  {claims or '-'}")
    return "\n".join(lines) + "\n"


def main() -> int:
    runs = build_demo(ROOT)
    summary = summarize(runs)
    document = summary.to_document(runs)
    output = ROOT / "runs" / "demo.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    print(_render_runs(runs))
    print(render_document(document), end="")
    print(f"\nWrote {output.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
