"""Render a saved prototype evaluation document."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from pathlib import Path


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


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="saved evaluation JSON")
    args = parser.parse_args(argv)
    document = json.loads(args.path.read_text())
    if not isinstance(document, dict):
        raise TypeError("evaluation document must be an object")
    print(render_document(document), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
