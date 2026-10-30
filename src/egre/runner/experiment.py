"""Experiment designer: inputs that discriminate the live hypothesis set.

V2_SPEC.md section 4.1/4.3, V-17. Designed inputs are generated here, never
copied from the knowledge base's own ``public_vectors`` (V2_SPEC.md section
5.2) -- those exist for cheap agent-visible sanity checks; a verdict needs
inputs that were never published anywhere a program could have been built
to fake against. This module feeds :func:`egre.runner.verify.verify_with_inputs`
together with the held-out vectors (never exposed through any agent-facing
tool, I10) to produce the final verdict.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path

from egre.runner.refs import Reference
from egre.runner.verify import VectorEvidence, Verdict, verify_with_inputs

# A fixed, deterministic pool -- not random, not the KB's public vectors, and
# disjoint from corpus/reference_vectors.json's own inputs_hex by construction
# (different lengths/content patterns), so a program tuned to those couldn't
# coast on designed inputs looking the same as public ones.
_POOL_LENGTHS = (0, 1, 2, 3, 4, 5, 6, 8, 12, 16, 24, 32)


def _generate_pool() -> tuple[bytes, ...]:
    """Every candidate input the designer is allowed to pick from."""
    candidates: list[bytes] = []
    for length in _POOL_LENGTHS:
        candidates.append(bytes((index * 37 + 11) % 256 for index in range(length)))
        candidates.append(bytes((index * 191 + 7) % 256 for index in range(length)))
        candidates.append(bytes(length))
        candidates.append(bytes([0xFF] * length))
    seen: set[bytes] = set()
    pool: list[bytes] = []
    for item in candidates:
        if item not in seen:
            seen.add(item)
            pool.append(item)
    return tuple(pool)


@dataclass(frozen=True, slots=True)
class ExperimentDesign:
    """The chosen discriminating inputs, and any live pair they couldn't separate."""

    inputs: tuple[str, ...]
    indistinguishable_pairs: tuple[tuple[str, str], ...]


def design_inputs(
    candidates: Sequence[str],
    references: Mapping[str, Reference],
    *,
    pool: Sequence[bytes] | None = None,
) -> ExperimentDesign:
    """Greedily choose inputs maximizing distinct predicted outputs across ``candidates``.

    Repeats until every pair of candidates with a reference implementation
    is separated by at least one chosen input, or the pool is exhausted --
    any pair still unseparated at that point is reported, not hidden.
    """
    live = sorted(name for name in candidates if name in references)
    pool_bytes = tuple(pool) if pool is not None else _generate_pool()

    outputs_by_input = {
        candidate_input: {name: references[name](candidate_input) for name in live}
        for candidate_input in pool_bytes
    }

    remaining = set(combinations(live, 2))
    selected: list[bytes] = []
    while remaining:
        best_input: bytes | None = None
        best_covered: set[tuple[str, str]] = set()
        for candidate_input, outputs in outputs_by_input.items():
            if candidate_input in selected:
                continue
            covered = {pair for pair in remaining if outputs[pair[0]] != outputs[pair[1]]}
            if len(covered) > len(best_covered):
                best_covered = covered
                best_input = candidate_input
        if best_input is None or not best_covered:
            break
        selected.append(best_input)
        remaining -= best_covered

    return ExperimentDesign(
        inputs=tuple(data.hex() for data in selected),
        indistinguishable_pairs=tuple(sorted(remaining)),
    )


def load_held_out_inputs(root: str | os.PathLike[str] = ".") -> tuple[str, ...]:
    """The held-out input set (V2_SPEC.md section 4.1, invariant I10).

    This is the ONE place in the runtime allowed to read
    corpus/held_out_vectors.json -- the experiment runner, offline, after
    the agent has already finished. Never call this from mediator/agent
    code: nothing it returns may reach a tool result or a prompt.
    """
    path = Path(root) / "corpus" / "held_out_vectors.json"
    if not path.exists():
        return ()
    data = json.loads(path.read_text())
    return tuple(data["inputs_hex"])


def verdict_for(
    binary: str | os.PathLike[str],
    primitive: str,
    candidates: Sequence[str],
    references: Mapping[str, Reference],
    *,
    root: str | os.PathLike[str] = ".",
) -> Verdict:
    """The final V2 verdict for ``primitive``: held-out vectors plus designed
    discriminating inputs for the live ``candidates``, run against ``binary``.
    """
    reference = references.get(primitive)
    if reference is None:
        unknown = VectorEvidence(
            input_hex="", expected=None, actual=None, error=f"unknown primitive: {primitive}"
        )
        return Verdict("inconclusive", (unknown,))

    held_out = load_held_out_inputs(root)
    design = design_inputs(candidates, references)
    inputs = tuple(dict.fromkeys((*held_out, *design.inputs)))
    return verify_with_inputs(binary, reference, inputs)
