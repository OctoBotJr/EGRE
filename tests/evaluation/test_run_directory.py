import json
import re
from pathlib import Path

from egre.evaluation.cli import main

ROOT = Path(__file__).resolve().parents[2]


def _run_document(
    *, program: str, invalid_steps: int, claims: list[dict[str, object]]
) -> dict[str, object]:
    return {
        "state": "completed",
        "program": program,
        "invalid_steps": invalid_steps,
        "outcome": {
            "policy": "LLM",
            "program": program,
            "truth": "crc32",
            "claims": claims,
        },
    }


def _claim(
    claim_id: str,
    primitive: str,
    *,
    support: str,
    reason: str | None,
    status: str,
    is_true: bool,
) -> dict[str, object]:
    return {
        "claim_id": claim_id,
        "primitive": primitive,
        "support": support,
        "reason": reason,
        "verdict": "confirmed" if is_true else "refuted",
        "status": status,
        "support_gap": support == "insufficient" and status == "verified",
        "is_true": is_true,
    }


def test_evaluation_cli_reads_run_directory_and_prints_run_totals(
    capsys, tmp_path: Path
) -> None:
    true_claim = {
        "claim_id": "c1",
        "primitive": "crc32",
        "support": "entailed",
        "reason": None,
        "verdict": "confirmed",
        "status": "verified",
        "support_gap": False,
        "is_true": True,
    }
    (tmp_path / "a.json").write_text(
        json.dumps(_run_document(program="crc32_clean", invalid_steps=2, claims=[true_claim]))
    )
    (tmp_path / "b.json").write_text(
        json.dumps(_run_document(program="crc32_obfpoly", invalid_steps=1, claims=[]))
    )

    assert main([str(tmp_path)]) == 0
    output = capsys.readouterr().out
    assert "Support x truth" in output
    assert "Total claims: 1" in output
    assert "Zero-claim runs: 1" in output
    assert "Total invalid steps: 3" in output


def test_evaluation_cli_prints_breakdown_and_deduplicated_views(
    capsys, tmp_path: Path
) -> None:
    duplicate_claims = [
        _claim(
            "c1",
            "crc32",
            support="insufficient",
            reason="NO_CITATION",
            status="verified",
            is_true=True,
        ),
        _claim(
            "c2",
            "crc32",
            support="entailed",
            reason=None,
            status="verified",
            is_true=True,
        ),
        _claim(
            "c3",
            "adler32",
            support="insufficient",
            reason="NO_SIGNATURE_EVIDENCE",
            status="refuted",
            is_true=False,
        ),
    ]
    beta_claims = [
        _claim(
            "c4",
            "fnv1a32",
            support="entailed",
            reason=None,
            status="verified",
            is_true=True,
        )
    ]
    (tmp_path / "alpha-1.json").write_text(
        json.dumps(_run_document(program="alpha", invalid_steps=2, claims=duplicate_claims))
    )
    (tmp_path / "alpha-2.json").write_text(
        json.dumps(_run_document(program="alpha", invalid_steps=1, claims=[]))
    )
    (tmp_path / "beta-1.json").write_text(
        json.dumps(_run_document(program="beta", invalid_steps=4, claims=beta_claims))
    )

    assert main([str(tmp_path)]) == 0
    output = capsys.readouterr().out
    assert "Insufficient-support reasons\nreason                 count" in output
    assert "NO_CITATION                1" in output
    assert "NO_SIGNATURE_EVIDENCE      1" in output
    assert "alpha       2       3     2      1         1             2           1        3" in output
    assert "beta        1       1     1      0         1             0           0        4" in output
    assert "Runs with duplicate (run, primitive) claims: 1" in output
    assert "Deduplicated gate views (first claim per run and primitive)" in output
    assert "C1         3     2      1      66.7%     66.7%" in output
    assert "C2         1     1      0     100.0%     33.3%" in output
    assert "C3         2     2      0     100.0%     66.7%" in output


def test_evaluation_cli_omits_s1_rescoring_when_run_files_lack_ledger_and_claims(
    capsys, tmp_path: Path
) -> None:
    (tmp_path / "a.json").write_text(
        json.dumps(_run_document(program="crc32_clean", invalid_steps=0, claims=[]))
    )

    assert main([str(tmp_path)]) == 0
    output = capsys.readouterr().out

    assert "S1 re-scoring" not in output


def test_evaluation_cli_prints_s1_rescoring_when_run_files_carry_claims_and_ledger(
    capsys, tmp_path: Path
) -> None:
    document = _run_document(program="crc32_clean", invalid_steps=0, claims=[])
    document["claims"] = [
        {
            "id": "c1",
            "function_addr": 0x1000,
            "primitive": "crc32",
            "cited_handles": ["obs-000001"],
            "confidence": 0.9,
        }
    ]
    document["ledger"] = [
        {
            "handle": "obs-000001",
            "kind": "disasm",
            "tool": "disassemble",
            "args": {"addr": 0x1000, "count": 4},
            "anchor": {"start": 0x1000, "end": 0x1010},
            "payload": "x",
            "facts": [0xEDB88320],
            "ts": "2026-01-01T00:00:00+00:00",
        }
    ]
    document["outcome"]["claims"] = [
        {
            "claim_id": "c1",
            "primitive": "crc32",
            "support": "entailed",
            "reason": None,
            "verdict": "confirmed",
            "status": "verified",
            "support_gap": False,
            "is_true": True,
        }
    ]
    (tmp_path / "a.json").write_text(json.dumps(document))

    assert main([str(tmp_path)]) == 0
    output = capsys.readouterr().out

    assert "S1 re-scoring" in output
    assert "structural" in output


def test_s1_rescoring_of_the_frozen_r0_run_closes_part_of_the_s0_blind_spot(capsys) -> None:
    frozen = ROOT / "runs" / "ollama-qwen3.5-4b-final"

    assert main([str(frozen)]) == 0
    output = capsys.readouterr().out

    assert "S1 re-scoring" in output
    assert "behavioral        2      0" in output
    assert "structural        4      0" in output
    assert "contested         1      0" in output
    assert "none             16      2" in output
    assert "contradicted      0      0" in output
    match = re.search(r"S0 entailed but S1 <= contested.*: (\d+)", output)
    assert match is not None
    # Of C2's 6 S0-entailed claims, one is only "contested" under S1's
    # contrastive rules (a rival's signature constant is also present).
    assert int(match.group(1)) == 1
