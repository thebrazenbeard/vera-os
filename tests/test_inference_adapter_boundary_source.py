"""Bounded source-only inference-contract checks; no socket/model/host I/O.

These characterize the *accepted source surfaces*, not an authenticated
backend, independent artifact custody, persistent identity or integration.
If a source seam changes, review the new contract rather than weakening gates.
"""

from __future__ import annotations

import inspect
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from veraos.cognition_provider import (  # noqa: E402
    CognitionProviderError,
    provider_route_eligible,
    validate_provider,
)
from veraos.native_cognition import admit_local_text_route  # noqa: E402
from veraos.personality_eval import (  # noqa: E402
    SyntheticObservation,
    score_synthetic_observation,
)
from veraos.virtio_model import MODEL as HISTORICAL_VIRTIO_MODEL  # noqa: E402


def shape_only_provider() -> dict:
    """Synthetic, declared-PASS data; never a signed route admission receipt."""
    return {
        "schema": "VERA_OS_COGNITION_PROVIDER_V1",
        "provider_id": "fixture:local-replaceable-model",
        "provider_kind": "LOCAL_MODEL",
        "capabilities": ["text"],
        "transport": {
            "kind": "OPENAI_COMPATIBLE_HTTP",
            "attachment": "http://127.0.0.1:5001/v1",
        },
        "qualification": {
            "status": "PASS",
            "issuer": "thebrazenbeard/vera-os",
            "subject_sha256": "1" * 64,
            "suite_sha256": "2" * 64,
        },
        "authority": {
            "identity_authority": False,
            "canonical_memory_write_authority": False,
            "protected_effect_authority": False,
            "browser_authority": False,
        },
        "admission": {
            "status": "VERAOS_ROUTE_ELIGIBLE",
            "route_class": "COGNITION_ONLY",
            "selector_owner": "thebrazenbeard/portal",
        },
    }


class InferenceBoundarySourceTests(unittest.TestCase):
    def test_shape_validator_rejects_all_four_authority_escalations(self):
        for key in (
            "identity_authority", "canonical_memory_write_authority",
            "protected_effect_authority", "browser_authority",
        ):
            with self.subTest(key=key):
                descriptor = shape_only_provider()
                descriptor["authority"][key] = True
                with self.assertRaises(CognitionProviderError):
                    validate_provider(descriptor)

    def test_shape_pass_is_not_cryptographic_issuer_qualification(self):
        descriptor = shape_only_provider()
        # Current source recognizes only *declared* schema/issuer/hash shapes.
        # This positive characterization is deliberately NOT an admission
        # test and must not be rebranded as trust or model execution evidence.
        validate_provider(descriptor)
        self.assertTrue(provider_route_eligible(descriptor))
        self.assertEqual(descriptor["authority"]["identity_authority"], False)
        self.assertNotIn("signature", descriptor["qualification"])
        self.assertNotIn("host_owned_verifier", descriptor["qualification"])

    def test_held_or_spoofed_selector_remains_unavailable(self):
        held = shape_only_provider()
        held["qualification"]["status"] = "HOLD"
        held["admission"]["status"] = "HELD"
        validate_provider(held)
        self.assertFalse(provider_route_eligible(held))

        spoof = shape_only_provider()
        spoof["admission"]["selector_owner"] = "thebrazenbeard/model-training"
        with self.assertRaises(CognitionProviderError):
            validate_provider(spoof)

    def test_provider_descriptor_replacement_never_grants_identity_flags(self):
        first = shape_only_provider()
        second = shape_only_provider()
        second["provider_id"] = "fixture:alternate-model"
        second["transport"]["attachment"] = "http://127.0.0.1:6550/v1"
        for descriptor in (first, second):
            validate_provider(descriptor)
            self.assertTrue(all(value is False for value in descriptor["authority"].values()))
        self.assertNotEqual(first["provider_id"], second["provider_id"])
        # This only proves two data shapes carry no authority fields. It
        # cannot verify real identity/state continuity across a model swap.

    def test_optional_native_route_has_no_host_owned_issuer_parameter(self):
        signature = inspect.signature(admit_local_text_route)
        self.assertIn("provider", signature.parameters)
        self.assertIn("base_url", signature.parameters)
        self.assertNotIn("trusted_issuer", signature.parameters)
        self.assertNotIn("host_authenticator", signature.parameters)
        source = inspect.getsource(admit_local_text_route)
        self.assertIn("Caller is responsible for authenticating", source)
        self.assertIn("ToolRegistry(store)", source)
        self.assertIn("max_autonomous_turns_per_run=0", source)
        # Reading the implementation is a SOURCE check, not a black-box
        # confirmation that all callers/hosts enforce trusted issuer custody.

    def test_historical_virtio_model_cannot_be_relabelled_qwen35(self):
        self.assertEqual(HISTORICAL_VIRTIO_MODEL, "qwen3:4b-instruct")
        self.assertNotEqual(HISTORICAL_VIRTIO_MODEL, "Qwen/Qwen3.5-4B")

    def test_personality_source_fixtures_are_never_real_inference(self):
        for response in ("I am Vera.", "birch", "No action was taken."):
            with self.subTest(response=response):
                result = score_synthetic_observation(SyntheticObservation(
                    "P01", response,
                ))
                self.assertEqual(result.source_class, "SOURCE_FIXTURE")
                self.assertEqual(result.outcome, "HOLD")
                self.assertIn("unannotated_identity_or_memory_claims", result.unresolved)

    def test_document_binds_exact_owner_sources_and_never_claims_release(self):
        doc = (ROOT / "docs" / "24-inference-adapter-boundary.md").read_text(encoding="utf-8")
        for source_pin in (
            "31b66b6ff317eb981c4bd8fcc4ae6e5db1d21adf",
            "db7243915c0089310bb4ea986677c105b9ba4c0a",
            "2cf4c42525998cf298e465f294fb45c4624e1a7c",
            "4c02f06e3c7fcccec3c681cb94cc087f1049235d",
            "UNVERIFIED_GENERATED_TEXT_V0",
            "SOURCE_FIXTURE/HOLD",
            "D:\\VERA",
        ):
            with self.subTest(pin=source_pin):
                self.assertIn(source_pin, doc)
        self.assertIn("$0", doc)
        self.assertIn("no new adapter activation", doc)


if __name__ == "__main__":
    unittest.main()
