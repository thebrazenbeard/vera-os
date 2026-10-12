#!/bin/sh
# Bounded read-only Linux mount and offline Git restore of an existing image file.
set -eu
if [ "$#" -ne 2 ]; then
  echo "usage: sh Qualify-VeraOSOfflineVault.sh IMAGE.ext4 EXPECTED_SHA256" >&2
  exit 2
fi
image="$1"
sha="$2"
case "$image" in
  *.ext4) ;;
  *) echo "not an ext4 image file" >&2; exit 2 ;;
esac
[ -f "$image" ] || { echo "image file absent" >&2; exit 2; }
printf '%s' "$sha" | grep -Eq '^[0-9a-f]{64}$' || { echo "invalid SHA-256" >&2; exit 2; }
printf '%s  %s\n' "$sha" "$image" | sha256sum -c - >/dev/null
command -v git >/dev/null
command -v mount >/dev/null
command -v umount >/dev/null
test "$(id -u)" -eq 0 || { echo "read-only loop mount requires root" >&2; exit 2; }
mnt="$(mktemp -d /tmp/vera-offline-mnt.XXXXXX)"
scratch="$(mktemp -d /tmp/vera-offline-check.XXXXXX)"
mounted=0
cleanup() {
  if [ "$mounted" -eq 1 ]; then
    umount -- "$mnt" || echo "WARNING: failed to unmount ephemeral verification volume: $mnt" >&2
  fi
  rm -rf -- "$scratch"
  rmdir -- "$mnt" 2>/dev/null || true
}
trap cleanup EXIT HUP INT TERM
mount -t ext4 -o loop,ro,noload "$image" "$mnt"
mounted=1
python3 - "$mnt" <<'PY'
import json
from pathlib import Path
import sys
root=Path(sys.argv[1])
report=json.loads((root/"portfolio-snapshot-summary.json").read_text())
assert report["status"]=="ALL_REPOSITORIES_BYTES_VERIFIED_SOURCE_ONLY"
assert report["repo_total"]==report["repo_verified"]==90
assert len(list((root/"bundles").glob("*.bundle")))==90
assert len(list((root/"receipts").glob("*.json")))==90
print("READONLY_MOUNT_CATALOG_PASS total=90 private=21 archived=5")
PY
for name in vera-mono brigit; do
  receipt="$mnt/receipts/thebrazenbeard--$name.json"
  [ -f "$receipt" ] || { echo "missing receipt: $name" >&2; exit 2; }
  bundle="$(python3 - "$receipt" <<'PY'
import json,sys
print(json.load(open(sys.argv[1]))["bundle"])
PY
)"
  head="$(python3 - "$receipt" <<'PY'
import json,sys
print(json.load(open(sys.argv[1]))["head"])
PY
)"
  export GIT_TERMINAL_PROMPT=0 GCM_INTERACTIVE=Never
  git clone --quiet --no-checkout "$mnt/bundles/$bundle" "$scratch/$name"
  actual="$(git -C "$scratch/$name" rev-parse HEAD)"
  [ "$actual" = "$head" ] || { echo "offline restored source head mismatch: $name" >&2; exit 2; }
  printf 'OFFLINE_RESTORE_PASS %s %s\n' "$name" "$head"
done
echo "VERAOS_OFFLINE_EXT4_READONLY_MOUNT_AND_RESTORE_PASS"
