from egre.evaluation.rescoring import is_rescorable, ledger_from_document, rescore_document
from egre.runner.refs import REFERENCES


def _claim_doc(claim_id: str, primitive: str, cited_handles: list[str]) -> dict[str, object]:
    return {
        "id": claim_id,
        "function_addr": 0x1000,
        "primitive": primitive,
        "cited_handles": cited_handles,
        "confidence": 0.9,
    }


def _ledger_entry(
    handle: str,
    kind: str,
    *,
    args: dict[str, object],
    payload: object,
    facts: list[int] | None = None,
) -> dict[str, object]:
    return {
        "handle": handle,
        "kind": kind,
        "tool": kind if kind != "disasm" else "disassemble",
        "args": args,
        "anchor": {"start": 0x1000, "end": 0x1010},
        "payload": payload,
        "facts": facts or [],
        "ts": "2026-01-01T00:00:00+00:00",
    }


def test_ledger_from_document_reproduces_original_handles() -> None:
    document = {
        "ledger": [
            _ledger_entry("obs-000001", "disasm", args={"addr": 0x1000, "count": 4}, payload="x"),
            _ledger_entry("obs-000002", "run", args={"input_hex": "61"}, payload=1),
        ]
    }

    ledger = ledger_from_document(document)

    assert [observation.handle for observation in ledger.all()] == ["obs-000001", "obs-000002"]
    assert ledger.get("obs-000001").kind == "disasm"
    assert ledger.get("obs-000002").payload == 1


def test_rescore_document_s0_is_read_not_recomputed_s1_is_fresh() -> None:
    document = {
        "claims": [_claim_doc("c1", "fnv1a32", ["obs-000001"])],
        "ledger": [
            _ledger_entry(
                "obs-000001",
                "disasm",
                args={"addr": 0x1000, "count": 4},
                payload="shared",
                facts=[0x811C9DC5, 0xEDB88320],
            )
        ],
        "outcome": {
            "policy": "LLM",
            "program": "fnv1a_crcdecoy",
            "truth": "fnv1a32",
            "claims": [
                {
                    "claim_id": "c1",
                    "primitive": "fnv1a32",
                    "support": "entailed",
                    "reason": None,
                    "verdict": "confirmed",
                    "status": "verified",
                    "support_gap": False,
                    "is_true": True,
                }
            ],
        },
    }

    (rescored,) = rescore_document(document)

    assert rescored.claim_id == "c1"
    assert rescored.s0_entailed is True
    assert rescored.s1_tier == "contested"
    assert rescored.is_true is True


def test_rescore_document_behavioral_run_evidence() -> None:
    data = b"abc"
    document = {
        "claims": [_claim_doc("c1", "crc32", ["obs-000001"])],
        "ledger": [
            _ledger_entry(
                "obs-000001", "run", args={"input_hex": data.hex()}, payload=REFERENCES["crc32"](data)
            )
        ],
        "outcome": {
            "policy": "LLM",
            "program": "crc32_clean",
            "truth": "crc32",
            "claims": [
                {
                    "claim_id": "c1",
                    "primitive": "crc32",
                    "support": "insufficient",
                    "reason": "NO_SIGNATURE_EVIDENCE",
                    "verdict": "confirmed",
                    "status": "verified",
                    "support_gap": True,
                    "is_true": True,
                }
            ],
        },
    }

    (rescored,) = rescore_document(document)

    assert rescored.s0_entailed is False
    assert rescored.s1_tier == "behavioral"


def test_is_rescorable_requires_both_claims_and_ledger() -> None:
    assert is_rescorable({"claims": [], "ledger": []}) is True
    assert is_rescorable({"claims": []}) is False
    assert is_rescorable({}) is False
