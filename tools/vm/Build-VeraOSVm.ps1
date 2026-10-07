param(
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\\..")),
    [string]$ArtifactRoot = "D:\\VeraOS\\vm\\artifacts",
    [string]$NixImage = "nixos/nix:latest",
    [string]$NixStoreVolume = "veraos-nix-store"
)

$ErrorActionPreference = "Stop"

$repo = [System.IO.Path]::GetFullPath($RepoRoot)
$artifacts = [System.IO.Path]::GetFullPath($ArtifactRoot)

New-Item -ItemType Directory -Force $artifacts | Out-Null

$existingVolume = (& docker volume ls --filter "name=^$NixStoreVolume$" --format "{{.Name}}").Trim()
if ($existingVolume -ne $NixStoreVolume) {
    docker volume create $NixStoreVolume | Out-Null
}

$script = @'
set -eu
nix --extra-experimental-features "nix-command flakes" flake lock
nix --extra-experimental-features "nix-command flakes" build .#packages.x86_64-linux.veraos-vm-iso --out-link result
iso="$(find -L result/iso -maxdepth 1 -type f -name '*.iso' -print -quit)"
test -n "$iso"
cp "$iso" /artifacts/veraos-vm.iso
sha256sum /artifacts/veraos-vm.iso > /artifacts/veraos-vm.iso.sha256
'@

$dockerArgs = @(
    "run",
    "--rm",
    "--mount", "type=bind,source=$repo,target=/workspace",
    "--mount", "type=bind,source=$artifacts,target=/artifacts",
    "--mount", "type=volume,source=$NixStoreVolume,target=/nix",
    "--workdir", "/workspace",
    "--entrypoint", "/bin/sh",
    $NixImage,
    "-lc",
    $script
)

& docker @dockerArgs
if ($LASTEXITCODE -ne 0) {
    throw "VeraOS VM ISO build failed"
}

$isoPath = Join-Path $artifacts "veraos-vm.iso"

if (-not (Test-Path $isoPath)) {
    throw "VeraOS VM ISO was not produced"
}

[pscustomobject]@{
    Schema = "VERA_OS_VM_BUILD_RESULT_V1"
    Iso = $isoPath
    Sha256 = ((Get-FileHash $isoPath -Algorithm SHA256).Hash.ToLowerInvariant())
    FlakeLock = (Join-Path $repo "flake.lock")
    ProtectedEffectAuthority = $false
} | ConvertTo-Json -Depth 4
