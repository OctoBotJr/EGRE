"""Architectural invariant I5/I2: runtime code never touches corpus/evaluation; verdict code never touches LLMs."""
import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src" / "egre"
RUNTIME = ["agent", "mediator", "ledger", "claims", "contracts", "runner", "controller", "report"]
NO_LLM = ["contracts", "runner", "controller"]
OFFLINE = ("egre.corpus", "egre.evaluation")
LLM = ("egre.llm", "openai", "anthropic")


def imported(path: Path):
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                yield a.name
        elif isinstance(node, ast.ImportFrom):
            if node.level >= 2:  # e.g. `from ..corpus import x` inside egre/<component>/
                base = "egre" + (f".{node.module}" if node.module else "")
                yield base
                if node.module is None:
                    for a in node.names:
                        yield f"egre.{a.name}"
            elif node.module:
                yield node.module


def violations(path: Path, forbidden):
    return [m for m in imported(path) if any(m == f or m.startswith(f + ".") for f in forbidden)]


def py_files(pkg: str):
    return sorted((SRC / pkg).rglob("*.py"))


@pytest.mark.parametrize("pkg", RUNTIME)
def test_runtime_does_not_import_offline_code(pkg):
    bad = {str(p): violations(p, OFFLINE) for p in py_files(pkg) if violations(p, OFFLINE)}
    assert not bad, bad


@pytest.mark.parametrize("pkg", NO_LLM)
def test_verdict_code_does_not_import_llm(pkg):
    bad = {str(p): violations(p, LLM) for p in py_files(pkg) if violations(p, LLM)}
    assert not bad, bad


def test_detector_catches_violations(tmp_path):
    f = tmp_path / "x.py"
    f.write_text("from egre.corpus import gen\nfrom ..evaluation import m\nimport openai\n")
    assert violations(f, OFFLINE) == ["egre.corpus", "egre.evaluation"]
    assert violations(f, LLM) == ["openai"]
