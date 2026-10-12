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
  case "$target_python" in
    python3.12|python3.13|python3.14|python3.15|python3.16) ;;
    *) echo "VeraOS resident runtime requires target Python >=3.12; observed $target_python" >&2; exit 1 ;;
  esac

  python3 "$repo_root/tools/vm/Stage-VeraOSResidentSources.py" \
    --verify-stage "$stage" --repo-root "$repo_root"

  install -d "$target_dir/opt/veraos/components"
  cp -R "$stage/components/." "$target_dir/opt/veraos/components/"
  install -m 0644 "$stage/VERA_OS_RESIDENT_COMPONENTS_BUILD_RECEIPT_V1.json" \
    "$target_dir/etc/veraos/architecture/VERA_OS_RESIDENT_COMPONENTS_BUILD_RECEIPT_V1.json"

  # Explicitly no auto-start or protected-effect admission here.
fi


# Optional private local visuals. Do not turn wallpaper into a boot dependency.
# These files are staged outside Git and remain in a locally held VeraOS image.
if [ -n "${VERAOS_DESKTOP_STAGE:-}" ]; then
  branding_stage="$VERAOS_DESKTOP_STAGE"
  python3 "$repo_root/tools/ui/Stage-VeraOSBranding.py" \
    --verify-stage "$branding_stage" >/dev/null
  install -d "$target_dir/usr/share/veraos/branding"
  for name in wallpaper-1920x1080.jpg launcher-256.png launcher-128.png \
              launcher-64.png launcher-32.png; do
    install -m 0644 "$branding_stage/$name" \
      "$target_dir/usr/share/veraos/branding/$name"
  done
  if [ -f "$branding_stage/avatar-512.png" ]; then
    install -m 0644 "$branding_stage/avatar-512.png" \
      "$target_dir/usr/share/veraos/branding/avatar-512.png"
  fi
  install -m 0644 "$branding_stage/branding-receipt.json" \
    "$target_dir/etc/veraos/architecture/VERA_OS_LOCAL_BRANDING_BUILD_RECEIPT_V1.json"
  # Copied raster assets are not proof of graphical UI or P.O.R.T.A.L. render.
fi

chmod 0755 "$target_dir/sbin/vera-init"
