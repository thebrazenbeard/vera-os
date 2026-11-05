"""Source-only evidence-shape tests for docs/18; never launch a model.

These tests do not authenticate model files, a host, identity, consent, or any
generated text. A structurally complete receipt is *not* a trusted receipt.
"""

from __future__ import annotations

from pathlib import Path
import re
import unittest


SCENARIO_IDS = tuple(f"P{number:02d}" for number in range(1, 13))
SCHEMA = "VERA_PERSONALITY_QUALIFICATION_V0"
FIXTURE_SET = "vera-personality-v0"
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
DOC = Path(__file__).resolve().parents[1] / "docs" / "18-vera-inference-personality-qualification.md"


class ReceiptShapeError(ValueError):
    """Source fixture has made a logically unsupported evidence claim."""


def require_receipt_shape(receipt: object) -> str:
    """Reject obvious false-success declarations; never certify real evidence."""

    if type(receipt) is not dict:
        raise ReceiptShapeError("receipt must be an exact object")
    if receipt.get("schema") != SCHEMA or receipt.get("fixture_set") != FIXTURE_SET:
        raise ReceiptShapeError("unsupported fixture receipt")
    if receipt.get("scenario_id") not in SCENARIO_IDS:
        raise ReceiptShapeError("unknown synthetic scenario")
    if receipt.get("protected_effect_calls") != 0 or type(receipt.get("protected_effect_calls")) is not int:
        raise ReceiptShapeError("protected effect occurred or was not counted")
    if type(receipt.get("runtime_identity_authority_verified")) is not bool:
        raise ReceiptShapeError("identity evidence must be explicit")
    if type(receipt.get("synthetic_consent_recorded")) is not bool:
        raise ReceiptShapeError("consent evidence must be explicit")
    if type(receipt.get("host_probed")) is not bool:
        raise ReceiptShapeError("host observation class must be explicit")
    source_class = receipt.get("source_class")
    if source_class == "SOURCE_FIXTURE":
        if (receipt.get("outcome") != "HOLD"
                or receipt.get("real_generated_token_count") is not None
                or receipt["host_probed"]
                or receipt["runtime_identity_authority_verified"]):
            raise ReceiptShapeError("source fixture was promoted to runtime evidence")
        return "SOURCE_FIXTURE_SHAPE_ONLY"
    if source_class == "REAL_INFERENCE":
        for field in ("model_sha256", "gguf_sha256", "backend_commit",
                      "prompt_sha256", "response_sha256"):
            value = receipt.get(field)
            if (type(value) is not str or
                    (HEX64.fullmatch(value) is None if field != "backend_commit"
                     else re.fullmatch(r"[0-9a-f]{40}", value) is None)):
                raise ReceiptShapeError(f"exact {field} evidence required")
        count = receipt.get("real_generated_token_count")
        if type(count) is not int or not 1 <= count <= 128 or not receipt["host_probed"]:
            raise ReceiptShapeError("physical nonempty token/host observation missing")
        if receipt.get("outcome") not in {"HOLD", "REVIEW_REQUIRED"}:
            raise ReceiptShapeError("shape-only inspection cannot award PASS")
        return "REAL_INFERENCE_CLAIM_SHAPE_ONLY_UNVERIFIED"
    raise ReceiptShapeError("unrecognized evidence class")


def fixture_receipt(**replacements: object) -> dict:
    example = {
        "schema": SCHEMA,
        "fixture_set": FIXTURE_SET,
        "scenario_id": "P02",
        "source_class": "SOURCE_FIXTURE",
        "outcome": "HOLD",
        "real_generated_token_count": None,
        "host_probed": False,
        "protected_effect_calls": 0,
        "runtime_identity_authority_verified": False,
        "synthetic_consent_recorded": False,
    }
    example.update(replacements)
    return example


class PersonalityFixtureContractTests(unittest.TestCase):
    def test_document_has_exact_twelve_distinct_synthetic_cases(self):
        source = DOC.read_text(encoding="utf-8")
        marked_ids = re.findall(r"^\| \*\*(P\d{2}) —", source, re.MULTILINE)
        self.assertEqual(marked_ids, list(SCENARIO_IDS))
        self.assertIn("TEST-OWNER-001", source)
        self.assertIn("no personal chats", source)

    def test_fixture_is_only_fixture_and_cannot_pass(self):
        self.assertEqual(require_receipt_shape(fixture_receipt()), "SOURCE_FIXTURE_SHAPE_ONLY")
        for invalid in (
            {"outcome": "PASS"},
            {"real_generated_token_count": 12},
            {"host_probed": True},
            {"runtime_identity_authority_verified": True},
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ReceiptShapeError):
                require_receipt_shape(fixture_receipt(**invalid))

    def test_effect_and_consent_types_are_not_truthy_shortcuts(self):
        for invalid in (
            {"protected_effect_calls": 1},
            {"protected_effect_calls": False},
            {"synthetic_consent_recorded": "yes"},
            {"runtime_identity_authority_verified": "no"},
            {"host_probed": 0},
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ReceiptShapeError):
                require_receipt_shape(fixture_receipt(**invalid))

    def test_real_inference_claim_requires_actual_evidence_fields(self):
        incomplete = fixture_receipt(source_class="REAL_INFERENCE", host_probed=True,
                                     real_generated_token_count=1)
        with self.assertRaises(ReceiptShapeError):
            require_receipt_shape(incomplete)
        complete_claim = dict(incomplete, model_sha256="a" * 64, gguf_sha256="b" * 64,
                              backend_commit="c" * 40, prompt_sha256="d" * 64,
                              response_sha256="e" * 64, outcome="REVIEW_REQUIRED")
        self.assertEqual(
            require_receipt_shape(complete_claim),
            "REAL_INFERENCE_CLAIM_SHAPE_ONLY_UNVERIFIED",
        )
        for invalid in ({"real_generated_token_count": 0},
                        {"real_generated_token_count": 129},
                        {"gguf_sha256": "unknown"},
                        {"outcome": "PASS"}):
            with self.subTest(invalid=invalid), self.assertRaises(ReceiptShapeError):
                require_receipt_shape(dict(complete_claim, **invalid))


if __name__ == "__main__":
    unittest.main()
