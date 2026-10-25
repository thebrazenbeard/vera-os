#!/usr/bin/env bash
# Qualify a native VeraOS Buildroot image with two network-isolated QEMU boots.
set -euo pipefail
if (( $# < 3 || $# > 4 )); then echo "usage: $0 REPO_ROOT ARTIFACT_DIR LOG_DIR [TIMEOUT_SECONDS]" >&2; exit 2; fi
repo=$(realpath "$1"); artifacts=$(realpath "$2"); logs=$(realpath -m "$3")
seconds=${4:-300}
[[ "$seconds" =~ ^[1-9][0-9]*$ ]] || { echo "Invalid timeout" >&2; exit 2; }
for bin in git qemu-img qemu-system-x86_64 timeout python3 sha256sum; do command -v "$bin" >/dev/null || { echo "Missing $bin" >&2; exit 1; }; done
head=$(git -C "$repo" rev-parse HEAD)
[[ -z "$(git -C "$repo" status --porcelain=v1)" ]] || { echo "Dirty source tree" >&2; exit 1; }
[[ -s "$artifacts/veraos-bzImage" && -s "$artifacts/veraos-rootfs.ext2" && -f "$artifacts/veraos-build-result.json" ]] || { echo "Missing build artifacts" >&2; exit 1; }
python3 - "$artifacts" "$head" <<'PY'
import hashlib,json,pathlib,sys
root=pathlib.Path(sys.argv[1]); head=sys.argv[2]
r=json.loads((root/'veraos-build-result.json').read_text())
assert r['Schema']=='VERA_OS_BUILDROOT_BUILD_RESULT_V1'
assert r['SourceHead']==head and r['SourceTreeClean'] is True
assert r['BuildrootVersion']=='2024.02.4'
assert r['BuildrootCommit']=='e0a2687421a4f93e65aa00a30bcb0b4817f7a195'
assert r['BuildProfile'] in ('CORE_BOOT','BROWSER')
assert (r['BuildProfile']=='BROWSER')==r['BrowserPackaged']
for filename,field in [('veraos-bzImage','KernelSha256'),('veraos-rootfs.ext2','RootfsSha256')]:
 h=hashlib.sha256()
 with (root/filename).open('rb') as f:
  for block in iter(lambda:f.read(1024*1024),b''): h.update(block)
 assert h.hexdigest()==r[field],filename
PY
mkdir -p "$logs"
overlay=$(mktemp "$logs/veraos-native-XXXXXXXX.qcow2")
rm -f "$overlay"
trap 'rm -f "$overlay"' EXIT
qemu-img create -q -f qcow2 -F raw -b "$artifacts/veraos-rootfs.ext2" "$overlay"
# Expected markers are fixed by the VeraOS guest boot contract, not user-supplied.
composition="$repo/architecture/portfolio/VERA_OS_PORTFOLIO_COMPOSITION_V1.json"
python3 - "$composition" "$logs/expected-marker.txt" <<'PY'
import json,pathlib,sys
repos=json.loads(pathlib.Path(sys.argv[1]).read_text())['repositories']
total=len(repos); integrated=sum(r['disposition']=='INTEGRATED' for r in repos); excluded=sum(r['disposition']=='EXCLUDED' for r in repos)
marker=f'VERAOS_BOOT_READY_V1 pid=1 base=VERA total={total} integrated={integrated} excluded={excluded} portfolio_plan_validated=true cognition_required=false browser_first_class=true ambient_protected_effect_authority=false'
pathlib.Path(sys.argv[2]).write_text(marker)
PY
bootmarker=$(cat "$logs/expected-marker.txt")
for pass in 1 2; do
 logfile="$logs/veraos-native-pass${pass}.log"
 # QEMU remains running after the markers; timeout is an intentional stop.
 timeout --signal=TERM --kill-after=5 "$seconds" qemu-system-x86_64 \
   -m 4096 -smp 2 -accel tcg -machine q35 \
   -kernel "$artifacts/veraos-bzImage" \
   -drive "file=$overlay,format=qcow2,if=virtio" \
   -append "root=/dev/vda rw console=ttyS0,115200 init=/sbin/vera-init" \
   -nic none -nographic -no-reboot > "$logfile" 2>&1 || status=$?
 status=${status:-0}
 if [[ "$status" != 0 && "$status" != 124 && "$status" != 143 ]]; then echo "QEMU failed on pass $pass: $status" >&2; exit 1; fi
 unset status
 grep -Fq "$bootmarker" "$logfile" || { echo "Boot marker missing on pass $pass" >&2; exit 1; }
 prev=$((pass-1))
 grep -Fq "VERAOS_PERSISTENCE_READY_V1 boot_ordinal=$pass previous_boot_ordinal=$prev canonical_memory=false supabase_replacement=false" "$logfile" || { echo "Persistence marker missing on pass $pass" >&2; exit 1; }
done
python3 - "$artifacts" "$logs" "$head" <<'PY'
import datetime,hashlib,json,pathlib,subprocess,sys
a,l,head=pathlib.Path(sys.argv[1]),pathlib.Path(sys.argv[2]),sys.argv[3]
build=json.loads((a/'veraos-build-result.json').read_text())
receipt={'schema':'VERA_OS_VM_QUALIFICATION_V3','qualified':True,'observed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source_head':head,'source_tree_clean':True,'build_receipt_sha256':hashlib.sha256((a/'veraos-build-result.json').read_bytes()).hexdigest(),'kernel_sha256':build['KernelSha256'],'rootfs_sha256':build['RootfsSha256'],'acceleration':'TCG_SOFTWARE_EMULATION','network':'NONE','qualification_disk':'DISPOSABLE_QCOW2_OVERLAY','restart_boot_passes':2,'restart_persistence_qualified':True,'lifecycle_persistence_qualified':True,'build_profile':build['BuildProfile'],'browser_packaged':build['BrowserPackaged'],'browser_runtime_qualified':False,'canonical_memory_qualified':False,'supabase_replacement_qualified':False,'ambient_protected_effect_authority':False,'host_partition_table_modified':False}
(a/'veraos-vm-qualification.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt,indent=2))
PY
