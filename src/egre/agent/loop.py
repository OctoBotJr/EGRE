"""Bounded JSON action loop connecting one LLM client to mediator tools."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from pydantic import ValidationError

from egre.claims.schema import Claim, Registry
from egre.ledger.store import UnknownHandleError
from egre.llm.base import LLMClient, Message
from egre.mediator.tools import MediatorTools, ToolResult

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


def _json_object(raw: str) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        raise AgentProtocolError("assistant response must be valid JSON") from exc
    if not isinstance(value, dict):
        raise AgentProtocolError("assistant response must be a JSON object")
    return value


def _required(action: Mapping[str, Any], key: str, expected: type[Any]) -> Any:
    value = action.get(key)
    if isinstance(value, bool) and expected is int:
        raise AgentProtocolError(f"{key} must be {expected.__name__}")
    if not isinstance(value, expected):
        raise AgentProtocolError(f"{key} must be {expected.__name__}")
    return value


def _tool_view(result: ToolResult) -> dict[str, object]:
    return {
        "handle": result.handle,
        "kind": result.kind,
        "anchor": {"start": result.anchor.start, "end": result.anchor.end},
        "content": result.content,
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

    def run(self) -> Registry:
        registry = Registry()
        messages: list[Message] = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps({"task": self._task}, sort_keys=True)},
        ]

        for _ in range(self._max_steps):
            raw = self._client.complete(tuple(messages))
            messages.append({"role": "assistant", "content": raw})
            action = _json_object(raw)
            name = action.get("action")
            if not isinstance(name, str):
                raise AgentProtocolError("action must be a string")

            if name in {"disassemble", "read_memory", "run"}:
                result = self._execute_tool(action, name)
                messages.append(
                    {
                        "role": "user",
                        "content": json.dumps({"observation": _tool_view(result)}, sort_keys=True),
                    }
                )
                continue

            if name == "claim":
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
                continue

            if name == "finish":
                return registry

            raise AgentProtocolError(f"unknown action: {name}")

        raise StepLimitError(f"agent exceeded the {self._max_steps}-step limit")


def run_agent(
    task: Mapping[str, object],
    tools: MediatorTools,
    client: LLMClient,
    *,
    max_steps: int = DEFAULT_MAX_STEPS,
) -> Registry:
    """Convenience wrapper around :class:`AgentLoop`."""
    return AgentLoop(task, tools, client, max_steps=max_steps).run()

