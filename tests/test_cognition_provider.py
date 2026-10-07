from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from veraos.cognition_provider import (
    CognitionProviderError,
    provider_route_eligible,
    validate_provider,
)


def provider(kind: str = "LOCAL_MODEL") -> dict:
    return {
        "schema": "VERA_OS_COGNITION_PROVIDER_V1",
        "provider_id": "local:vera-qwen35",
        "provider_kind": kind,
        "capabilities": ["text", "reasoning"],
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


class CognitionProviderTests(unittest.TestCase):
    def test_local_model_is_only_one_supported_provider_kind(self) -> None:
        for kind in (
            "LOCAL_MODEL",
            "REMOTE_API",
            "HOSTED_SESSION",
            "LOCAL_SERVICE",
            "SPECIALIST",
        ):
            item = provider(kind)
            validate_provider(item)
            self.assertTrue(provider_route_eligible(item))

    def test_no_specific_model_or_training_repository_is_required(self) -> None:
        item = provider("REMOTE_API")
        item["provider_id"] = "hosted:any-capable-provider"
        item["transport"] = {
            "kind": "CHAT_SESSION",
            "attachment": "provider-session-binding",
        }
        validate_provider(item)
        self.assertTrue(provider_route_eligible(item))

    def test_provider_cannot_gain_browser_or_effect_authority_from_cognition(self) -> None:
        for key in (
            "identity_authority",
            "canonical_memory_write_authority",
            "protected_effect_authority",
            "browser_authority",
        ):
            item = provider()
            item["authority"][key] = True
            with self.assertRaises(CognitionProviderError):
                validate_provider(item)

    def test_only_veraos_qualification_can_admit_provider(self) -> None:
        item = provider()
        item["qualification"]["issuer"] = "thebrazenbeard/vera_model_training"
        with self.assertRaisesRegex(CognitionProviderError, "qualification issuer"):
            validate_provider(item)

    def test_nonpass_provider_must_remain_held(self) -> None:
        item = provider()
        item["qualification"]["status"] = "HOLD"
        item["admission"]["status"] = "HELD"
        validate_provider(item)
        self.assertFalse(provider_route_eligible(item))

    def test_portal_owns_route_selection(self) -> None:
        item = provider()
        item["admission"]["selector_owner"] = "thebrazenbeard/vera_model_training"
        with self.assertRaisesRegex(CognitionProviderError, "P.O.R.T.A.L."):
            validate_provider(item)


if __name__ == "__main__":
    unittest.main()
