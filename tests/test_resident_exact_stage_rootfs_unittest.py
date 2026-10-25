"""Optional real 431-file stage readback against a copied directory-rootfs.

Requires VERAOS_REAL_STAGE from an exact verified stage. Read-only stage
input, disposable copied rootfs output; not a Buildroot/guest qualification.
"""
from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verified_package_audit", ROOT / "tools/vm/Verify-VeraOSResidentFiles.py"
)
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


@unittest.skipUnless(os.getenv("VERAOS_REAL_STAGE"), "exact stage not provided")
class ExactStageTests(unittest.TestCase):
    def test_real_receipt_and_full_bytes_then_hostile_mutations(self):
        stage = Path(os.environ["VERAOS_REAL_STAGE"])
        scratch = Path(os.environ.get("VERAOS_TEST_TEMP", tempfile.gettempdir()))
        with tempfile.TemporaryDirectory(prefix="c-", dir=scratch) as temp:
            image = Path(temp) / "image"
            dest = image / "opt/veraos/components"
            shutil.copytree(stage / "components", dest)
            receipt = image / "etc/veraos/architecture" / audit.RECEIPT
            receipt.parent.mkdir(parents=True)
            shutil.copyfile(stage / audit.RECEIPT, receipt)
            rootfs = audit._rootfs("directory", image, ROOT)
            def verify():
                return audit.verify_image(stage, ROOT, rootfs)
            result = verify()
            self.assertEqual(result["resident_files_verified"], 431)
            self.assertEqual(result["stage_receipt_sha256"],
                hashlib.sha256((stage/audit.RECEIPT).read_bytes()).hexdigest())
            self.assertIs(result["guest_import_qualified"], False)
            extra = dest/"vera_mono"/"packages"/"vera_core"/"src"/"vera_core"/"stale.py"
            extra.write_bytes(b"# could shadow source bytes")
            with self.assertRaisesRegex(audit.ResidentIntegrityError,
                                        "Unexpected or missing files"):
                verify()
            extra.unlink()
            changed = dest/"vera_mono"/"packages"/"vera_core"/"src"/"vera_core"/"local_conversation.py"
            expected = changed.read_bytes()
            changed.write_bytes(expected + b"\n# unauthorized\n")
            with self.assertRaisesRegex(audit.ResidentIntegrityError,
                                        "source byte mismatch"):
                verify()
            changed.write_bytes(expected)
            receipt.write_bytes(receipt.read_bytes() + b" ")
            with self.assertRaisesRegex(audit.ResidentIntegrityError,
                                        "Embedded receipt differs"):
                verify()
