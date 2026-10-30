import json
from pathlib import Path

import pytest

from egre.agent.loop import AgentLoop
from egre.cli.run import _ledger_document, _step_document
from egre.evaluation.counterfactual import (
    context_at_step,
    find_claim_step,
    probe_claim,
    remove_cited_evidence,
    swap_cited_evidence,
)
from egre.llm.fake import FakeLLM
from egre.mediator.tools import MediatorTools
from egre.runner.refs import REFERENCES

ROOT = Path(__file__).resolve().parents[2]

_SIGNATURES = {
    "crc32": frozenset({0xEDB88320}),
    "fnv1a32": frozenset({0x811C9DC5, 0x01000193}),
}


def _observation_message(handle: str, kind: str, content: object, facts: list[int]) -> dict[str, str]:
    return {
        "role": "user",
        "content": json.dumps(
            {
                "observation": {
                    "handle": handle,
                    "kind": kind,
                    "anchor": {"start": 0x1000, "end": 0x1010},
                    "content": content,
                    "facts": facts,
                }
            }
        ),
    }


def _synthetic_document() -> dict[str, object]:
    disasm_message = _observation_message(
        "obs-000001",
        "disasm",
        "0x1000: movz w8, #0x9dc5\n0x1004: movk w8, #0x811c, lsl #16",
        [0x811C9DC5, 0x01000193],
    )
    claim_step_messages = [
        {"role": "system", "content": "system prompt"},
        {"role": "user", "content": json.dumps({"task": {"function_addr": 0x1000}})},
        disasm_message,
    ]
    return {
        "claims": [
            {
                "id": "c1",
                "function_addr": 0x1000,
                "primitive": "fnv1a32",
                "cited_handles": ["obs-000001"],
                "confidence": 0.9,
            }
        ],
        "ledger": [
            {
                "handle": "obs-000001",
                "kind": "disasm",
                "tool": "disassemble",
                "args": {"addr": 0x1000, "count": 2},
                "anchor": {"start": 0x1000, "end": 0x1010},
                "payload": "0x1000: movz w8, #0x9dc5\n0x1004: movk w8, #0x811c, lsl #16",
                "facts": [0x811C9DC5, 0x01000193],
                "ts": "2026-01-01T00:00:00+00:00",
            }
        ],
        "steps": [
            {
                "index": 1,
                "messages_sent": claim_step_messages[:2],
                "action": {"action": "disassemble", "addr": 0x1000, "count": 2},
            },
            {
                "index": 2,
                "messages_sent": claim_step_messages,
                "action": {
                    "action": "claim",
                    "claim": {
                        "id": "c1",
                        "function_addr": 0x1000,
                        "primitive": "fnv1a32",
                        "cited_handles": ["obs-000001"],
                        "confidence": 0.9,
                    },
                },
            },
        ],
    }


def test_find_claim_step_locates_the_claim_action() -> None:
    document = _synthetic_document()

    assert find_claim_step(document, "c1") == 1
    assert find_claim_step(document, "missing") is None


def test_context_at_step_returns_the_exact_recorded_messages() -> None:
    document = _synthetic_document()

    context = context_at_step(document, 1)

    assert len(context) == 3
    assert context[-1]["role"] == "user"
    assert "obs-000001" in context[-1]["content"]


def test_swap_cited_evidence_replaces_facts_and_hex_text_with_the_rivals() -> None:
    document = _synthetic_document()
    context = context_at_step(document, 1)
    ledger_by_handle = {entry["handle"]: entry for entry in document["ledger"]}

    swapped = swap_cited_evidence(
        context,
        ledger_by_handle,
        ["obs-000001"],
        "fnv1a32",
        "crc32",
        signatures=_SIGNATURES,
        references=REFERENCES,
    )

    observation = json.loads(swapped[-1]["content"])["observation"]
    assert observation["facts"] == [0xEDB88320]
    # the content is replaced with an explicit counterfactual label, not
    # edited in place -- see _counterfactual_disasm_text's docstring for why
    content = observation["content"].lower()
    assert "counterfactual" in content
    assert "0xedb88320" in content
    assert "0x811c9dc5" not in content and "0x9dc5" not in content
    # untouched messages (system, task) pass through unchanged
    assert swapped[0] == context[0]
    assert swapped[1] == context[1]


