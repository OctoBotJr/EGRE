"""Counterfactual evidence-sensitivity probe (H7, V2_SPEC.md section 3.5, V-19).

Offline only, and it never runs the binary or the agent again: it rebuilds
the EXACT message context V-02 recorded at the step a claim was submitted
(or last revised), swaps the cited evidence for a rival's or removes it
outright, and re-queries the SAME model 3 times at temperature 0 / a fixed
seed (the caller's ``client`` is responsible for that determinism -- this
module just calls ``complete`` three times).

The model is the SUBJECT of this probe, never a judge: nothing it returns
here changes any claim's tier, status, or verdict (I2, I11). The question
being asked is purely "does this model's stated conclusion depend on the
evidence it cited", which is orthogonal to whether that conclusion is
correct or well-supported.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import cast

from egre.agent.loop import AgentProtocolError, _json_object
from egre.llm.base import CompletionResult, LLMClient, LLMResponse, Message
from egre.runner.refs import Reference

JsonValue = str | int | float | bool | None | list["JsonValue"] | dict[str, "JsonValue"]


def _completion_text(result: CompletionResult) -> str:
    return result.content if isinstance(result, LLMResponse) else result


def _extract_primitive(raw_content: str) -> str | None:
    """Best-effort: the primitive a response's claim action names, or None.

    Unlike ``egre.agent.loop``'s action parser, this never raises -- a
    response that isn't a valid claim action just means "no claim this
    time", which is itself a meaningful (evidence-insensitive-adjacent)
    outcome for the probe, not an error.
    """
    try:
        action = _json_object(raw_content)
    except AgentProtocolError:
        return None
    if action.get("action") != "claim":
        return None
    claim = action.get("claim")
    if not isinstance(claim, dict):
        return None
    primitive = claim.get("primitive")
    return primitive if isinstance(primitive, str) else None


def _counterfactual_disasm_text(rival_signature: Sequence[int]) -> str:
    """A safe stand-in for swapped disassembly text.

    Editing real assembly text in place is NOT attempted: ARM64 -O0 splits a
    32-bit constant into two small hex fragments (``movz``/``movk``), and
    naive substring replacement of a value that small risks corrupting
    unrelated text that happens to contain the same short hex digits (an
    address, another operand) -- confirmed by a real false-positive match
    during testing (a 2-hex-digit fragment collided with an instruction
    address). Replacing the whole field with an explicit, honest
    counterfactual label is safer and no less informative to the model
    being probed than a surgically-edited-but-possibly-wrong listing would
    have been.
    """
    constants = ", ".join(f"{value:#x}" for value in rival_signature)
    return f"[counterfactual: signature constants replaced] constants present: {constants}"


def _parse_observation_message(message: Message) -> dict[str, JsonValue] | None:
    if message["role"] != "user":
        return None
    try:
        payload = json.loads(message["content"])
    except json.JSONDecodeError:
        return None
    if isinstance(payload, dict):
        observation = payload.get("observation")
        if isinstance(observation, dict):
            return observation
    return None


def find_claim_step(document: Mapping[str, object], claim_id: str) -> int | None:
    """Index of the last step that submitted or revised ``claim_id``, or None."""
    steps = document.get("steps")
    if not isinstance(steps, list):
        return None
    found: int | None = None
    for index, step in enumerate(steps):
        if not isinstance(step, dict):
            continue
        action = step.get("action")
        if not isinstance(action, dict) or action.get("action") not in ("claim", "revise_claim"):
            continue
        claim_data = action.get("claim")
        if isinstance(claim_data, dict) and claim_data.get("id") == claim_id:
            found = index
    return found


def context_at_step(document: Mapping[str, object], step_index: int) -> tuple[Message, ...]:
    """The exact ``messages_sent`` V-02 recorded for one step."""
    steps = document.get("steps")
    if not isinstance(steps, list) or not 0 <= step_index < len(steps):
        raise IndexError(f"no such step: {step_index}")
    step = steps[step_index]
    messages = step.get("messages_sent")
    if not isinstance(messages, list):
        raise TypeError(f"step {step_index} has no messages_sent list")
    return tuple({"role": m["role"], "content": m["content"]} for m in messages)


def _ledger_by_handle(document: Mapping[str, object]) -> dict[str, dict[str, object]]:
    entries = document.get("ledger")
    if not isinstance(entries, list):
        return {}
    return {entry["handle"]: entry for entry in entries if isinstance(entry, dict)}


def swap_cited_evidence(
    messages: Sequence[Message],
    ledger_by_handle: Mapping[str, Mapping[str, object]],
    cited_handles: Sequence[str],
    primitive: str,
    rival: str,
    *,
    signatures: Mapping[str, frozenset[int]],
    references: Mapping[str, Reference],
) -> tuple[Message, ...]:
    """Replace each cited observation's evidence with the rival's.

    Run outputs become ``ref_rival(x)``. Disassembly facts become the
    rival's signature constants; the content field becomes an explicit
    counterfactual label rather than edited assembly text (see
    :func:`_counterfactual_disasm_text` for why editing the text in place
    isn't safe).
    """
    cited = set(cited_handles)
    own_signature = sorted(signatures.get(primitive, frozenset()))
    rival_signature = sorted(signatures.get(rival, frozenset()))
    rival_reference = references.get(rival)

    swapped: list[Message] = []
    for message in messages:
        observation = _parse_observation_message(message)
        handle = observation.get("handle") if observation is not None else None
        if observation is None or handle not in cited:
            swapped.append(message)
            continue

        ledger_entry = ledger_by_handle.get(str(handle), {})
        kind = ledger_entry.get("kind")
        new_observation = dict(observation)

        if kind == "run" and rival_reference is not None:
            args = ledger_entry.get("args")
            input_hex = args.get("input_hex") if isinstance(args, dict) else None
            if isinstance(input_hex, str):
                new_observation["content"] = rival_reference(bytes.fromhex(input_hex))
        elif kind == "disasm":
            original_facts = observation.get("facts")
            fact_set: set[int] = (
                {fact for fact in original_facts if isinstance(fact, int)}
                if isinstance(original_facts, list)
                else set()
            )
            new_observation["facts"] = cast(
                "list[JsonValue]", sorted((fact_set - set(own_signature)) | set(rival_signature))
            )
            if isinstance(observation.get("content"), str) and rival_signature:
                new_observation["content"] = _counterfactual_disasm_text(rival_signature)

        swapped.append(
            {"role": message["role"], "content": json.dumps({"observation": new_observation})}
        )
    return tuple(swapped)


def remove_cited_evidence(messages: Sequence[Message], cited_handles: Sequence[str]) -> tuple[Message, ...]:
    """Strip each cited observation down to its handle: no content, no facts."""
    cited = set(cited_handles)
    stripped: list[Message] = []
    for message in messages:
        observation = _parse_observation_message(message)
        if observation is None or observation.get("handle") not in cited:
            stripped.append(message)
            continue
        emptied = dict(observation)
        emptied["content"] = ""
        emptied["facts"] = []
        stripped.append({"role": message["role"], "content": json.dumps({"observation": emptied})})
    return tuple(stripped)


@dataclass(frozen=True, slots=True)
class CounterfactualResult:
    claim_id: str
    primitive: str
    rival: str
    swap_responses: tuple[str | None, ...]
    evidence_sensitive: bool
    removed_responses: tuple[str | None, ...]
    removed_evidence_insensitive: bool

    def to_document(self) -> dict[str, JsonValue]:
        return {
            "claim_id": self.claim_id,
            "primitive": self.primitive,
            "rival": self.rival,
            "swap_responses": list(self.swap_responses),
            "evidence_sensitive": self.evidence_sensitive,
            "removed_responses": list(self.removed_responses),
            "removed_evidence_insensitive": self.removed_evidence_insensitive,
        }


def probe_claim(
    document: Mapping[str, object],
    claim_id: str,
    rival: str,
    client: LLMClient,
    *,
    signatures: Mapping[str, frozenset[int]],
    references: Mapping[str, Reference],
    repeats: int = 3,
) -> CounterfactualResult:
    """Run the swap and remove-evidence variants for one claim, 3x each.

    ``evidence_sensitive`` is True when the model switches to ``rival`` in
    at least 2 of ``repeats`` swap-variant replies. ``removed_evidence_insensitive``
    is True when the model keeps naming the ORIGINAL primitive in at least
    2 of ``repeats`` replies even with its cited evidence stripped away --
    a model that does this is post-rationalizing, not reasoning from what
    it was shown.
    """
    raw_claims = document.get("claims")
    if not isinstance(raw_claims, list):
        raise TypeError("run document has no 'claims' list")
    claim_data = next(
        (c for c in raw_claims if isinstance(c, dict) and c.get("id") == claim_id), None
    )
    if claim_data is None:
        raise ValueError(f"no claim with id {claim_id!r} in this run document")
    primitive = claim_data["primitive"]
    cited_handles = claim_data.get("cited_handles", [])

    step_index = find_claim_step(document, claim_id)
    if step_index is None:
        raise ValueError(f"no claim/revise_claim step found for {claim_id!r}")
    messages = context_at_step(document, step_index)
    ledger_by_handle = _ledger_by_handle(document)

    swapped = swap_cited_evidence(
        messages,
        ledger_by_handle,
        cited_handles,
        primitive,
        rival,
        signatures=signatures,
        references=references,
    )
    swap_responses = tuple(
        _extract_primitive(_completion_text(client.complete(swapped))) for _ in range(repeats)
    )
    evidence_sensitive = sum(response == rival for response in swap_responses) >= 2

    removed = remove_cited_evidence(messages, cited_handles)
    removed_responses = tuple(
        _extract_primitive(_completion_text(client.complete(removed))) for _ in range(repeats)
    )
    removed_evidence_insensitive = sum(response == primitive for response in removed_responses) >= 2

    return CounterfactualResult(
        claim_id=claim_id,
        primitive=primitive,
        rival=rival,
        swap_responses=swap_responses,
        evidence_sensitive=evidence_sensitive,
        removed_responses=removed_responses,
        removed_evidence_insensitive=removed_evidence_insensitive,
    )
