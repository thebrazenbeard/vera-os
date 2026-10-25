#!/usr/bin/env python3
"""Two cold boots of one disposable VeraOS resident QEMU overlay.

Research qualification only. No physical disks, host guest-network bridge,
model admission, or production service activation. Requires an already built
image and QEMU Docker runner; never builds, downloads or installs anything.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid


BUILDROOT_COMMIT = "d030e36bbc9669230c015be971b14b6e062cfdde"
EXPECTED_SOURCE_HEAD = "79e9258bf5bb5fa993a98966fcd81260ea0c4c92"
TRUSTED_STAGE_VERIFIER_BLOB = "64395340a7cd9d45b016c770092544b7566f303c"
SHA40 = re.compile(r"[0-9a-f]{40}\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
IMAGE_ID = re.compile(r"sha256:[0-9a-f]{64}\Z")
BOOT_CONSOLE = "root=/dev/vda rw console=ttyS0,115200 init=/sbin/vera-init"
RESIDENT_MARKER = "VERAOS_RESIDENT_COMPONENTS_COMPOSED_V1"
PANIC_MARKERS = ("Kernel panic", "Oops:", "BUG: unable to handle kernel")


class QualificationError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise QualificationError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_build(artifacts: Path, expected_head: str) -> dict:
    require(SHA40.fullmatch(expected_head) is not None, "invalid exact source HEAD")
    require(expected_head == EXPECTED_SOURCE_HEAD, "unreviewed image source HEAD")
    result_path = artifacts / "veraos-build-result.json"
    require(result_path.is_file(), "build receipt missing")
    result = json.loads(result_path.read_text(encoding="utf-8-sig"))
    require(result.get("Schema") == "VERA_OS_BUILDROOT_BUILD_RESULT_V1", "wrong build receipt schema")
    require(result.get("SourceHead") == expected_head, "build/source SHA mismatch")
    require(result.get("SourceTreeClean") is True, "unclean source build receipt")
    require(result.get("BuildrootVersion") == "2025.02.18", "wrong Buildroot version")
    require(result.get("BuildrootCommit") == BUILDROOT_COMMIT, "wrong Buildroot Git pin")
    require(result.get("BuildProfile") == "RESIDENT_BROWSER", "wrong build profile")
    require(result.get("Defconfig") == "veraos_x86_64_resident_browser_defconfig", "wrong defconfig")
    require(result.get("BrowserPackaged") is True, "browser not packaged")
    require(result.get("ResidentCoreSourceStaged") is True, "resident source not staged")
    require(result.get("ResidentCoreImportQualified") is False, "premature import qualification")
    require(result.get("ProtectedEffectAuthority") is False, "protected authority present")
    for name, key in (("veraos-bzImage", "KernelSha256"), ("veraos-rootfs.ext2", "RootfsSha256")):
        path = artifacts / name
        require(path.is_file() and path.stat().st_size > 1024 * 1024, f"invalid image: {name}")
        claimed = result.get(key)
        require(isinstance(claimed, str) and SHA256.fullmatch(claimed) is not None,
                f"invalid SHA256 field: {key}")
        require(sha256_file(path) == claimed, f"hash mismatch: {name}")
    return result


def expected_boot_marker(composition_path: Path) -> str:
    composition = json.loads(composition_path.read_text(encoding="utf-8"))
    rows = composition["repositories"]
    require(isinstance(rows, list) and len(rows) > 0, "invalid portfolio composition")
    dispositions = [row["disposition"] for row in rows]
    total = len(rows)
    integrated = dispositions.count("INTEGRATED")
    excluded = dispositions.count("EXCLUDED")
    return (f"VERAOS_BOOT_READY_V1 pid=1 base=VERA total={total} "
            f"integrated={integrated} excluded={excluded} "
            "portfolio_plan_validated=true cognition_required=false "
            "browser_first_class=true ambient_protected_effect_authority=false")


def validate_resident_stage(stage: Path, result: dict) -> None:
    receipt_path = stage / "VERA_OS_RESIDENT_COMPONENTS_BUILD_RECEIPT_V1.json"
    require(receipt_path.is_file(), "resident source stage receipt missing")
    claimed = result.get("ResidentCoreStageReceiptSha256")
    require(isinstance(claimed, str) and SHA256.fullmatch(claimed) is not None,
            "resident source receipt hash absent")
    require(sha256_file(receipt_path) == claimed,
            "resident source stage hash disagrees with built image")


def expected_persistence(pass_number: int) -> str:
    return (f"VERAOS_PERSISTENCE_READY_V1 boot_ordinal={pass_number} "
            f"previous_boot_ordinal={pass_number - 1} canonical_memory=false "
            "supabase_replacement=false")


def assess_log(log: str, boot: str, pass_number: int) -> None:
    require(not any(x in log for x in PANIC_MARKERS), "guest emitted kernel panic/oops")
    require(log.count(boot) == 1, "PID1 boot marker missing or repeated")
    require(log.count(expected_persistence(pass_number)) == 1,
            "lifecycle persistence marker missing or repeated")
    require(log.count(RESIDENT_MARKER) == 1, "resident component composition not observed")
    require("ambient_protected_effect_authority=true" not in log,
            "guest claims ambient protected-effect authority")
    require("cognition_route_qualified=true" not in log,
            "guest claims an unqualified cognition route")


def docker_mounts(artifacts: Path, logs: Path) -> list[str]:
    return ["--network", "none", "--mount", f"type=bind,source={artifacts},target=/artifacts,readonly",
            "--mount", f"type=bind,source={logs},target=/logs"]


def overlay_command(image: str, artifacts: Path, logs: Path) -> list[str]:
    return (["docker", "run", "--rm", *docker_mounts(artifacts, logs),
             "--entrypoint", "/usr/bin/qemu-img", image, "create", "-f", "qcow2", "-F", "raw",
             "-b", "/artifacts/veraos-rootfs.ext2", "/logs/veraos-qualification-overlay.qcow2"])


def qemu_command(image: str, name: str, artifacts: Path, logs: Path, *, memory: int) -> list[str]:
    return (["docker", "run", "--rm", "--name", name, *docker_mounts(artifacts, logs),
             "--entrypoint", "/usr/bin/qemu-system-x86_64", image,
             "-m", str(memory), "-smp", "2", "-accel", "tcg", "-machine", "q35",
             "-kernel", "/artifacts/veraos-bzImage", "-drive",
             "file=/logs/veraos-qualification-overlay.qcow2,format=qcow2,if=virtio",
             "-append", BOOT_CONSOLE, "-nic", "none", "-nographic", "-no-reboot"])


def run_boot(command: list[str], name: str, logfile: Path, boot: str,
             number: int, seconds: int, *, dwell_seconds: float = 5.0) -> None:
    process = None
    observed_all_markers = False
    first_marker_seen_at = None
    clean_stop = False
    require(dwell_seconds >= 5.0, "at least five seconds of live dwell required")
    try:
        with logfile.open("x", encoding="utf-8") as output:
            process = subprocess.Popen(command, stdout=output, stderr=subprocess.STDOUT)
            deadline = time.monotonic() + seconds
            while time.monotonic() < deadline:
                log = logfile.read_text(encoding="utf-8", errors="replace")
                if any(x in log for x in PANIC_MARKERS):
                    raise QualificationError(f"guest panic on pass {number}")
                if process.poll() is not None:
                    raise QualificationError(
                        f"QEMU exited before live dwell completed on pass {number}: {process.returncode}"
                    )
                markers_found = all(x in log for x in (boot, expected_persistence(number), RESIDENT_MARKER))
                if markers_found:
                    assess_log(log, boot, number)
                    now = time.monotonic()
                    if first_marker_seen_at is None:
                        first_marker_seen_at = now
                    if now - first_marker_seen_at >= dwell_seconds:
                        observed_all_markers = True
                        break
                else:
                    first_marker_seen_at = None
                time.sleep(0.5)
            if not observed_all_markers:
                raise QualificationError(f"QEMU timeout before markers on pass {number}")
    finally:
        if process is not None and process.poll() is None:
            # Only stop the uniquely generated container created by this invocation.
            stopped = subprocess.run(["docker", "stop", "-t", "1", name],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                     timeout=15, check=False)
            clean_stop = stopped.returncode == 0
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
    if observed_all_markers:
        require(clean_stop, "QEMU stopped unexpectedly after markers; no verified live dwell")
        # Include final output written during the bounded Docker/QEMU stop.
        assess_log(logfile.read_text(encoding="utf-8", errors="replace"), boot, number)


def pin_runner_image(tag: str, claimed_id: str) -> str:
    require(IMAGE_ID.fullmatch(claimed_id) is not None, "runner image SHA256 ID required")
    observed = subprocess.run(["docker", "image", "inspect", "--format", "{{.Id}}", tag],
                              check=True, capture_output=True, text=True).stdout.strip()
    require(observed == claimed_id, "Docker runner tag disagrees with externally reviewed image ID")
    return observed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--resident-source-stage", type=Path, required=True)
    parser.add_argument("--logs", type=Path, required=True,
                        help="Unique nonexistent directory; no existing artifacts are overwritten")
    parser.add_argument("--source-head", required=True)
    parser.add_argument("--runner-image", default="veraos-qemu-runner:local")
    parser.add_argument("--expected-runner-image-id", required=True,
                        help="sha256:<64>, independently reviewed QEMU runner Docker image ID")
    parser.add_argument("--timeout-seconds", type=int, default=300)
    parser.add_argument("--memory-mib", type=int, default=3072)
    args = parser.parse_args(argv)
    repo, artifacts, logs, stage = (
        x.resolve() for x in (args.repo, args.artifacts, args.logs, args.resident_source_stage)
    )
    require(args.timeout_seconds >= 30, "timeout must be >= 30 seconds")
    require(1024 <= args.memory_mib <= 8192, "memory outside supported research range")
    require(logs != artifacts and logs != repo and not logs.is_relative_to(repo),
            "logs must be outside source checkout")
    require(logs != artifacts and not logs.is_relative_to(artifacts),
            "logs must be outside artifacts")
    require(not logs.exists(), "log directory already exists; refuse overwrite")
    require(args.source_head == EXPECTED_SOURCE_HEAD, "unreviewed image source HEAD")
    require(subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                           capture_output=True, text=True, check=True).stdout.strip() == args.source_head,
            "repo HEAD does not match requested exact SHA")
    require(not subprocess.run(["git", "-C", str(repo), "status", "--porcelain=v1"],
                               capture_output=True, text=True, check=True).stdout.strip(),
            "repo source tree is dirty")
    receipt = validate_build(artifacts, args.source_head)
    validate_resident_stage(stage, receipt)
    verifier = repo / "tools/vm/Stage-VeraOSResidentSources.py"
    verified_blob = subprocess.run(["git", "hash-object", "--", str(verifier)],
                                   check=True, capture_output=True, text=True).stdout.strip()
    require(verified_blob == TRUSTED_STAGE_VERIFIER_BLOB,
            "staged-source verifier differs from reviewed exact Git blob")
    subprocess.run([sys.executable, str(repo / "tools/vm/Stage-VeraOSResidentSources.py"),
                    "--verify-stage", str(stage), "--repo-root", str(repo)],
                   check=True, stdout=subprocess.DEVNULL)
    boot = expected_boot_marker(repo / "architecture/portfolio/VERA_OS_PORTFOLIO_COMPOSITION_V1.json")
    # The runner ID is supplied from independent source-bound review. Using the
    # immutable ID rather than tag closes the tag-change race during a boot.
    runner_id = pin_runner_image(args.runner_image, args.expected_runner_image_id)
    logs.mkdir(parents=True, exist_ok=False)
    subprocess.run(overlay_command(runner_id, artifacts, logs), check=True)
    results = []
    for number in (1, 2):
        name = f"veraos-bt2-qualify-{uuid.uuid4().hex[:16]}"
        logfile = logs / f"veraos-pass{number}.log"
        run_boot(qemu_command(runner_id, name, artifacts, logs,
                              memory=args.memory_mib),
                 name, logfile, boot, number, args.timeout_seconds)
        results.append({"pass": number, "boot_ready": True, "resident_marker": True,
                        "persistence_marker": expected_persistence(number),
                        "log_sha256": sha256_file(logfile)})
    qualification = {
        "schema": "VERA_OS_RESIDENT_QEMU_RESEARCH_QUALIFICATION_V1",
        "source_head": args.source_head,
        "build_receipt_sha256": sha256_file(artifacts / "veraos-build-result.json"),
        "kernel_sha256": receipt["KernelSha256"],
        "rootfs_sha256": receipt["RootfsSha256"],
        "profile": "RESIDENT_BROWSER", "qemu_two_boots": True,
        "runner_image_id": runner_id,
        "live_dwell_seconds_per_boot": 5,
        "isolated_network": "DOCKER_NETWORK_NONE_AND_QEMU_NIC_NONE",
        "qualification_disk": "DISPOSABLE_QCOW2_OVERLAY_HOST_DISKS_UNTOUCHED",
        "resident_component_import_serial_marker_observed": True,
        "resident_component_import_independently_qualified": False,
        "guest_pid1_heartbeat_qualified": False,
        "runner_image_source_attestation_qualified": False,
        "model_admission_qualified": False,
        "protected_effect_authority_qualified": False,
        "desktop_render_qualified": False,
        "canonical_memory_qualified": False,
        "physical_installation_qualified": False,
        "passes": results,
    }
    with (logs / "veraos-resident-qemu-research-qualification.json").open("x", encoding="utf-8") as f:
        json.dump(qualification, f, indent=2, sort_keys=True)
        f.write("\n")
    print(json.dumps(qualification, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (QualificationError, ValueError, OSError, subprocess.CalledProcessError) as exc:
        print(f"RESEARCH_QEMU_QUALIFICATION_HOLD: {exc}", file=sys.stderr)
        raise SystemExit(1)
