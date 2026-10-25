"""Static custody invariants for the PowerShell VM qualification wrapper.

Runtime Docker/QEMU qualification is a separate installed-system gate.
"""
from pathlib import Path
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "tools/vm/Test-VeraOSVm.ps1"


class VmQualificationCustodyTests(unittest.TestCase):
    def test_prior_receipts_and_logs_are_not_deleted_or_overwritten(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("Remove-Item $overlay", source)
        self.assertNotIn("Remove-Item $stdout,$stderr", source)
        self.assertNotIn('Join-Path $artifacts "veraos-vm-qualification.json"', source)
        self.assertIn("[IO.FileMode]::CreateNew", source)
        self.assertIn("$receiptFile.Flush($true)", source)

    def test_containers_are_never_removed_by_ambient_name(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("docker ps -aq --filter", source)
        self.assertNotIn("docker rm -f", source)
        self.assertNotIn('docker ps -q --filter', source)
        self.assertIn('"--cidfile", $cidPath', source)
        self.assertIn("$ownedContainerId", source)

    def test_each_invocation_owns_distinct_artifacts_and_pinned_runner(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("[guid]::NewGuid()", source)
        self.assertIn("$runLogs", source)
        self.assertIn("$runnerImageId", source)
        self.assertIn("runner_image_source_attestation_qualified = $false", source)
        self.assertIn("host_log_acl_qualified = $false", source)
        self.assertIn("Assert-NoLinkedAncestor", source)
        self.assertIn('source=$runLogs,target=/logs', source)
        self.assertNotIn('source=$logs,target=/logs', source)
        self.assertIn('"--network", "none"', source)
        self.assertIn('"--rm", "--network", "none"', source)
        self.assertIn('docker run --rm --network none $runnerImageId', source)

    def test_guest_liveness_and_panic_are_fenced(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("$dwellQualified", source)
        self.assertIn("TotalSeconds -ge 5", source)
        self.assertIn("Kernel panic|Oops:|BUG: unable to handle kernel", source)
        self.assertIn("if ($process.HasExited) { break }", source)
        self.assertIn("$finished = $process.WaitForExit(5000)", source)
        self.assertIn('throw "VM qualification Docker process remained live after owned cleanup"', source)
        self.assertIn("if (-not $ownedContainerId -or -not $bootMarker", source)
        self.assertIn("stdout_sha256 = $firstBoot.stdout_sha256", source)
        self.assertIn("stderr_sha256 = $secondBoot.stderr_sha256", source)


if __name__ == "__main__":
    unittest.main()
