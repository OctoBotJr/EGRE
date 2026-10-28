"""Native prototype executor with a macOS no-network sandbox."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

SANDBOX_PROFILE = "(version 1)(allow default)(deny network*)"
_INPUT = re.compile(r"(?:[0-9a-fA-F]{2})*")
_OUTPUT = re.compile(r"[0-9a-f]{8}")
_NESTED_SANDBOX_DENIAL = b"sandbox_apply: Operation not permitted"


class ExecError(RuntimeError):
    """The experiment harness could not produce a trustworthy result."""


def _execute(command: list[str], timeout: float) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(command, capture_output=True, check=False, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise ExecError(f"program timed out after {timeout:g} seconds") from exc
    except OSError as exc:
        raise ExecError(f"program could not be started: {exc}") from exc


def run_program(binary: str | os.PathLike[str], input_hex: str, timeout: float = 5) -> int:
    """Run a prototype binary and return its unsigned 32-bit hexadecimal output."""
    if _INPUT.fullmatch(input_hex) is None:
        raise ExecError("input must be even-length hexadecimal")
    if timeout <= 0:
        raise ExecError("timeout must be positive")

    program_command = [str(Path(binary)), input_hex]
    sandbox_command = ["sandbox-exec", "-p", SANDBOX_PROFILE, *program_command]
    completed = _execute(sandbox_command, timeout)
    if completed.returncode == 71 and _NESTED_SANDBOX_DENIAL in completed.stderr:
        # Some outer macOS seatbelts prohibit applying a nested sandbox.  P-02 explicitly
        # permits a direct-execution fallback for that environment; D-017 records the limit.
        completed = _execute(program_command, timeout)

    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", errors="replace").strip()
        detail = f": {stderr}" if stderr else ""
        raise ExecError(f"program exited with status {completed.returncode}{detail}")

    try:
        output = completed.stdout.decode("ascii")
    except UnicodeDecodeError as exc:
        raise ExecError("program output was not ASCII") from exc
    output = output.removesuffix("\n")
    if _OUTPUT.fullmatch(output) is None:
        raise ExecError("program output must be exactly 8 lowercase hexadecimal digits")
    return int(output, 16)
