param(
    [Parameter(Mandatory=$true)][string]$RepoRoot,
    [Parameter(Mandatory=$true)][string]$ArtifactRoot,
    [Parameter(Mandatory=$true)][string]$ResidentSourceStage,
    [Parameter(Mandatory=$true)][string]$BuildVolume,
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-f]{40}$')][string]$ExpectedSourceHead,
    [string]$BuilderImage = "veraos-buildroot-builder:2025.02.18"
)
# Bind an already-completed isolated resident Buildroot image without rebuilding.
# This doesn't install, mount, start the guest, or mutate any physical disk.

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$repo = [IO.Path]::GetFullPath($RepoRoot)
$art = [IO.Path]::GetFullPath($ArtifactRoot)
$stage = [IO.Path]::GetFullPath($ResidentSourceStage)
$resultPath = Join-Path $art "veraos-build-result.json"
$kernel = Join-Path $art "veraos-bzImage"
$rootfs = Join-Path $art "veraos-rootfs.ext2"
$stageReceipt = Join-Path $stage "VERA_OS_RESIDENT_COMPONENTS_BUILD_RECEIPT_V1.json"
if (Test-Path -LiteralPath $resultPath) { throw "Build result exists: refuse overwrite" }
foreach ($path in @($kernel, $rootfs, $stageReceipt)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Required completed build artifact missing: $path"
    }
}
if ($art.StartsWith($repo + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Artifacts must remain outside the source checkout"
}
$head = (& git -C $repo rev-parse HEAD | Select-Object -First 1).Trim()
if ($LASTEXITCODE -ne 0 -or $head -ne $ExpectedSourceHead) { throw "Unexpected VeraOS source revision: $head" }
$dirty = @(& git -C $repo status --porcelain=v1)
if ($LASTEXITCODE -ne 0 -or $dirty.Count -gt 0) { throw "VeraOS source checkout is not clean" }
$stageTool = Join-Path $repo "tools\vm\Stage-VeraOSResidentSources.py"
& python $stageTool --verify-stage $stage --repo-root $repo | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Resident source receipt failed verification" }

$active = @(& docker ps --filter "volume=$BuildVolume" --format "{{.ID}}" |
    Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
if ($LASTEXITCODE -ne 0) { throw "Docker state unavailable" }
if ($active.Count -gt 0) { throw "Resident builder still active; refuse premature receipt" }
$sha = @{}
foreach ($name in @("veraos-bzImage", "veraos-rootfs.ext2")) {
    $filePath = Join-Path $art $name
    if ((Get-Item -LiteralPath $filePath).Length -lt 1024 * 1024) { throw "Image is suspiciously short: $name" }
    $digest = ((Get-FileHash -LiteralPath $filePath -Algorithm SHA256).Hash.ToLowerInvariant())
    $manifest = Join-Path $art ($name + ".sha256")
    if (-not (Test-Path -LiteralPath $manifest -PathType Leaf)) { throw "Builder SHA manifest missing: $name" }
    $line = (Get-Content -LiteralPath $manifest -TotalCount 1).Trim()
    if ($line -notmatch '^([0-9a-f]{64})\s+/artifacts/(veraos-bzImage|veraos-rootfs\.ext2)$' -or
        $matches[2] -ne $name -or $matches[1] -ne $digest) {
        throw "Builder SHA manifest disagrees with final image: $name"
    }
    $sha[$name] = $digest
}
# Confirm exact Buildroot git head from the isolated volume, mounted read-only.
$probeArgs = @("run","--rm","--user","1000:1000",
    "--mount","type=volume,source=$BuildVolume,target=/work,readonly",
    "--entrypoint","/usr/bin/git",$BuilderImage,
    "-C","/work/buildroot","rev-parse","HEAD")
$verifiedBuildrootHead = (& docker @probeArgs | Select-Object -First 1).Trim()
if ($LASTEXITCODE -ne 0 -or
    $verifiedBuildrootHead -ne "d030e36bbc9669230c015be971b14b6e062cfdde") {
    throw "Buildroot exact-source pin not satisfied"
}
$receipt = [ordered]@{
    Schema = "VERA_OS_BUILDROOT_BUILD_RESULT_V1"
    ProductBase = "VERA"
    SourceHead = $head
    SourceTreeClean = $true
    ImageBuilder = "Buildroot"
    BuildrootVersion = "2025.02.18"
    BuildrootCommit = $verifiedBuildrootHead
    Kernel = $kernel
    KernelSha256 = $sha["veraos-bzImage"]
    Rootfs = $rootfs
    RootfsSha256 = $sha["veraos-rootfs.ext2"]
    BuildProfile = "RESIDENT_BROWSER"
    Defconfig = "veraos_x86_64_resident_browser_defconfig"
    BrowserPackaged = $true
    BrowserProfileDefconfig = "veraos_x86_64_resident_browser_defconfig"
    ResidentCoreSourceStaged = $true
    ResidentCoreStageReceiptSha256 = ((Get-FileHash $stageReceipt -Algorithm SHA256).Hash.ToLowerInvariant())
    ResidentCoreImportQualified = $false
    DesktopAssetStagePackaged = $false
    DesktopAssetsRenderedQualified = $false
    OfflinePortfolioMountedInGuest = $false
    ProtectedEffectAuthority = $false
    Evidence = "HASHED_BUILDER_OUTPUTS_AND_SOURCE_RECEIPTS_ONLY_NOT_GUEST_TEST"
}
$json = $receipt | ConvertTo-Json -Depth 5
$handle = [IO.File]::Open($resultPath, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
try {
    $data = [Text.UTF8Encoding]::new($false).GetBytes($json + [Environment]::NewLine)
    $handle.Write($data, 0, $data.Length)
    $handle.Flush($true)
} finally { $handle.Dispose() }
Write-Output $json
