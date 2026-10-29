"""Run the bounded agent against the explicitly local OpenAI-compatible Ollama endpoint."""

from __future__ import annotations

import argparse
import json
import os
import re
import time
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from functools import partial
from pathlib import Path

from egre.agent.loop import AgentLoop, StepRecord, hypotheses_schema
from egre.evaluation.metrics import evaluate_run
from egre.ledger.store import LedgerReader
from egre.llm.base import LLMClient, TokenUsage
from egre.llm.openai import OpenAIAdapter
from egre.mediator.tools import MediatorTools

ROOT = Path(__file__).resolve().parents[3]
LOCAL_OLLAMA_BASE_URL = "http://localhost:11434/v1"
AdapterFactory = Callable[..., LLMClient]


def sanitize_model(model: str) -> str:
    """Make the model name safe for a run-directory component."""
    sanitized = re.sub(r"[:/]", "-", model.strip())
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "-", sanitized).strip("-")
    if not sanitized:
        raise ValueError("model name has no filename-safe characters")
    return sanitized


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be positive")
    return parsed


def _positive_float(value: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be positive")
    return parsed


def _load_object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise TypeError(f"expected a JSON object: {path}")
    return value


def _usage_document(usage: TokenUsage) -> dict[str, int | None]:
    return {
        "prompt_tokens": usage.prompt_tokens,
        "completion_tokens": usage.completion_tokens,
        "total_tokens": usage.total_tokens,
    }


def _step_document(step: StepRecord) -> dict[str, object]:
    return {
        "index": step.index,
        "messages_sent": [dict(message) for message in step.messages_sent],
        "raw_response": step.raw_response,
        "content": step.content,
        "reasoning": step.reasoning,
        "action": step.action,
        "error": step.error,
        "tool_call": step.tool_call,
        "tool_result": step.tool_result,
        "usage": _usage_document(step.usage),
    }


def _ledger_document(reader: LedgerReader) -> list[dict[str, object]]:
    return [
        {
            "handle": observation.handle,
            "kind": observation.kind,
            "tool": observation.tool,
            "args": dict(observation.args),
            "anchor": {
                "start": observation.anchor.start,
                "end": observation.anchor.end,
            },
            "payload": observation.payload,
            "facts": sorted(observation.facts),
            "ts": observation.ts,
        }
        for observation in reader.all()
    ]


def _write_json(path: Path, document: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def _partial_document(
    *,
    program: str,
    repeat: int,
    model: str,
    settings: Mapping[str, object],
    started_at: str,
    steps: Sequence[StepRecord],
    ledger: LedgerReader,
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "state": "running",
        "program": program,
        "repeat": repeat,
        "model": model,
        "settings": dict(settings),
        "started_at": started_at,
        "steps": [_step_document(step) for step in steps],
        "tool_calls": [
            {
                "step": step.index,
                "call": step.tool_call,
                "result": step.tool_result,
            }
            for step in steps
            if step.tool_call is not None
        ],
        "ledger": _ledger_document(ledger),
        "claims": [],
        "invalid_steps": sum(step.error is not None for step in steps),
    }


def _persist_step(
    step: StepRecord,
    *,
    seen_steps: list[StepRecord],
    path: Path,
    program: str,
    repeat: int,
    model: str,
    settings: Mapping[str, object],
    started_at: str,
    ledger: LedgerReader,
) -> None:
    seen_steps.append(step)
    _write_json(
        path,
        _partial_document(
            program=program,
            repeat=repeat,
            model=model,
            settings=settings,
            started_at=started_at,
            steps=seen_steps,
            ledger=ledger,
        ),
    )


def _resolve_programs(root: Path, requested: str | None) -> tuple[str, ...]:
    available = tuple(path.stem for path in sorted((root / "corpus" / "tasks").glob("*.json")))
    if requested is None:
        return available
    programs = tuple(part.strip() for part in requested.split(",") if part.strip())
    if not programs:
        raise ValueError("--programs must contain at least one program")
    unknown = sorted(set(programs) - set(available))
    if unknown:
        raise ValueError(f"unknown programs: {', '.join(unknown)}")
    return programs


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--llm", choices=("openai",), default="openai")
    parser.add_argument("--model", default="qwen3.5:4b")
    parser.add_argument("--repeats", type=_positive_int, default=3)
    parser.add_argument("--programs", help="comma-separated corpus program names")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--base-url")
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument("--max-tokens", type=_positive_int, default=700)
    parser.add_argument("--timeout", type=_positive_float, default=120.0)
    parser.add_argument(
        "--hypotheses",
        action="store_true",
        help="require a hypotheses confidence map on every action (R1, schema-constrained output)",
    )
    parser.add_argument(
        "--query-graph",
        action="store_true",
        help="enable the read-only query_graph tool (R2, needs --hypotheses for R2's full condition)",
    )
    parser.add_argument(
        "--revision",
        action="store_true",
        help=(
            "enable revise_claim/retract_claim and reason-code feedback after each claim "
            "(R3, needs --query-graph for R3's full condition)"
        ),
    )
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    root: Path = ROOT,
    adapter_factory: AdapterFactory = OpenAIAdapter,
) -> int:
    args = _parser().parse_args(argv)
    base_url_value = args.base_url or os.environ.get("OPENAI_BASE_URL")
    if not isinstance(base_url_value, str) or base_url_value.rstrip("/") != LOCAL_OLLAMA_BASE_URL:
        raise ValueError(
            f"P-08 permits only the local Ollama endpoint {LOCAL_OLLAMA_BASE_URL}; "
            "set OPENAI_BASE_URL or --base-url"
        )
    base_url = LOCAL_OLLAMA_BASE_URL
    model = str(args.model)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out = args.out or root / "runs" / f"{timestamp}-{sanitize_model(model)}"
    if not out.is_absolute():
        out = root / out
    out.mkdir(parents=True, exist_ok=True)
    programs = _resolve_programs(root, args.programs)
    settings: dict[str, object] = {
        "base_url": base_url,
        "temperature": args.temperature,
        "max_tokens": args.max_tokens,
        "timeout": args.timeout,
        "hypotheses": args.hypotheses,
        "query_graph": args.query_graph,
        "revision": args.revision,
    }

    completed = 0
    skipped = 0
    for program in programs:
        task = _load_object(root / "corpus" / "tasks" / f"{program}.json")
        binary = task.get("binary")
        if not isinstance(binary, str):
            raise TypeError(f"task binary must be a string: {program}")
        truth_data = _load_object(root / "corpus" / "truth" / f"{program}.json")
        truth = truth_data.get("primitive")
        if not isinstance(truth, str):
            raise TypeError(f"truth primitive must be a string: {program}")

        for repeat in range(1, args.repeats + 1):
            target = out / f"{program}-repeat-{repeat:03d}.json"
            partial_path = target.with_suffix(target.suffix + ".partial")
            if target.exists():
                print(f"skip {program} repeat {repeat}: {target.name} exists")
                skipped += 1
                continue

            tools = MediatorTools(task, root=root)
            adapter_kwargs: dict[str, object] = {
                "model": model,
                "base_url": base_url,
                "temperature": args.temperature,
                "max_tokens": args.max_tokens,
                "timeout": args.timeout,
            }
            if args.hypotheses:
                adapter_kwargs["response_format"] = hypotheses_schema()
            client = adapter_factory(**adapter_kwargs)
            loop = AgentLoop(
                task,
                tools,
                client,
                require_hypotheses=args.hypotheses,
                enable_query_graph=args.query_graph,
                enable_revision=args.revision,
            )
            started_at = datetime.now(UTC).isoformat()
            started = time.monotonic()
            seen_steps: list[StepRecord] = []

            persist_step = partial(
                _persist_step,
                seen_steps=seen_steps,
                path=partial_path,
                program=program,
                repeat=repeat,
                model=model,
                settings=settings,
                started_at=started_at,
                ledger=tools.observations,
            )
            result = loop.run_detailed(on_step=persist_step)
            outcome = evaluate_run(
                policy="LLM",
                program=program,
                truth=truth,
                task=task,
                registry=result.registry,
                ledger=tools.observations,
                binary=root / binary,
            )
            steps = [_step_document(step) for step in result.steps]
            document: dict[str, object] = {
                "schema_version": 1,
                "state": "completed",
                "program": program,
                "repeat": repeat,
                "model": model,
                "settings": settings,
                "started_at": started_at,
                "wall_time_seconds": time.monotonic() - started,
                "stop_reason": result.stop_reason,
                "steps": steps,
                "tool_calls": [
                    {
                        "step": step.index,
                        "call": step.tool_call,
                        "result": step.tool_result,
                    }
                    for step in result.steps
                    if step.tool_call is not None
                ],
                "ledger": _ledger_document(tools.observations),
                "claims": [claim.model_dump(mode="json") for claim in result.registry],
                "invalid_steps": result.invalid_steps,
                "usage": _usage_document(result.usage),
                "outcome": outcome.to_document(),
            }
            _write_json(target, document)
            partial_path.unlink(missing_ok=True)
            print(
                f"wrote {target}: claims={len(result.registry)} "
                f"invalid_steps={result.invalid_steps} stop={result.stop_reason}"
            )
            completed += 1

    print(f"run directory: {out}")
    print(f"completed: {completed}; skipped: {skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
