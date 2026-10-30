"""Deterministic scripted agent policies used by tests and the offline demo."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

from egre.llm.base import Message
from egre.runner.refs import REFERENCES

_SIGNATURES: Mapping[str, frozenset[int]] = {
    "crc32": frozenset({0xEDB88320}),
    "fnv1a32": frozenset({0x811C9DC5, 0x01000193}),
    "adler32": frozenset({65521}),
    "djb2": frozenset({5381}),
}
_EMULATOR_INPUTS = ("61", "616263", "313233343536373839")


def _message_object(messages: Sequence[Message], key: str) -> dict[str, Any]:
    for message in reversed(messages):
        if message["role"] != "user":
            continue
        value = json.loads(message["content"])
        if isinstance(value, dict) and key in value and isinstance(value[key], dict):
            return value[key]
    raise RuntimeError(f"scripted policy did not receive {key}")


def _task(messages: Sequence[Message]) -> dict[str, Any]:
    return _message_object(messages, "task")


def _observation(messages: Sequence[Message]) -> dict[str, Any]:
    return _message_object(messages, "observation")


def _query_result(messages: Sequence[Message]) -> dict[str, Any]:
    return _message_object(messages, "query_result")


def _claim(
    claim_id: str,
    addr: int,
    primitive: str,
    handles: list[str],
    confidence: float,
) -> str:
    return json.dumps(
        {
            "action": "claim",
            "claim": {
                "id": claim_id,
                "function_addr": addr,
                "primitive": primitive,
                "cited_handles": handles,
                "confidence": confidence,
            },
        }
    )


class GrepperPolicy:
    """P1: claim each primitive whose signature constants appear in disassembly."""

    def __init__(self) -> None:
        self._phase = "disassemble"
        self._matches: list[str] = []
        self._handle = ""

    def complete(self, messages: Sequence[Message]) -> str:
        task = _task(messages)
        addr = task["function_addr"]
        size = task["function_size"]
        if not isinstance(addr, int) or not isinstance(size, int):
            raise TypeError("scripted policy requires an integer function range")

        if self._phase == "disassemble":
            self._phase = "inspect"
            return json.dumps(
                {"action": "disassemble", "addr": addr, "count": min(256, (size + 3) // 4)}
            )
        if self._phase == "inspect":
            observation = _observation(messages)
            facts = observation.get("facts")
            if not isinstance(facts, list) or not all(isinstance(fact, int) for fact in facts):
                raise RuntimeError("disassembly observation has invalid facts")
            self._handle = str(observation["handle"])
            fact_set = set(facts)
            self._matches = [
                primitive
                for primitive, signature in _SIGNATURES.items()
                if not signature.isdisjoint(fact_set)
            ]
            self._phase = "claim"
        if self._matches:
            primitive = self._matches.pop(0)
            return _claim(f"p1-{primitive}", addr, primitive, [self._handle], 0.8)
        return '{"action":"finish"}'


class EmulatorPolicy:
    """P2: compare three native runs with local primitive references, then claim the match."""

    def __init__(self) -> None:
        self._next_input = 0
        self._pending_run = False
        self._runs: list[tuple[str, int]] = []
        self._matches: list[str] | None = None

    def complete(self, messages: Sequence[Message]) -> str:
        task = _task(messages)
        addr = task["function_addr"]
        if not isinstance(addr, int):
            raise TypeError("scripted policy requires an integer function address")

        if self._pending_run:
            observation = _observation(messages)
            handle = observation.get("handle")
            output = observation.get("content")
            if not isinstance(handle, str) or isinstance(output, bool) or not isinstance(output, int):
                raise RuntimeError("run observation has invalid content")
            self._runs.append((handle, output))
            self._pending_run = False

        if self._next_input < len(_EMULATOR_INPUTS):
            input_hex = _EMULATOR_INPUTS[self._next_input]
            self._next_input += 1
            self._pending_run = True
            return json.dumps({"action": "run", "input_hex": input_hex})

        if self._matches is None:
            outputs = [output for _, output in self._runs]
            self._matches = [
                primitive
                for primitive, reference in REFERENCES.items()
                if outputs
                == [reference(bytes.fromhex(input_hex)) for input_hex in _EMULATOR_INPUTS]
            ]
        if self._matches:
            primitive = self._matches.pop(0)
            return _claim(
                f"p2-{primitive}",
                addr,
                primitive,
                [handle for handle, _ in self._runs],
                0.95,
            )
        return '{"action":"finish"}'


class PriorGuesserPolicy:
    """P3: inspect once, then always submit a CRC32 claim citing that observation."""

    def __init__(self) -> None:
        self._phase = "disassemble"

    def complete(self, messages: Sequence[Message]) -> str:
        task = _task(messages)
        addr = task["function_addr"]
        size = task["function_size"]
        if not isinstance(addr, int) or not isinstance(size, int):
            raise TypeError("scripted policy requires an integer function range")
        if self._phase == "disassemble":
            self._phase = "claim"
            return json.dumps(
                {"action": "disassemble", "addr": addr, "count": min(256, (size + 3) // 4)}
            )
        if self._phase == "claim":
            observation = _observation(messages)
            handle = observation.get("handle")
            if not isinstance(handle, str):
                raise RuntimeError("disassembly observation has invalid handle")
            self._phase = "finish"
            return _claim("p3-crc32", addr, "crc32", [handle], 0.55)
        return '{"action":"finish"}'


class TraceQualifiedGrepperPolicy:
    """P4: run once, then claim hypotheses whose constants sit in an executed
    block, citing the disassembly only (V2_SPEC.md section 6). Needs the
    agent loop built with ``enable_query_graph=True``."""

    _RUN_INPUT = "61"

    def __init__(self) -> None:
        self._phase = "disassemble"
        self._handle = ""
        self._matches: list[str] | None = None

    def complete(self, messages: Sequence[Message]) -> str:
        task = _task(messages)
        addr = task["function_addr"]
        size = task["function_size"]
        if not isinstance(addr, int) or not isinstance(size, int):
            raise TypeError("scripted policy requires an integer function range")

        if self._phase == "disassemble":
            self._phase = "await_run"
            return json.dumps(
                {"action": "disassemble", "addr": addr, "count": min(256, (size + 3) // 4)}
            )
        if self._phase == "await_run":
            observation = _observation(messages)
            handle = observation.get("handle")
            if not isinstance(handle, str):
                raise RuntimeError("disassembly observation has invalid handle")
            self._handle = handle
            self._phase = "await_query"
            return json.dumps({"action": "run", "input_hex": self._RUN_INPUT})
        if self._phase == "await_query":
            self._phase = "claim"
            return json.dumps({"action": "query_graph", "query": "constants_in", "args": {}})

        if self._matches is None:
            result = _query_result(messages)
            constants = result.get("constants")
            if not isinstance(constants, list):
                raise RuntimeError("query_graph constants_in result is malformed")
            executed_values = {entry["value"] for entry in constants if entry.get("executed") is True}
            self._matches = [
                primitive for primitive, signature in _SIGNATURES.items() if signature & executed_values
            ]
        if self._matches:
            primitive = self._matches.pop(0)
            return _claim(f"p4-{primitive}", addr, primitive, [self._handle], 0.85)
        return '{"action":"finish"}'


P1Grepper = GrepperPolicy
P2Emulator = EmulatorPolicy
P3PriorGuesser = PriorGuesserPolicy
P4TraceQualifiedGrepper = TraceQualifiedGrepperPolicy

