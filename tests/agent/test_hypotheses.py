import json
from typing import cast

from egre.agent.loop import (
    AgentLoop,
    hypotheses_schema,
    hypothesis_steps,
    observation_step_map,
)
from egre.controller.status_v2 import HypothesisStep, detect_post_hoc
from egre.ledger.store import Anchor, Ledger
from egre.llm.fake import FakeLLM
from egre.mediator.tools import MediatorTools, ToolResult


class _FakeTools:
    def __init__(self) -> None:
        self._ledger = Ledger()
        self.observations = self._ledger.reader()

    def disassemble(self, addr: int, count: int) -> ToolResult:
        observation = self._ledger.record(
            kind="disasm",
            tool="disassemble",
            args={"addr": addr, "count": count},
            anchor=Anchor(addr, addr + 4),
            payload="0x1000: mov w8, #0x8320",
            facts={0xEDB88320},
        )
        return ToolResult(
            observation.handle,
            observation.kind,
            observation.anchor,
            observation.payload,
            observation.facts,
        )

    def read_memory(self, addr: int, n: int) -> ToolResult:
        raise AssertionError((addr, n))

    def run(self, input_hex: str) -> ToolResult:
        raise AssertionError(input_hex)


def _loop(client: FakeLLM, **kwargs: object) -> tuple[AgentLoop, _FakeTools]:
    task = {"function_addr": 0x1000, "function_size": 16, "binary": "unused"}
    tools = _FakeTools()
    return AgentLoop(task, cast(MediatorTools, tools), client, **kwargs), tools  # type: ignore[arg-type]


def _action(action: dict[str, object], hypotheses: dict[str, float] | None) -> str:
    if hypotheses is not None:
        action = {**action, "hypotheses": hypotheses}
    return json.dumps(action)


def test_hypotheses_schema_requires_action_and_hypotheses() -> None:
    schema = hypotheses_schema(("crc32", "fnv1a32"))

    properties = schema["json_schema"]["schema"]["properties"]
    assert schema["json_schema"]["schema"]["required"] == ["action", "hypotheses"]
    assert set(properties["hypotheses"]["properties"]) == {"crc32", "fnv1a32", "other"}


def test_valid_hypotheses_are_accepted_and_counted_as_a_normal_step() -> None:
    client = FakeLLM(
        [
            _action({"action": "finish"}, {"crc32": 0.9, "fnv1a32": 0.1, "adler32": 0.0, "djb2": 0.0}),
        ]
    )

    loop, _tools = _loop(client, require_hypotheses=True)
    result = loop.run_detailed()

    assert result.invalid_steps == 0
    assert result.steps[0].action is not None
    assert result.steps[0].action["hypotheses"]["crc32"] == 0.9


def test_missing_hypotheses_counts_as_an_invalid_step_like_any_malformed_action() -> None:
    client = FakeLLM(
        [
            _action({"action": "finish"}, None),  # no hypotheses field at all
            _action({"action": "finish"}, {"crc32": 1.0}),
        ]
    )

    loop, _tools = _loop(client, require_hypotheses=True)
    result = loop.run_detailed()

    assert result.invalid_steps == 1
    assert result.steps[0].error is not None
    assert "hypotheses" in result.steps[0].error


def test_out_of_range_or_unknown_hypothesis_name_is_invalid() -> None:
    client = FakeLLM(
        [
            _action({"action": "finish"}, {"crc32": 1.5}),
            _action({"action": "finish"}, {"not_a_primitive": 0.5}),
            _action({"action": "finish"}, {"crc32": 1.0}),
        ]
    )

    loop, _tools = _loop(client, require_hypotheses=True)
    result = loop.run_detailed()

    assert result.invalid_steps == 2


def test_require_hypotheses_false_by_default_ignores_a_missing_field() -> None:
    client = FakeLLM(['{"action":"finish"}'])

    loop, _tools = _loop(client)
    result = loop.run_detailed()

    assert result.invalid_steps == 0


def test_observation_step_map_tracks_the_step_that_produced_each_handle() -> None:
    client = FakeLLM(
        [
            _action({"action": "disassemble", "addr": 0x1000, "count": 4}, {"crc32": 0.9}),
            _action({"action": "finish"}, {"crc32": 0.9}),
        ]
    )

    loop, _tools = _loop(client, require_hypotheses=True)
    result = loop.run_detailed()
    mapping = observation_step_map(result.steps)

    assert mapping == {"obs-000001": 1}


def test_hypothesis_steps_collects_confidences_declared_at_each_step() -> None:
    client = FakeLLM(
        [
            _action({"action": "disassemble", "addr": 0x1000, "count": 4}, {"crc32": 0.9}),
            _action({"action": "finish"}, {"crc32": 0.95, "fnv1a32": 0.05}),
        ]
    )

    loop, _tools = _loop(client, require_hypotheses=True)
    result = loop.run_detailed()
    steps = hypothesis_steps(result.steps)

    assert steps == (
        HypothesisStep(step=1, confidences={"crc32": 0.9}),
        HypothesisStep(step=2, confidences={"crc32": 0.95, "fnv1a32": 0.05}),
    )


def test_hypothesis_steps_feed_detect_post_hoc_end_to_end() -> None:
    """The real payoff of V-13: post_hoc now runs on genuine step data, not a stub."""
    client = FakeLLM(
        [
            # confident in crc32 BEFORE citing any evidence for it
            _action({"action": "disassemble", "addr": 0x1000, "count": 4}, {"crc32": 0.9}),
            _action(
                {
                    "action": "claim",
                    "claim": {
                        "id": "c1",
                        "function_addr": 0x1000,
                        "primitive": "crc32",
                        "cited_handles": ["obs-000001"],
                        "confidence": 0.9,
                    },
                },
                {"crc32": 0.9},
            ),
            _action({"action": "finish"}, {"crc32": 0.9}),
        ]
    )

    loop, tools = _loop(client, require_hypotheses=True)
    result = loop.run_detailed()
    steps = hypothesis_steps(result.steps)
    obs_steps = observation_step_map(result.steps)

    (claim,) = result.registry.claims
    assert detect_post_hoc("crc32", steps, claim.cited_handles, obs_steps, tools.observations) is False
    # the agent declared confidence at step 1, the same step the evidence was
    # gathered at -- not "before" the evidence existed, so this is not post-hoc
    # by the proxy's definition (it requires the support to postdate the claim).