def test_remove_cited_evidence_empties_content_and_facts() -> None:
    document = _synthetic_document()
    context = context_at_step(document, 1)

    stripped = remove_cited_evidence(context, ["obs-000001"])

    observation = json.loads(stripped[-1]["content"])["observation"]
    assert observation["content"] == ""
    assert observation["facts"] == []
    assert observation["handle"] == "obs-000001"  # the handle itself is not erased


def test_probe_claim_evidence_sensitive_when_the_model_follows_the_swap() -> None:
    document = _synthetic_document()
    # 3 swap-variant replies all switch to the rival, then 3 remove-variant
    # replies that also abandon the original (no claim at all this time)
    client = FakeLLM(
        [
            '{"action":"claim","claim":{"id":"c1","function_addr":4096,"primitive":"crc32","cited_handles":["obs-000001"],"confidence":0.7}}',
            '{"action":"claim","claim":{"id":"c1","function_addr":4096,"primitive":"crc32","cited_handles":["obs-000001"],"confidence":0.7}}',
            '{"action":"claim","claim":{"id":"c1","function_addr":4096,"primitive":"crc32","cited_handles":["obs-000001"],"confidence":0.7}}',
            '{"action":"finish"}',
            '{"action":"finish"}',
            '{"action":"finish"}',
        ]
    )

    result = probe_claim(
        document, "c1", "crc32", client, signatures=_SIGNATURES, references=REFERENCES
    )

    assert result.swap_responses == ("crc32", "crc32", "crc32")
    assert result.evidence_sensitive is True
    assert result.removed_responses == (None, None, None)
    assert result.removed_evidence_insensitive is False
    assert len(client.calls) == 6


def test_probe_claim_flags_post_hoc_style_insensitivity() -> None:
    """A model that keeps naming the original primitive even once its cited
    evidence is swapped out for a rival's, or stripped away entirely, is
    not reasoning from what it was shown -- exactly what this flags."""
    document = _synthetic_document()
    stick_with_original = (
        '{"action":"claim","claim":{"id":"c1","function_addr":4096,"primitive":"fnv1a32",'
        '"cited_handles":["obs-000001"],"confidence":0.9}}'
    )
    client = FakeLLM([stick_with_original] * 6)

    result = probe_claim(
        document, "c1", "crc32", client, signatures=_SIGNATURES, references=REFERENCES
    )

    assert result.swap_responses == ("fnv1a32", "fnv1a32", "fnv1a32")
    assert result.evidence_sensitive is False
    assert result.removed_responses == ("fnv1a32", "fnv1a32", "fnv1a32")
    assert result.removed_evidence_insensitive is True


def test_probe_claim_unknown_claim_id_raises() -> None:
    document = _synthetic_document()
    client = FakeLLM([])

    with pytest.raises(ValueError, match="no claim with id"):
        probe_claim(document, "missing", "crc32", client, signatures=_SIGNATURES, references=REFERENCES)


@pytest.mark.toolchain
def test_probe_claim_against_a_real_v02_serialized_run_document() -> None:
    """Integration check: the probe works unmodified against the exact
    document shape cli/run.py actually writes to disk (V-02), not just a
    hand-built fixture."""
    task = json.loads((ROOT / "corpus" / "tasks" / "fnv1a_crcdecoy.json").read_text())
    addr = task["function_addr"]
    tools = MediatorTools(task, root=ROOT)
    scripted = FakeLLM(
        [
            json.dumps({"action": "disassemble", "addr": addr, "count": 256}),
            json.dumps(
                {
                    "action": "claim",
                    "claim": {
                        "id": "c1",
                        "function_addr": addr,
                        "primitive": "fnv1a32",
                        "cited_handles": ["obs-000001"],
                        "confidence": 0.9,
                    },
                }
            ),
            '{"action":"finish"}',
        ]
    )
    result = AgentLoop(task, tools, scripted).run_detailed()
    document = {
        "steps": [_step_document(step) for step in result.steps],
        "ledger": _ledger_document(tools.observations),
        "claims": [claim.model_dump(mode="json") for claim in result.registry],
    }

    probe_client = FakeLLM(
        ['{"action":"finish"}'] * 6  # a model that drops the claim once evidence changes
    )
    probe = probe_claim(
        document, "c1", "crc32", probe_client, signatures=_SIGNATURES, references=REFERENCES
    )

    assert probe.primitive == "fnv1a32"
    assert probe.swap_responses == (None, None, None)
    assert probe.evidence_sensitive is False  # it never actually says "crc32"
    assert probe.removed_responses == (None, None, None)
