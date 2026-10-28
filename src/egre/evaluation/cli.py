"""Render a saved prototype evaluation document."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from egre.evaluation.metrics import (
    RunOutcome,
    deduplicate_runs,
    has_duplicate_primitives,
    summarize,
)


@dataclass(frozen=True, slots=True)
class _CompletedRun:
    outcome: RunOutcome
    invalid_steps: int


def _percent(value: object) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("metric must be numeric or null")
    return f"{value:.1%}"


def render_document(document: Mapping[str, object]) -> str:
    """Render the support matrix and gate views from JSON-compatible data."""
    matrix = document.get("support_truth")
    views = document.get("views")
    if not isinstance(matrix, dict) or not isinstance(views, list):
        raise TypeError("evaluation document requires support_truth and views")

    lines = [
        "Support x truth",
        "support       true  false",
        f"entailed      {matrix.get('entailed_true', 0):>4}  {matrix.get('entailed_false', 0):>5}",
        f"insufficient  {matrix.get('insufficient_true', 0):>4}  {matrix.get('insufficient_false', 0):>5}",
        "",
        "Gate views",
        "view  claims  true  false  precision  coverage",
    ]
    for raw_view in views:
        if not isinstance(raw_view, dict):
            raise TypeError("each view must be an object")
        lines.append(
            f"{raw_view.get('name', ''):<4}  {raw_view.get('retained_claims', 0):>6}  "
            f"{raw_view.get('true_claims', 0):>4}  {raw_view.get('false_claims', 0):>5}  "
            f"{_percent(raw_view.get('precision')):>9}  {_percent(raw_view.get('coverage')):>8}"
        )
    return "\n".join(lines) + "\n"


def _read_object(path: Path) -> dict[str, object]:
    document = json.loads(path.read_text())
    if not isinstance(document, dict):
        raise TypeError(f"JSON document must be an object: {path}")
    return document


def _render_view_rows(document: Mapping[str, object]) -> str:
    views = document.get("views")
    if not isinstance(views, list):
        raise TypeError("evaluation document requires views")
    lines = ["view  claims  true  false  precision  coverage"]
    for raw_view in views:
        if not isinstance(raw_view, dict):
            raise TypeError("each view must be an object")
        lines.append(
            f"{raw_view.get('name', ''):<4}  {raw_view.get('retained_claims', 0):>6}  "
            f"{raw_view.get('true_claims', 0):>4}  {raw_view.get('false_claims', 0):>5}  "
            f"{_percent(raw_view.get('precision')):>9}  {_percent(raw_view.get('coverage')):>8}"
        )
    return "\n".join(lines)


def _render_reason_counts(runs: Sequence[_CompletedRun]) -> str:
    reasons = Counter(
        claim.reason or "NONE"
        for run in runs
        for claim in run.outcome.claims
        if claim.support == "insufficient"
    )
    lines = ["Insufficient-support reasons", "reason                 count"]
    if not reasons:
        lines.append("(none)                     0")
    else:
        lines.extend(f"{reason:<27}{count}" for reason, count in sorted(reasons.items()))
    return "\n".join(lines)


def _render_program_breakdown(runs: Sequence[_CompletedRun]) -> str:
    programs = sorted({run.outcome.program for run in runs})
    variant_width = max(10, *(len(program) for program in programs))
    lines = [
        "Per-program breakdown",
        (
            f"{'variant':<{variant_width}}  runs  claims  true  false  entailed  "
            "insufficient  zero-claim-runs  invalid-steps"
        ),
    ]
    for program in programs:
        selected = [run for run in runs if run.outcome.program == program]
        claims = [claim for run in selected for claim in run.outcome.claims]
        lines.append(
            f"{program:<{variant_width}}  {len(selected):>1}  {len(claims):>6}  "
            f"{sum(claim.is_true for claim in claims):>4}  "
            f"{sum(not claim.is_true for claim in claims):>5}  "
            f"{sum(claim.support == 'entailed' for claim in claims):>8}  "
            f"{sum(claim.support == 'insufficient' for claim in claims):>12}  "
            f"{sum(not run.outcome.claims for run in selected):>10}  "
            f"{sum(run.invalid_steps for run in selected):>7}"
        )
    return "\n".join(lines)


def _render_run_directory(path: Path) -> str:
    run_documents = [_read_object(run_path) for run_path in sorted(path.glob("*.json"))]
    completed_runs: list[_CompletedRun] = []
    for document in run_documents:
        if document.get("state") != "completed":
            continue
        raw_outcome = document.get("outcome")
        if not isinstance(raw_outcome, dict):
            raise TypeError("completed run document requires an outcome object")
        outcome = RunOutcome.from_document(raw_outcome)
        raw_invalid = document.get("invalid_steps", 0)
        if isinstance(raw_invalid, bool) or not isinstance(raw_invalid, int) or raw_invalid < 0:
            raise TypeError("invalid_steps must be a non-negative integer")
        completed_runs.append(_CompletedRun(outcome=outcome, invalid_steps=raw_invalid))

    outcomes = [run.outcome for run in completed_runs]
    summary = summarize(outcomes)
    deduplicated_runs = deduplicate_runs(outcomes)
    deduplicated = summarize(deduplicated_runs)
    totals = (
        f"Total claims: {sum(len(outcome.claims) for outcome in outcomes)}\n"
        f"Zero-claim runs: {sum(not outcome.claims for outcome in outcomes)}\n"
        f"Total invalid steps: {sum(run.invalid_steps for run in completed_runs)}\n"
    )
    duplicate_runs = sum(has_duplicate_primitives(outcome) for outcome in outcomes)
    analysis = (
        _render_reason_counts(completed_runs)
        + "\n\n"
        + _render_program_breakdown(completed_runs)
        + "\n\n"
        + f"Runs with duplicate (run, primitive) claims: {duplicate_runs}\n\n"
        + "Deduplicated gate views (first claim per run and primitive)\n"
        + _render_view_rows(deduplicated.to_document(deduplicated_runs))
        + "\n"
    )
    return render_document(summary.to_document(outcomes)) + "\n" + totals + "\n" + analysis


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="saved evaluation JSON or run directory")
    args = parser.parse_args(argv)
    if args.path.is_dir():
        print(_render_run_directory(args.path), end="")
    else:
        print(render_document(_read_object(args.path)), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
