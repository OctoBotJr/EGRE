import json
import os
from pathlib import Path

import pytest

from egre.runner.executor import ExecError, run_program
from egre.runner.refs import REFERENCE_INPUTS, REFERENCES
from egre.runner.verify import verify_claim

pytestmark = pytest.mark.toolchain

ROOT = Path(__file__).resolve().parents[2]
PRIMITIVES = frozenset({"crc32", "fnv1a32", "adler32", "djb2"})


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text())


def test_references_match_independent_vectors() -> None:
    vectors = _load_json(ROOT / "corpus" / "reference_vectors.json")
    inputs_hex = vectors["inputs_hex"]
    expected = vectors["expected"]

    assert isinstance(inputs_hex, list)
    assert tuple(inputs_hex) == REFERENCE_INPUTS
    assert isinstance(expected, dict)
    assert set(REFERENCES) == PRIMITIVES
    for primitive, reference in REFERENCES.items():
        assert [f"{reference(bytes.fromhex(value)):08x}" for value in inputs_hex] == expected[
            primitive
        ]


@pytest.mark.parametrize(
    "truth_path", sorted((ROOT / "corpus" / "truth").glob("*.json")), ids=lambda path: path.stem
)
def test_verify_claim_confirms_truth_and_refutes_wrong_primitives(truth_path: Path) -> None:
    truth = _load_json(truth_path)
    program = truth["program"]
    true_primitive = truth["primitive"]
    assert isinstance(program, str)
    assert isinstance(true_primitive, str)

    binary = ROOT / "corpus" / "bin" / program
    confirmed = verify_claim(binary, true_primitive)
    assert confirmed.verdict == "confirmed"
    assert len(confirmed.evidence) == len(REFERENCE_INPUTS)

    for wrong_primitive in PRIMITIVES - {true_primitive}:
        refuted = verify_claim(binary, wrong_primitive)
        assert refuted.verdict == "refuted"
        assert any(item.actual != item.expected for item in refuted.evidence)


def test_bad_binary_is_inconclusive() -> None:
    verdict = verify_claim(ROOT / "corpus" / "bin" / "does-not-exist", "crc32")

    assert verdict.verdict == "inconclusive"
    assert verdict.evidence[0].error is not None


def test_harness_failure_overrides_an_observed_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_after_mismatches(_binary: object, input_hex: str) -> int:
        if input_hex == REFERENCE_INPUTS[-1]:
            raise ExecError("synthetic late harness failure")
        return 0

    monkeypatch.setattr("egre.runner.verify.run_program", fail_after_mismatches)

    verdict = verify_claim("unused", "crc32")

    assert any(item.actual != item.expected for item in verdict.evidence if item.actual is not None)
    assert verdict.evidence[-1].error == "synthetic late harness failure"
    assert verdict.verdict == "inconclusive"


def test_unknown_primitive_is_inconclusive() -> None:
    verdict = verify_claim(ROOT / "corpus" / "bin" / "crc32_clean", "other")

    assert verdict.verdict == "inconclusive"
    assert verdict.evidence[0].error == "unknown primitive: other"


def test_executor_blocks_network(tmp_path: Path) -> None:
    probe = tmp_path / "network-probe"
    probe.write_text(
        "#!/bin/sh\n"
        "set -eu\n"
        "/usr/bin/curl -sS -m 2 -o /dev/null https://example.com\n"
        "printf '00000000\\n'\n"
    )
    os.chmod(probe, 0o755)

    with pytest.raises(ExecError):
        run_program(probe, "")


def test_executor_rejects_malformed_inputs_and_outputs(tmp_path: Path) -> None:
    malformed = tmp_path / "malformed"
    malformed.write_text("#!/bin/sh\nprintf 'not-a-u32\\n'\n")
    os.chmod(malformed, 0o755)

    with pytest.raises(ExecError, match="even-length hexadecimal"):
        run_program(malformed, "0")
    with pytest.raises(ExecError, match="8 lowercase hexadecimal"):
        run_program(malformed, "00")

    padded = tmp_path / "padded"
    padded.write_text("#!/bin/sh\nprintf ' 00000000 \\n'\n")
    os.chmod(padded, 0o755)
    with pytest.raises(ExecError, match="8 lowercase hexadecimal"):
        run_program(padded, "00")
