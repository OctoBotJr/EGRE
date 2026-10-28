import json
from pathlib import Path

from egre.evaluation.cli import main


def test_cli_prints_saved_evaluation(capsys, tmp_path: Path) -> None:
    path = tmp_path / "evaluation.json"
    path.write_text(
        json.dumps(
            {
                "support_truth": {
                    "entailed_true": 1,
                    "entailed_false": 0,
                    "insufficient_true": 0,
                    "insufficient_false": 0,
                },
                "views": [
                    {
                        "name": "C1",
                        "retained_claims": 1,
                        "true_claims": 1,
                        "false_claims": 0,
                        "precision": 1.0,
                        "coverage": 1.0,
                    }
                ],
                "runs": [],
            }
        )
    )

    assert main([str(path)]) == 0
    output = capsys.readouterr().out
    assert "Support x truth" in output
    assert "C1" in output
    assert "100.0%" in output
