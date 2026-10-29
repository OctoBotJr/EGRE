"""Reconstruct the exact model context at any step of a persisted run file.

Run files (written by ``egre.cli.run``) log ``messages_sent`` verbatim for
every step, so replay is a direct lookup rather than re-simulating the loop's
message-assembly logic.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, cast

from egre.llm.base import Message


class ReplayError(ValueError):
    """The run document does not contain enough information to replay a step."""


def _step_documents(run_document: Mapping[str, Any]) -> Sequence[Mapping[str, Any]]:
    steps = run_document.get("steps")
    if not isinstance(steps, Sequence):
        raise ReplayError("run document has no 'steps' list")
    return steps


def step_at(run_document: Mapping[str, Any], step_index: int) -> Mapping[str, Any]:
    """Return the full recorded step document for ``step_index`` (1-based)."""
    for step in _step_documents(run_document):
        if step.get("index") == step_index:
            return step
    raise ReplayError(f"run document has no step {step_index}")


def reconstruct_context(run_document: Mapping[str, Any], step_index: int) -> tuple[Message, ...]:
    """Return the exact messages sent to the model at ``step_index`` (1-based)."""
    messages = step_at(run_document, step_index).get("messages_sent")
    if not isinstance(messages, Sequence):
        raise ReplayError(f"step {step_index} has no recorded messages_sent")
    return tuple(
        cast(Message, {"role": message["role"], "content": message["content"]})
        for message in messages
    )
