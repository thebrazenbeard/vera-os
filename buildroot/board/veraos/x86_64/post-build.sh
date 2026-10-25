#!/bin/sh
set -eu

target_dir="$1"
script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
repo_root="$(CDPATH= cd -- "$script_dir/../../../.." && pwd)"

install -d "$target_dir/opt/veraos/src"
rm -rf "$target_dir/opt/veraos/src/veraos"
cp -R "$repo_root/src/veraos" "$target_dir/opt/veraos/src/veraos"
find "$target_dir/opt/veraos/src/veraos" -type d -name __pycache__ -prune -exec rm -rf {} +

install -d "$target_dir/etc/veraos/architecture"
install -m 0644 "$repo_root/architecture/os/VERA_OS_BOOT_CONTRACT_V1.json"   "$target_dir/etc/veraos/architecture/VERA_OS_BOOT_CONTRACT_V1.json"
install -m 0644 "$repo_root/architecture/portfolio/VERA_OS_PORTFOLIO_COMPOSITION_V1.json"   "$target_dir/etc/veraos/architecture/VERA_OS_PORTFOLIO_COMPOSITION_V1.json"
install -m 0644 "$repo_root/architecture/portfolio/VERA_OS_PORTFOLIO_IMPLEMENTATION_PLAN_V1.json"   "$target_dir/etc/veraos/architecture/VERA_OS_PORTFOLIO_IMPLEMENTATION_PLAN_V1.json"
install -m 0644 "$repo_root/architecture/capabilities/VERA_OS_PORTFOLIO_CAPABILITY_MAP_V1.json"   "$target_dir/etc/veraos/architecture/VERA_OS_PORTFOLIO_CAPABILITY_MAP_V1.json"


if [ "${VERAOS_REQUIRE_RESIDENT_CORE:-0}" = "1" ]; then
  # Only the 2025 resident guest candidate is eligible here. The packaged
  # V1 boot contract remains an explicitly historical 2024 baseline.
  if [ "${VERAOS_RESIDENT_GUEST_PROFILE:-}" != "2025.02.18" ]; then
    echo "Explicit VERAOS_RESIDENT_GUEST_PROFILE=2025.02.18 required" >&2
    exit 1
  fi
  # This is an opt-in source packaging stage, not service activation.
  stage="${VERAOS_RESIDENT_STAGE:-}"
  if [ -z "$stage" ] || [ ! -d "$stage/components" ] ||
     [ ! -f "$stage/VERA_OS_RESIDENT_COMPONENTS_BUILD_RECEIPT_V1.json" ]; then
    echo "VeraOS resident component stage missing" >&2
    exit 1
  fi

  # Both Vera Mono and Portal require Python >=3.12. Buildroot 2024.02.4
  # ships Python 3.11, so fail rather than embed incompatible code.
  target_python="$(readlink "$target_dir/usr/bin/python3" || true)"
  # The selected Buildroot 2025.02.18 contract pins Python 3.12.14.
  # Newer host interpreters cannot substitute for a different target ABI.
  case "$target_python" in
    python3.12|/usr/bin/python3.12) ;;
    *) echo "VeraOS resident target must be pinned Python 3.12; observed $target_python" >&2; exit 1 ;;
  esac

  python3 "$repo_root/tools/vm/Stage-VeraOSResidentSources.py" \
    --verify-stage "$stage" --repo-root "$repo_root"
  # Parse required resident API symbols without importing staged third-party code.
  python3 "$repo_root/tools/vm/Verify-ResidentDependencies.py" \
    --components-root "$stage/components"
  # Sidecar is a SOURCE-GUEST PROFILE only; never claim final output/images
  # or a booted/selected QualifiedVeraRuntime from successful source staging.
  python3 "$repo_root/tools/vm/Verify-VeraOSResidentGuestProfile.py" \
    --stage "$stage" --repo-root "$repo_root"
  install -m 0644 "$repo_root/architecture/os/VERA_OS_RESIDENT_GUEST_PROFILE_V1.json" \
    "$target_dir/etc/veraos/architecture/VERA_OS_RESIDENT_GUEST_PROFILE_V1.json"

  install -d "$target_dir/opt/veraos/components"
  cp -R "$stage/components/." "$target_dir/opt/veraos/components/"
  install -m 0644 "$stage/VERA_OS_RESIDENT_COMPONENTS_BUILD_RECEIPT_V1.json" \
    "$target_dir/etc/veraos/architecture/VERA_OS_RESIDENT_COMPONENTS_BUILD_RECEIPT_V1.json"

  # SOURCE proof does not prove the target copy. Check the actual built
  # tree's entire 431-file inventory, imported modules and PID1/GUI assets
  # before Buildroot turns the tree into an image. Guest behavior stays HOLD.
  python3 "$repo_root/tools/vm/Verify-VeraOSResidentFiles.py" \
    --rootfs-directory "$target_dir" --stage "$stage" --repo-root "$repo_root"
  python3 "$repo_root/tools/vm/Probe-ResidentTargetRootfs.py" \
    --rootfs-directory "$target_dir" --repo-root "$repo_root"
  # Actual target ELF64 dynamic dependencies must resolve transitively;
  # source/package presence alone is not target native-link qualification.
  python3 "$repo_root/tools/vm/Probe-ResidentELFClosure.py" \
    --rootfs-directory "$target_dir"

  # Explicitly no auto-start or protected-effect admission here.
fi

chmod 0755 "$target_dir/sbin/vera-init"
# Explicit QEMU-only diagnostic init; NEVER used by default boot.
chmod 0755 "$target_dir/sbin/vera-virtio-probe"
