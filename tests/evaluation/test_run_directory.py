import json
from pathlib import Path

from egre.evaluation.cli import main


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
