param(
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")),
    [string]$ArtifactRoot = "D:\VeraOS\vm\artifacts",
    [string]$BuilderImage = "veraos-buildroot-builder:2024.02.4",
    [string]$BuildVolume = "veraos-buildroot-work",
    [int]$Jobs = 4
)

$ErrorActionPreference = "Stop"

$repo = [System.IO.Path]::GetFullPath($RepoRoot)
$artifacts = [System.IO.Path]::GetFullPath($ArtifactRoot)
$builderDockerfile = Join-Path $repo "tools\vm\buildroot-builder.Dockerfile"

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
expected="e0a2687421a4f93e65aa00a30bcb0b4817f7a195"
if [ ! -d /work/buildroot/.git ]; then
  git clone --depth 1 --branch 2024.02.4 https://github.com/buildroot/buildroot.git /work/buildroot
fi
actual="$(git -C /work/buildroot rev-parse HEAD)"
test "$actual" = "$expected"
make -C /work/buildroot O=/work/output BR2_EXTERNAL=/workspace/buildroot veraos_x86_64_defconfig
make -C /work/buildroot O=/work/output BR2_EXTERNAL=/workspace/buildroot olddefconfig
make -C /work/buildroot O=/work/output BR2_EXTERNAL=/workspace/buildroot -j"$VERAOS_JOBS"
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
    "--mount", "type=bind,source=$repo,target=/workspace,readonly",
    "--mount", "type=bind,source=$artifacts,target=/artifacts",
    "--mount", "type=volume,source=$BuildVolume,target=/work",
    "--entrypoint", "/bin/sh",
    $BuilderImage,
    "/artifacts/veraos-buildroot-build.sh"
)

& docker @dockerArgs
if ($LASTEXITCODE -ne 0) {
    throw "VeraOS Buildroot image build failed"
}

$kernel = Join-Path $artifacts "veraos-bzImage"
$rootfs = Join-Path $artifacts "veraos-rootfs.ext2"
if (-not (Test-Path $kernel) -or -not (Test-Path $rootfs)) {
    throw "VeraOS Buildroot artifacts were not produced"
}

[pscustomobject]@{
    Schema = "VERA_OS_BUILDROOT_BUILD_RESULT_V1"
    ProductBase = "VERA"
    ImageBuilder = "Buildroot"
    BuildrootVersion = "2024.02.4"
    BuildrootCommit = "e0a2687421a4f93e65aa00a30bcb0b4817f7a195"
    Kernel = $kernel
    KernelSha256 = ((Get-FileHash $kernel -Algorithm SHA256).Hash.ToLowerInvariant())
    Rootfs = $rootfs
    RootfsSha256 = ((Get-FileHash $rootfs -Algorithm SHA256).Hash.ToLowerInvariant())
    BrowserEngine = "WPE WebKit / Cog"
    ProtectedEffectAuthority = $false
} | ConvertTo-Json -Depth 4
