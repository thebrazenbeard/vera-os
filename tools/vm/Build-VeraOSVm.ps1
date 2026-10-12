param(
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")),
    [string]$ArtifactRoot = "D:\VeraOS\vm\artifacts",
    [string]$BuilderImage = "veraos-buildroot-builder:2024.02.4",
    [string]$BuildVolume = "veraos-buildroot-work",
    [int]$Jobs = 4,
    [ValidateSet("CORE_BOOT", "BROWSER", "RESIDENT_BROWSER")]
    [string]$Profile = "CORE_BOOT",
    [string]$ResidentSourceStage = ""
)

$ErrorActionPreference = "Stop"

$repo = [System.IO.Path]::GetFullPath($RepoRoot)
$artifacts = [System.IO.Path]::GetFullPath($ArtifactRoot)
$builderDockerfile = Join-Path $repo "tools\vm\buildroot-builder.Dockerfile"
$sourceHead = (& git -C $repo rev-parse HEAD | Select-Object -First 1)
if (-not $sourceHead) { throw "Unable to resolve VeraOS source head" }
$sourceStatus = @(& git -C $repo status --porcelain=v1)
if ($sourceStatus.Count -gt 0) {
    throw "VeraOS image build requires a clean source tree for exact-head provenance"
}

$buildrootVersion = "2024.02.4"
$buildrootCommit = "e0a2687421a4f93e65aa00a30bcb0b4817f7a195"
switch ($Profile) {
    "CORE_BOOT" {
        $defconfig = "veraos_x86_64_defconfig"
        $browserPackaged = $false
    }
    "BROWSER" {
        $defconfig = "veraos_x86_64_browser_defconfig"
        $browserPackaged = $true
    }
    "RESIDENT_BROWSER" {
        $defconfig = "veraos_x86_64_resident_browser_defconfig"
        $browserPackaged = $true
        $buildrootVersion = "2025.02.18"
        $buildrootCommit = "d030e36bbc9669230c015be971b14b6e062cfdde"
        if (-not $ResidentSourceStage) {
            throw "RESIDENT_BROWSER requires an explicit, separately verified resident source stage"
        }
    }
}
if ($ResidentSourceStage -and $Profile -ne "RESIDENT_BROWSER") {
    throw "Resident source staging is allowed only for RESIDENT_BROWSER"
}

$residentSourceStageResolved = $null
if ($ResidentSourceStage) {
    $residentSourceStageResolved = [System.IO.Path]::GetFullPath($ResidentSourceStage)
    $receipt = Join-Path $residentSourceStageResolved "VERA_OS_RESIDENT_COMPONENTS_BUILD_RECEIPT_V1.json"
    $sources = Join-Path $residentSourceStageResolved "components"
    if (-not (Test-Path -PathType Container $sources) -or -not (Test-Path -PathType Leaf $receipt)) {
        throw "Resident source stage or its pinned receipt is missing"
    }
    if ($residentSourceStageResolved.StartsWith($repo + [IO.Path]::DirectorySeparatorChar,
         [StringComparison]::OrdinalIgnoreCase)) {
        throw "Resident source stage must be external to the VeraOS checkout"
    }
}
New-Item -ItemType Directory -Force $artifacts | Out-Null

& docker build -t $BuilderImage -f $builderDockerfile $repo
if ($LASTEXITCODE -ne 0) {
    throw "VeraOS Buildroot builder image failed"
}

$existingVolume = (& docker volume ls --filter "name=^$BuildVolume$" --format "{{.Name}}" | Select-Object -First 1)
if ($existingVolume -ne $BuildVolume) {
    docker volume create $BuildVolume | Out-Null
}

$script = @'
set -eu
expected="$VERAOS_BUILDROOT_COMMIT"
if [ ! -d /work/buildroot/.git ]; then
  git clone --depth 1 --branch "$VERAOS_BUILDROOT_VERSION" https://github.com/buildroot/buildroot.git /work/buildroot
fi
actual="$(git -C /work/buildroot rev-parse HEAD)"
test "$actual" = "$expected"
if [ "${VERAOS_REQUIRE_RESIDENT_CORE:-0}" = "1" ]; then
  python_major="$(sed -n 's/^PYTHON3_VERSION_MAJOR = //p' /work/buildroot/package/python3/python3.mk | head -1)"
  case "$python_major" in
    3.12|3.13|3.14|3.15|3.16) ;;
    *) echo "Resident source packaging requires Buildroot Python >=3.12; version major $python_major" >&2; exit 12 ;;
  esac
