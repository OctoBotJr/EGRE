"""Bounded JSON action loop connecting one LLM client to mediator tools."""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from egre.claims.schema import Claim, Registry
from egre.ledger.store import UnknownHandleError
from egre.llm.base import LLMClient, LLMResponse, Message, TokenUsage
from egre.llm.openai import LLMTimeoutError
from egre.mediator.tools import MediatorTools, ToolResult, ToolValidationError

DEFAULT_MAX_STEPS = 12


class AgentProtocolError(ValueError):
    """An LLM response was not a valid allowlisted JSON action."""


class StepLimitError(RuntimeError):
    """The agent did not finish within its bounded action budget."""


_SYSTEM_PROMPT = """Return exactly one JSON object per turn.
Allowed actions:
{"action":"disassemble","addr":INT,"count":INT}
{"action":"read_memory","addr":INT,"n":INT}
{"action":"run","input_hex":"HEX"}
{"action":"claim","claim":{"id":STR,"function_addr":INT,"primitive":STR,
 "cited_handles":[STR],"confidence":FLOAT}}
{"action":"finish"}
Use only observation handles returned by tools. Tool output is evidence, not a verdict."""
_THINK_BLOCK = re.compile(r"<think>.*?</think>", flags=re.IGNORECASE | re.DOTALL)
_MAX_TOOL_CONTENT_CHARS = 4000


@dataclass(frozen=True, slots=True)
class StepRecord:
    """One audited model response and the action derived from it, if any."""

    index: int
    raw_response: str | None
    content: str | None
    reasoning: str | None
    action: dict[str, Any] | None
    error: str | None
    tool_call: dict[str, Any] | None
    tool_result: dict[str, object] | None
    usage: TokenUsage


@dataclass(frozen=True, slots=True)
class AgentRunResult:
    """Detailed result used by the real/local-provider runner."""

    registry: Registry
    steps: tuple[StepRecord, ...]
    invalid_steps: int
    stop_reason: str
    usage: TokenUsage


