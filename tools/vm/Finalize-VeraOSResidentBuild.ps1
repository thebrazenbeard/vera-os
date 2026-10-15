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
# The compiled image belongs to the original DRM-only source head, not to
# the later qualification-tooling commit. Validate exact ancestry and ensure
# only an allowlisted qualification-file delta exists.
$sourceValidator = Join-Path $repo "tools\vm\Verify-VeraOSBuildSource.py"
$sourceResult = & python $sourceValidator --repo-root $repo --image-source-head $ExpectedSourceHead
if ($LASTEXITCODE -ne 0) { throw "VeraOS image-source ancestry or isolation check failed" }
$sourceBinding = ($sourceResult | Out-String | ConvertFrom-Json)
if ($sourceBinding.image_build_source_head -ne $ExpectedSourceHead -or
    -not $sourceBinding.image_source_unchanged_since_build) {
    throw "VeraOS image source binding does not match completed builder"
}
$head = $sourceBinding.image_build_source_head
$qualificationHead = $sourceBinding.qualification_tool_head
$stageTool = Join-Path $repo "tools\vm\Stage-VeraOSResidentSources.py"
& python $stageTool --verify-stage $stage --repo-root $repo | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Resident source receipt failed verification" }

$active = @(& docker ps --filter "volume=$BuildVolume" --format "{{.ID}}" |
    Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
if ($LASTEXITCODE -ne 0) { throw "Docker state unavailable" }
if ($active.Count -gt 0) { throw "Resident builder still active; refuse premature receipt" }
# Bind this image to the exact finished container that produced the outputs,
# rather than inferring build success merely from files being present.
$builderName = "veraos-resident-browser-cogdrm-20261015"
$builderRecord = & docker inspect $builderName
if ($LASTEXITCODE -ne 0) { throw "Completed resident builder cannot be inspected" }
$builder = ($builderRecord | Out-String | ConvertFrom-Json)[0]
$expectedBuilderId = "969b67ba71a11c4e6c5d635bf686ad76d62d5d99ccff0c5c08580ebbef297f12"
if ($builder.Id -ne $expectedBuilderId -or
    $builder.State.Status -ne "exited" -or
    $builder.State.ExitCode -ne 0 -or
    $builder.State.OOMKilled -ne $false) {
    throw "Resident Buildroot builder did not complete successfully"
}
$buildSourceMount = @($builder.Mounts | Where-Object { $_.Destination -eq "/workspace" })
$residentStageMount = @($builder.Mounts | Where-Object { $_.Destination -eq "/resident" })
$buildVolumeMount = @($builder.Mounts | Where-Object { $_.Destination -eq "/work" })
if ($buildSourceMount.Count -ne 1 -or $residentStageMount.Count -ne 1 -or
    $buildVolumeMount.Count -ne 1 -or
    $buildSourceMount[0].Source -ne "D:\VeraOS\vm\resident-cog-drm-only-20261015" -or
    $buildSourceMount[0].RW -ne $false -or
    $residentStageMount[0].Source -ne $stage -or
    $residentStageMount[0].RW -ne $false -or
    $buildVolumeMount[0].Name -ne $BuildVolume) {
    throw "Completed build container source/stage/volume bindings do not match"
}
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
    QualificationToolHead = $qualificationHead
    ImageBuildSourceUnchanged = $true
    SourceTreeClean = $true
    ImageBuilder = "Buildroot"
    BuildrootVersion = "2025.02.18"
    BuildrootCommit = $verifiedBuildrootHead
    BuilderContainerId = $expectedBuilderId
    BuilderExitCode = 0
    BuilderOOMKilled = $false
    BuilderSourceReadOnly = $true
    ResidentStageReadOnly = $true
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
