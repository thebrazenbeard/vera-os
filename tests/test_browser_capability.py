from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from veraos.browser_capability import (
    BrowserCapabilityError,
    validate_browser_grant,
)


def grant() -> dict:
    return {
        "schema": "VERA_OS_BROWSER_CAPABILITY_GRANT_V1",
        "grant_id": "browser-grant-1",
        "requester": "vera-session:test",
        "mode": "AUTOMATION",
        "network": {
            "scope": "GENERAL_WEB",
            "allowed_schemes": ["https"],
        },
        "profile": {
            "persistence": "EPHEMERAL",
            "credential_access": False,
        },
        "downloads": {
            "mode": "GOVERNED_DIRECTORY",
            "path": "/var/lib/vera-browser/downloads",
        },
        "effects": {
            "protected_effect_authority": False,
            "credential_mutation_authority": False,
            "protected_actions_require_effect_broker": True,
        },
    }


class BrowserCapabilityTests(unittest.TestCase):
    def test_browser_grant_is_separate_from_cognition_provider(self) -> None:
        item = grant()
        validate_browser_grant(item)
        self.assertNotIn("provider_id", item)

    def test_browser_grant_cannot_confer_protected_effect_authority(self) -> None:
        item = grant()
        item["effects"]["protected_effect_authority"] = True
        with self.assertRaises(BrowserCapabilityError):
            validate_browser_grant(item)

    def test_browser_grant_cannot_confer_credential_mutation_authority(self) -> None:
        item = grant()
        item["effects"]["credential_mutation_authority"] = True
        with self.assertRaises(BrowserCapabilityError):
            validate_browser_grant(item)

    def test_persistent_profile_requires_no_ambient_credentials(self) -> None:
        item = grant()
        item["profile"]["persistence"] = "GOVERNED_PERSISTENT"
        item["profile"]["credential_access"] = True
        with self.assertRaisesRegex(BrowserCapabilityError, "credential"):
            validate_browser_grant(item)

    def test_http_is_not_implicitly_allowed(self) -> None:
        item = grant()
        item["network"]["allowed_schemes"] = ["https", "file"]
        with self.assertRaisesRegex(BrowserCapabilityError, "scheme"):
            validate_browser_grant(item)

    def test_buildroot_browser_profile_provisions_real_browser_engine(self) -> None:
        core = (
            ROOT / "buildroot" / "configs" / "veraos_x86_64_defconfig"
        ).read_text(encoding="utf-8")
        text = (
            ROOT / "buildroot" / "configs" / "veraos_x86_64_browser_defconfig"
        ).read_text(encoding="utf-8")
        self.assertNotIn("BR2_PACKAGE_WPEWEBKIT=y", core)
        self.assertNotIn("BR2_PACKAGE_COG=y", core)
        self.assertIn("BR2_PACKAGE_WPEWEBKIT=y", text)
        self.assertIn("BR2_PACKAGE_WPEWEBKIT_SANDBOX=y", text)
        self.assertIn("BR2_PACKAGE_WPEWEBKIT_WEBDRIVER=y", text)
        self.assertIn("BR2_PACKAGE_COG=y", text)
        self.assertIn("BR2_PACKAGE_COG_PLATFORM_DRM=y", text)


if __name__ == "__main__":
    unittest.main()