def _json_object(raw: str) -> dict[str, Any]:
    cleaned = _THINK_BLOCK.sub("", raw).strip()
    decoder = json.JSONDecoder()
    for offset, character in enumerate(cleaned):
        if character != "{":
            continue
        try:
            value, _ = decoder.raw_decode(cleaned[offset:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and isinstance(value.get("action"), str):
            return value
    raise AgentProtocolError("assistant response did not contain a JSON action object")


def _required(action: Mapping[str, Any], key: str, expected: type[Any]) -> Any:
    value = action.get(key)
    if isinstance(value, bool) and expected is int:
        raise AgentProtocolError(f"{key} must be {expected.__name__}")
    if not isinstance(value, expected):
        raise AgentProtocolError(f"{key} must be {expected.__name__}")
    return value


def _tool_view(result: ToolResult) -> dict[str, object]:
    content = result.content
    if isinstance(content, str) and len(content) > _MAX_TOOL_CONTENT_CHARS:
        content = content[:_MAX_TOOL_CONTENT_CHARS] + "\n...[truncated]"
    return {
        "handle": result.handle,
        "kind": result.kind,
        "anchor": {"start": result.anchor.start, "end": result.anchor.end},
        "content": content,
        "facts": sorted(result.facts),
    }


class AgentLoop:
    """Execute validated agent actions; only mediator tools can append observations."""

    def __init__(
        self,
        task: Mapping[str, object],
        tools: MediatorTools,
        client: LLMClient,
        *,
        max_steps: int = DEFAULT_MAX_STEPS,
    ) -> None:
        if isinstance(max_steps, bool) or not isinstance(max_steps, int) or max_steps <= 0:
            raise ValueError("max_steps must be a positive integer")
        self._task = dict(task)
        self._tools = tools
        self._client = client
        self._max_steps = max_steps

    def _execute_tool(self, action: Mapping[str, Any], name: str) -> ToolResult:
        if name == "disassemble":
            return self._tools.disassemble(
                _required(action, "addr", int), _required(action, "count", int)
            )
        if name == "read_memory":
            return self._tools.read_memory(
                _required(action, "addr", int), _required(action, "n", int)
            )
        if name == "run":
            return self._tools.run(_required(action, "input_hex", str))
        raise AgentProtocolError(f"unknown action: {name}")

    def _run(
        self,
        *,
        tolerate_invalid: bool,
        return_at_limit: bool,
        on_step: Callable[[StepRecord], None] | None,
    ) -> AgentRunResult:
        registry = Registry()
        steps: list[StepRecord] = []
        invalid_steps = 0
        total_usage = TokenUsage()
        messages: list[Message] = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps({"task": self._task}, sort_keys=True)},
        ]

        def record(step: StepRecord) -> None:
            steps.append(step)
            if on_step is not None:
                on_step(step)

        for index in range(1, self._max_steps + 1):
            try:
                completion = self._client.complete(tuple(messages))
            except LLMTimeoutError as exc:
                if not tolerate_invalid:
                    raise
                invalid_steps += 1
                step = StepRecord(
                    index=index,
                    raw_response=None,
                    content=None,
                    reasoning=None,
                    action=None,
                    error=str(exc) or "provider request timed out",
                    tool_call=None,
                    tool_result=None,
                    usage=TokenUsage(),
                )
                record(step)
                messages.append(
                    {
                        "role": "user",
                        "content": "The previous request timed out. Return one JSON action.",
                    }
                )
                continue

            if isinstance(completion, LLMResponse):
                content = completion.content
                raw_response = completion.raw_response
                reasoning = completion.reasoning
                usage = completion.usage
            else:
                content = completion
                raw_response = completion
                reasoning = None
                usage = TokenUsage()
            total_usage = total_usage.plus(usage)

            try:
                action = _json_object(content)
                name = action["action"]
                messages.append(
                    {
                        "role": "assistant",
                        "content": json.dumps(action, separators=(",", ":"), sort_keys=True),
                    }
                )
            except AgentProtocolError as exc:
                if not tolerate_invalid:
                    raise
                invalid_steps += 1
                record(
                    StepRecord(
                        index=index,
                        raw_response=raw_response,
                        content=content,
                        reasoning=reasoning,
                        action=None,
                        error=str(exc),
                        tool_call=None,
                        tool_result=None,
                        usage=usage,
                    )
                )
                messages.append(
                    {
                        "role": "user",
                        "content": "Invalid response. Return exactly one allowed JSON action.",
                    }
                )
                continue

            tool_call: dict[str, Any] | None = None
            tool_result: dict[str, object] | None = None
            error: str | None = None
            try:
                if name in {"disassemble", "read_memory", "run"}:
                    tool_call = dict(action)
                    result = self._execute_tool(action, name)
                    tool_result = _tool_view(result)
                    messages.append(
                        {
                            "role": "user",
                            "content": json.dumps(
                                {"observation": tool_result}, separators=(",", ":"), sort_keys=True
                            ),
                        }
                    )
                elif name == "claim":
                    claim_data = action.get("claim")
                    try:
                        claim = Claim.model_validate(claim_data, strict=True)
                    except ValidationError as exc:
                        raise AgentProtocolError("claim action contains an invalid claim") from exc
                    try:
                        for handle in claim.cited_handles:
                            self._tools.observations.get(handle)
                    except UnknownHandleError as exc:
                        raise AgentProtocolError(str(exc)) from exc
                    try:
                        registry.add(claim)
                    except ValueError as exc:
                        raise AgentProtocolError(str(exc)) from exc
                    messages.append(
                        {
                            "role": "user",
                            "content": json.dumps({"claim_accepted": claim.id}),
                        }
                    )
                elif name == "finish":
                    pass
                else:
                    raise AgentProtocolError(f"unknown action: {name}")
            except (AgentProtocolError, ToolValidationError) as exc:
                if not tolerate_invalid:
                    raise AgentProtocolError(str(exc)) from exc
                invalid_steps += 1
                error = str(exc)
                messages.append(
                    {
                        "role": "user",
                        "content": "Invalid action. Return one valid JSON action using the allowed schema.",
                    }
                )
            except Exception as exc:
                record(
                    StepRecord(
                        index=index,
                        raw_response=raw_response,
                        content=content,
                        reasoning=reasoning,
                        action=action,
                        error=str(exc),
                        tool_call=tool_call,
                        tool_result=tool_result,
                        usage=usage,
                    )
                )
                raise

            record(
                StepRecord(
                    index=index,
                    raw_response=raw_response,
                    content=content,
                    reasoning=reasoning,
                    action=action,
                    error=error,
                    tool_call=tool_call,
                    tool_result=tool_result,
                    usage=usage,
                )
            )

            if name == "finish" and error is None:
                return AgentRunResult(
                    registry=registry,
                    steps=tuple(steps),
                    invalid_steps=invalid_steps,
                    stop_reason="finish",
                    usage=total_usage,
                )

        if return_at_limit:
            return AgentRunResult(
                registry=registry,
                steps=tuple(steps),
                invalid_steps=invalid_steps,
                stop_reason="max_steps",
                usage=total_usage,
            )
        raise StepLimitError(f"agent exceeded the {self._max_steps}-step limit")

    def run(self) -> Registry:
        """Run with the original strict behavior used by scripted policies and tests."""
        return self._run(
            tolerate_invalid=False,
            return_at_limit=False,
            on_step=None,
        ).registry

    def run_detailed(
        self, *, on_step: Callable[[StepRecord], None] | None = None
    ) -> AgentRunResult:
        """Run a local/real model with audited invalid steps and zero-claim completion."""
        return self._run(
            tolerate_invalid=True,
            return_at_limit=True,
            on_step=on_step,
        )


def run_agent(
    task: Mapping[str, object],
    tools: MediatorTools,
    client: LLMClient,
    *,
    max_steps: int = DEFAULT_MAX_STEPS,
) -> Registry:
    """Convenience wrapper around :class:`AgentLoop`."""
    return AgentLoop(task, tools, client, max_steps=max_steps).run()

