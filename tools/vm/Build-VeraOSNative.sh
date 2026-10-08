#!/usr/bin/env bash
# Native Linux Buildroot entrypoint; never installs or deploys VeraOS.
set -euo pipefail
if (( $# < 2 || $# > 4 )); then echo "usage: $0 REPO_ROOT ARTIFACT_DIR [CORE_BOOT|BROWSER] [JOBS]" >&2; exit 2; fi
repo=$(realpath "$1"); artifacts=$(realpath -m "$2")
profile=${3:-CORE_BOOT}; jobs=${4:-4}
case "$profile" in
 CORE_BOOT) defconfig=veraos_x86_64_defconfig; browser=false ;;
 BROWSER) defconfig=veraos_x86_64_browser_defconfig; browser=true ;;
 *) echo "Unknown profile" >&2; exit 2 ;;
esac
[[ "$jobs" =~ ^[1-9][0-9]*$ ]] || exit 2
[[ -d "$repo/.git" && -f "$repo/buildroot/external.desc" ]] || { echo "Invalid VeraOS checkout" >&2; exit 1; }
head=$(git -C "$repo" rev-parse HEAD)
[[ "$head" =~ ^[0-9a-f]{40}$ ]] || exit 1
[[ -z "$(git -C "$repo" status --porcelain=v1)" ]] || { echo "Dirty VeraOS checkout" >&2; exit 1; }
case "$artifacts/" in "$repo/"*) echo "Artifacts inside source checkout" >&2; exit 1 ;; esac
for bin in git make gcc python3 sha256sum realpath; do command -v "$bin" >/dev/null || { echo "Missing $bin" >&2; exit 1; }; done
work=$(realpath -m "${VERAOS_BUILD_WORK:-$artifacts/work}")
case "$work/" in "$repo/"*) echo "Build work inside source checkout" >&2; exit 1 ;; esac
mkdir -p "$work" "$artifacts"
broot="$work/buildroot"; expected=e0a2687421a4f93e65aa00a30bcb0b4817f7a195
if [[ ! -d "$broot/.git" ]]; then
 [[ ! -e "$broot" ]] || { echo "Existing untrusted Buildroot directory" >&2; exit 1; }
 git clone --depth 1 --branch 2024.02.4 https://github.com/buildroot/buildroot.git "$broot"
fi
actual=$(git -C "$broot" rev-parse HEAD)
[[ "$actual" == "$expected" ]] || { echo "Buildroot pin mismatch: $actual" >&2; exit 1; }
[[ -z "$(git -C "$broot" status --porcelain=v1)" ]] || { echo "Dirty Buildroot checkout" >&2; exit 1; }
output="$work/output"
make -C "$broot" O="$output" BR2_EXTERNAL="$repo/buildroot" "$defconfig"
make -C "$broot" O="$output" BR2_EXTERNAL="$repo/buildroot" olddefconfig
make -C "$broot" O="$output" BR2_EXTERNAL="$repo/buildroot" BR2_JLEVEL="$jobs" -j"$jobs"
for file in bzImage rootfs.ext2; do [[ -s "$output/images/$file" ]] || { echo "Missing $file" >&2; exit 1; }; done
cp "$output/images/bzImage" "$artifacts/veraos-bzImage"
cp "$output/images/rootfs.ext2" "$artifacts/veraos-rootfs.ext2"
export VERAOS_HEAD="$head" VERAOS_PROFILE="$profile" VERAOS_DEFCONFIG="$defconfig" VERAOS_BROWSER="$browser" VERAOS_ARTIFACTS="$artifacts"
python3 - <<'PY'
import hashlib,json,os,pathlib
root=pathlib.Path(os.environ['VERAOS_ARTIFACTS'])
def sha(name):
 h=hashlib.sha256()
 with (root/name).open('rb') as f:
  for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
 return h.hexdigest()
receipt={'Schema':'VERA_OS_BUILDROOT_BUILD_RESULT_V1','ProductBase':'VERA','SourceHead':os.environ['VERAOS_HEAD'],'SourceTreeClean':True,'ImageBuilder':'Buildroot','BuildrootVersion':'2024.02.4','BuildrootCommit':'e0a2687421a4f93e65aa00a30bcb0b4817f7a195','Kernel':str(root/'veraos-bzImage'),'KernelSha256':sha('veraos-bzImage'),'Rootfs':str(root/'veraos-rootfs.ext2'),'RootfsSha256':sha('veraos-rootfs.ext2'),'BuildProfile':os.environ['VERAOS_PROFILE'],'Defconfig':os.environ['VERAOS_DEFCONFIG'],'BrowserPackaged':os.environ['VERAOS_BROWSER']=='true','BrowserProfileDefconfig':'veraos_x86_64_browser_defconfig','ProtectedEffectAuthority':False}
(root/'veraos-build-result.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt,indent=2))
PY
