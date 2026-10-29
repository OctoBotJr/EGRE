import json
from pathlib import Path

import pytest

from egre.agent.loop import AgentLoop, AgentProtocolError
from egre.llm.fake import FakeLLM
from egre.mediator.tools import MediatorTools

pytestmark = pytest.mark.toolchain

ROOT = Path(__file__).resolve().parents[2]


def _task(program: str) -> dict[str, object]:
    return json.loads((ROOT / "corpus" / "tasks" / f"{program}.json").read_text())


def test_revise_claim_disabled_by_default_is_an_unknown_action() -> None:
    task = _task("crc32_clean")
    tools = MediatorTools(task, root=ROOT)
    client = FakeLLM(['{"action":"retract_claim","claim_id":"c1"}'])

    with pytest.raises(AgentProtocolError, match="unknown action"):
        AgentLoop(task, tools, client).run()


def test_revision_loop_resolves_unqualified_evidence_within_one_revision() -> None:
    """Acceptance for V-15: a scripted policy revises after UNEXECUTED/UNQUALIFIED_EVIDENCE
    and reaches the expected (structural) tier within the 2-revision budget."""
    task = _task("fnv1a_crcdecoy")
    addr = task["function_addr"]
    assert isinstance(addr, int)
    tools = MediatorTools(task, root=ROOT)

    client = FakeLLM(
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
                        "confidence": 0.8,
                    },
                }
            ),
            json.dumps({"action": "run", "input_hex": "61"}),
            json.dumps(
                {
                    "action": "revise_claim",
                    "claim": {
                        "id": "c1",
                        "function_addr": addr,
                        "primitive": "fnv1a32",
                        "cited_handles": ["obs-000001"],
                        "confidence": 0.95,
                    },
                }
            ),
            '{"action":"finish"}',
        ]
    )

    loop = AgentLoop(task, tools, client, enable_revision=True)
    result = loop.run_detailed()

    assert result.invalid_steps == 0
    (claim,) = result.registry.claims
    assert claim.confidence == 0.95
    assert result.registry.revisions("c1") == 1

    # messages_sent at step N+1 ends with the feedback message appended after step N's action
    first_feedback_message = json.loads(result.steps[2].messages_sent[-1]["content"])
    assert first_feedback_message["claim_accepted"] == "c1"
    assert first_feedback_message["reason_codes"]  # non-empty: not yet qualified (no run yet)

    second_feedback_message = json.loads(result.steps[4].messages_sent[-1]["content"])
    assert second_feedback_message["claim_revised"] == "c1"
    second_codes = second_feedback_message["reason_codes"]
    # resolved: the tier reached structural (STRUCTURAL_ONLY, not CONTESTED_BY/NO_SUPPORTING_EVIDENCE),
    # and the earlier execution-qualification gap is gone now that a run exists and covers this block.
    assert "STRUCTURAL_ONLY" in second_codes
    assert not any(code.startswith("CONTESTED_BY") for code in second_codes)
    assert "NO_SUPPORTING_EVIDENCE" not in second_codes
    assert "UNQUALIFIED_EVIDENCE" not in second_codes
    assert "UNEXECUTED_EVIDENCE" not in second_codes


def test_retract_claim_frees_the_slot_for_a_fresh_claim() -> None:
    task = _task("crc32_clean")
    addr = task["function_addr"]
    assert isinstance(addr, int)
    tools = MediatorTools(task, root=ROOT)
    client = FakeLLM(
        [
            json.dumps({"action": "disassemble", "addr": addr, "count": 48}),
            json.dumps(
                {
                    "action": "claim",
                    "claim": {
                        "id": "c1",
                        "function_addr": addr,
                        "primitive": "djb2",
                        "cited_handles": ["obs-000001"],
                        "confidence": 0.3,
                    },
                }
            ),
            '{"action":"retract_claim","claim_id":"c1"}',
            json.dumps(
                {
                    "action": "claim",
                    "claim": {
                        "id": "c1",
                        "function_addr": addr,
                        "primitive": "crc32",
                        "cited_handles": ["obs-000001"],
                        "confidence": 0.9,
                    },
                }
            ),
            '{"action":"finish"}',
        ]
    )

    registry = AgentLoop(task, tools, client, enable_revision=True).run()

    (claim,) = registry.claims
    assert claim.primitive == "crc32"
    assert registry.revisions("c1") == 0  # a fresh claim, not a revision


def test_revise_claim_unknown_id_is_an_agent_protocol_error() -> None:
    task = _task("crc32_clean")
    addr = task["function_addr"]
    assert isinstance(addr, int)
    tools = MediatorTools(task, root=ROOT)
    client = FakeLLM(
        [
            json.dumps(
                {
                    "action": "revise_claim",
                    "claim": {
                        "id": "missing",
                        "function_addr": addr,
                        "primitive": "crc32",
                        "cited_handles": [],
                        "confidence": 0.5,
                    },
                }
            )
        ]
    )

    with pytest.raises(AgentProtocolError, match="no claim to revise"):
        AgentLoop(task, tools, client, enable_revision=True).run()


def test_revise_claim_past_the_limit_is_an_agent_protocol_error() -> None:
    task = _task("crc32_clean")
    addr = task["function_addr"]
    assert isinstance(addr, int)
    tools = MediatorTools(task, root=ROOT)

    def revise(confidence: float) -> str:
        return json.dumps(
            {
                "action": "revise_claim",
                "claim": {
                    "id": "c1",
                    "function_addr": addr,
                    "primitive": "crc32",
                    "cited_handles": ["obs-000001"],
                    "confidence": confidence,
                },
            }
        )

    client = FakeLLM(
        [
            json.dumps({"action": "disassemble", "addr": addr, "count": 48}),
            json.dumps(
                {
                    "action": "claim",
                    "claim": {
                        "id": "c1",
                        "function_addr": addr,
                        "primitive": "crc32",
                        "cited_handles": ["obs-000001"],
                        "confidence": 0.5,
                    },
                }
            ),
            revise(0.6),
            revise(0.7),
            revise(0.8),  # third revision: over the MAX_REVISIONS=2 budget
        ]
    )

    with pytest.raises(AgentProtocolError, match="already been revised 2 times"):
        AgentLoop(task, tools, client, enable_revision=True).run()
