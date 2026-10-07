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
install -m 0644 "$repo_root/architecture/capabilities/VERA_OS_PORTFOLIO_CAPABILITY_MAP_V1.json"   "$target_dir/etc/veraos/architecture/VERA_OS_PORTFOLIO_CAPABILITY_MAP_V1.json"

chmod 0755 "$target_dir/sbin/vera-init"
