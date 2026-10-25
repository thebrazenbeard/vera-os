"""Offline rootfs checks for every byte of Vera's staged resident source."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "resident_file_audit", ROOT / "tools/vm/Verify-VeraOSResidentFiles.py"
)
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


class FakeRootfs:
    def __init__(self, files):
        self.files = files

    def read(self, path):
        return self.files.get(path)

    def component_files(self):
        return {
            path.removeprefix("/opt/veraos/")
            for path in self.files
            if path.startswith("/opt/veraos/components/")
        }


class AllResidentFilesTest(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.root = Path(self.t.name)
        self.stage = self.root / "stage"
        self.stage.mkdir()
        self.bytes = {}
        components = []
        for repo, component in audit.EXPECTED_COMPONENTS.items():
            files = []
            for idx in range(2):
                rel = f"components/{component}/src/{component}/sample{idx}.py"
                source = f"# {repo}: {idx}\n".encode("utf-8")
                sha = hashlib.sha256(source).hexdigest()
                files.append({"path": rel, "sha256": sha})
                self.bytes["/opt/veraos/" + rel] = source
            components.append({"repository": repo, "files": files, "file_count": 2})
        self.receipt = {
            "schema": audit.RECEIPT.replace(".json", ""),
            "components": components,
            "authority": False,
        }
        self.receipt_path = self.stage / audit.RECEIPT
        self.write_receipt()
        self.readback = FakeRootfs(self.bytes)

    def write_receipt(self):
        data = json.dumps(self.receipt, sort_keys=True).encode("utf-8")
        self.receipt_path.write_bytes(data)
        self.bytes[audit.ROOTFS_RECEIPT] = data

    def verify(self):
        with mock.patch.object(audit, "_verify_stage") as require:
            result = audit.verify_image(self.stage, self.root, self.readback)
            require.assert_called_once_with(self.stage, self.root)
            return result

    def test_four_components_and_every_file_hash_check(self):
        result = self.verify()
        self.assertEqual(result["resident_repository_count"], 4)
        self.assertEqual(result["resident_files_verified"], 8)
        self.assertEqual(result["status"], "ALL_PINNED_SOURCE_FILES_IMAGE_BYTE_MATCH_NOT_RUNTIME_QUALIFIED")
        self.assertFalse(result["guest_import_qualified"])
        self.assertFalse(result["offline_model_route_qualified"])
        self.assertFalse(result["protected_effect_authority"])

    def test_modified_file_fails_even_when_present(self):
        path = next(k for k in self.bytes if k.endswith(".py"))
        self.bytes[path] = b"modified bytes\n"
        with self.assertRaisesRegex(audit.ResidentIntegrityError, "source byte mismatch"):
            self.verify()

    def test_missing_file_fails(self):
        path = next(k for k in self.bytes if k.endswith(".py"))
        del self.bytes[path]
        with self.assertRaisesRegex(audit.ResidentIntegrityError, "source byte mismatch"):
            self.verify()

    def test_copied_rootfs_rejects_stale_extra_source_file(self):
        image = self.root / "rootfs"
        for virtual_path, body in self.bytes.items():
            target = image / virtual_path.lstrip("/")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(body)
        self.readback = audit._rootfs("directory", image, ROOT)
        self.assertEqual(self.verify()["resident_files_verified"], 8)
        orphan = image / "opt/veraos/components/vera_mono/src/vera_mono/old.py"
        orphan.write_bytes(b"# stale import from previous image\\n")
        with self.assertRaisesRegex(audit.ResidentIntegrityError, "Unexpected or missing files"):
            self.verify()

    def test_ext2_image_extra_source_file_must_fail_closed(self):
        class ImageReader(FakeRootfs):
            def component_files(self):
                return {
                    path.lstrip("/").replace("opt/veraos/", "", 1)
                    for path in self.files if path.startswith("/opt/veraos/components/")
                } | {"components/vera_mono/old_shadow.py"}
        self.readback = ImageReader(self.bytes)
        with self.assertRaisesRegex(audit.ResidentIntegrityError, "Unexpected or missing files"):
            self.verify()

    def test_ext2_image_without_enumerator_fails_closed(self):
        class ImageReader(FakeRootfs):
            component_files = None
        self.readback = ImageReader(self.bytes)
        with self.assertRaisesRegex(audit.ResidentIntegrityError, "enumerat"):
            self.verify()

    def test_wrong_embedded_receipt_fails(self):
        self.bytes[audit.ROOTFS_RECEIPT] += b"x"
        with self.assertRaisesRegex(audit.ResidentIntegrityError, "Embedded receipt differs"):
            self.verify()

    def test_wrong_source_stage_receipt_fails(self):
        self.receipt_path.write_bytes(self.receipt_path.read_bytes() + b"!")
        with self.assertRaisesRegex(audit.ResidentIntegrityError, "Embedded receipt differs"):
            self.verify()

    def test_duplicate_file_receipt_fails(self):
        row = self.receipt["components"][0]
        row["files"][1] = dict(row["files"][0])
        self.write_receipt()
        with self.assertRaisesRegex(audit.ResidentIntegrityError, "duplicate"):
            self.verify()

    def test_unsafe_path_fails(self):
        row = self.receipt["components"][0]
        row["files"][0]["path"] = "components/vera_mono/../not-allowed.py"
        self.write_receipt()
        with self.assertRaisesRegex(audit.ResidentIntegrityError, "Unsafe"):
            self.verify()

    def test_nonverified_stage_fails_closed(self):
        with mock.patch.object(audit, "_verify_stage", side_effect=ValueError("unverified stage")):
            with self.assertRaisesRegex(ValueError, "unverified stage"):
                audit.verify_image(self.stage, self.root, self.readback)

    def test_duplicate_repository_fails(self):
        self.receipt["components"][1] = self.receipt["components"][0]
        self.write_receipt()
        with self.assertRaisesRegex(audit.ResidentIntegrityError, "Duplicate"):
            self.verify()


if __name__ == "__main__":
    unittest.main()