fi
make -C /work/buildroot O=/work/output BR2_EXTERNAL=/workspace/buildroot "$VERAOS_DEFCONFIG"
make -C /work/buildroot O=/work/output BR2_EXTERNAL=/workspace/buildroot olddefconfig
make -C /work/buildroot O=/work/output BR2_EXTERNAL=/workspace/buildroot BR2_JLEVEL="$VERAOS_JOBS" -j"$VERAOS_JOBS"
test -f /work/output/images/bzImage
test -f /work/output/images/rootfs.ext2
cp /work/output/images/bzImage /artifacts/veraos-bzImage
cp /work/output/images/rootfs.ext2 /artifacts/veraos-rootfs.ext2
sha256sum /artifacts/veraos-bzImage > /artifacts/veraos-bzImage.sha256
sha256sum /artifacts/veraos-rootfs.ext2 > /artifacts/veraos-rootfs.ext2.sha256
'@
$script = $script -replace "`r`n", "`n"
$scriptPath = Join-Path $artifacts "veraos-buildroot-build.sh"
[System.IO.File]::WriteAllText(
    $scriptPath,
    $script,
    [System.Text.UTF8Encoding]::new($false)
)

$dockerArgs = @(
    "run", "--rm",
    "--env", "VERAOS_JOBS=$Jobs",
    "--env", "VERAOS_DEFCONFIG=$defconfig",
    "--env", "VERAOS_BUILDROOT_VERSION=$buildrootVersion",
    "--env", "VERAOS_BUILDROOT_COMMIT=$buildrootCommit",
    "--mount", "type=bind,source=$repo,target=/workspace,readonly",
    "--mount", "type=bind,source=$artifacts,target=/artifacts",
    "--mount", "type=volume,source=$BuildVolume,target=/work",
    "--entrypoint", "/bin/sh",
    $BuilderImage,
    "/artifacts/veraos-buildroot-build.sh"
)

if ($residentSourceStageResolved) {
    # GNU autotools host packages must not be configured as root. This build
    # volume is profile-isolated; ownership changes cannot affect the
    # previously qualified 2024.02.4 CORE_BOOT/BROWSER caches.
    & docker run --rm --user "0:0" --mount "type=volume,source=$BuildVolume,target=/work" --entrypoint /bin/chown $BuilderImage -R "1000:1000" "/work"
    if ($LASTEXITCODE -ne 0) { throw "Could not prepare non-root resident build volume" }

    $dockerArgs = @(
        "run", "--rm",
        "--user", "1000:1000",
        "--env", "HOME=/home/vera-build",
        "--env", "VERAOS_REQUIRE_RESIDENT_CORE=1",
        "--env", "VERAOS_RESIDENT_STAGE=/resident",
        "--mount", "type=bind,source=$residentSourceStageResolved,target=/resident,readonly"
    ) + $dockerArgs[2..($dockerArgs.Count - 1)]
}
& docker @dockerArgs
if ($LASTEXITCODE -ne 0) {
    throw "VeraOS Buildroot image build failed"
}

$kernel = Join-Path $artifacts "veraos-bzImage"
$rootfs = Join-Path $artifacts "veraos-rootfs.ext2"
if (-not (Test-Path $kernel) -or -not (Test-Path $rootfs)) {
    throw "VeraOS Buildroot artifacts were not produced"
}

$result = [ordered]@{
    Schema = "VERA_OS_BUILDROOT_BUILD_RESULT_V1"
    ProductBase = "VERA"
    SourceHead = $sourceHead
    SourceTreeClean = $true
    ImageBuilder = "Buildroot"
    BuildrootVersion = $buildrootVersion
    BuildrootCommit = $buildrootCommit
    Kernel = $kernel
    KernelSha256 = ((Get-FileHash $kernel -Algorithm SHA256).Hash.ToLowerInvariant())
    Rootfs = $rootfs
    RootfsSha256 = ((Get-FileHash $rootfs -Algorithm SHA256).Hash.ToLowerInvariant())
    BuildProfile = $Profile
    Defconfig = $defconfig
    BrowserPackaged = $browserPackaged
    BrowserProfileDefconfig = if ($Profile -eq "RESIDENT_BROWSER") {
        "veraos_x86_64_resident_browser_defconfig"
    } else { "veraos_x86_64_browser_defconfig" }
    ResidentCoreSourceStaged = [bool]$residentSourceStageResolved
    ResidentCoreImportQualified = $false
    ResidentCoreStageReceiptSha256 = if ($residentSourceStageResolved) {
        ((Get-FileHash (Join-Path $residentSourceStageResolved "VERA_OS_RESIDENT_COMPONENTS_BUILD_RECEIPT_V1.json") -Algorithm SHA256).Hash.ToLowerInvariant())
    } else { $null }
    ProtectedEffectAuthority = $false
}
$resultJson = $result | ConvertTo-Json -Depth 4
$resultPath = Join-Path $artifacts "veraos-build-result.json"
[System.IO.File]::WriteAllText(
    $resultPath,
    $resultJson + [Environment]::NewLine,
    [System.Text.UTF8Encoding]::new($false)
)
$resultJson
