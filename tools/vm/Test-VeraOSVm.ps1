param(
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\\..")),
    [string]$ArtifactRoot = "D:\\VeraOS\\vm\\artifacts",
    [string]$LogRoot = "D:\\VeraOS\\vm\\logs",
    [int]$TimeoutSeconds = 300,
    [string]$RunnerImage = "veraos-qemu-runner:local"
)

$ErrorActionPreference = "Stop"

$repo = [System.IO.Path]::GetFullPath($RepoRoot)
$artifacts = [System.IO.Path]::GetFullPath($ArtifactRoot)
$logs = [System.IO.Path]::GetFullPath($LogRoot)

New-Item -ItemType Directory -Force $logs | Out-Null

$iso = Join-Path $artifacts "veraos-vm.iso"
if (-not (Test-Path $iso)) {
    throw "Missing VeraOS ISO: $iso"
}

$dockerfile = Join-Path $repo "tools\\vm\\qemu-runner.Dockerfile"
& docker build -t $RunnerImage -f $dockerfile $repo
if ($LASTEXITCODE -ne 0) {
    throw "QEMU runner image build failed"
}

$name = "veraos-vm-qualification"
& docker rm -f $name *> $null

$stdout = Join-Path $logs "veraos-vm.stdout.log"
$stderr = Join-Path $logs "veraos-vm.stderr.log"
Remove-Item $stdout,$stderr -Force -ErrorAction SilentlyContinue

$dockerArgs = @(
    "run",
    "--rm",
    "--name", $name,
    "--mount", "type=bind,source=$artifacts,target=/artifacts,readonly",
    $RunnerImage,
    "-m", "2048",
    "-smp", "2",
    "-accel", "tcg",
    "-machine", "q35",
    "-cdrom", "/artifacts/veraos-vm.iso",
    "-boot", "d",
    "-nic", "none",
    "-nographic",
    "-no-reboot"
)

$process = Start-Process -FilePath "docker.exe" -ArgumentList $dockerArgs -PassThru -NoNewWindow -RedirectStandardOutput $stdout -RedirectStandardError $stderr

$expected = "VERAOS_VM_BOOT_OK total=84 integrated=79 excluded=5 ambient_protected_effect_authority=false"
$deadline = (Get-Date).AddSeconds($TimeoutSeconds)
$marker = $null

try {
    while ((Get-Date) -lt $deadline) {
        $text = ""
        if (Test-Path $stdout) {
            $text += Get-Content $stdout -Raw -ErrorAction SilentlyContinue
        }
        if (Test-Path $stderr) {
            $text += Get-Content $stderr -Raw -ErrorAction SilentlyContinue
        }

        if ($text -match [regex]::Escape($expected)) {
            $marker = $expected
            break
        }

        if ($process.HasExited) {
            break
        }

        Start-Sleep -Milliseconds 500
        $process.Refresh()
    }
}
finally {
    & docker stop -t 1 $name *> $null
    if (-not $process.HasExited) {
        $process.WaitForExit(5000) | Out-Null
    }
}

if (-not $marker) {
    $tail = ""
    if (Test-Path $stdout) {
        $tail += (Get-Content $stdout -Tail 120 | Out-String)
    }
    if (Test-Path $stderr) {
        $tail += (Get-Content $stderr -Tail 120 | Out-String)
    }
    throw "VeraOS VM qualification marker not observed. Tail: $tail"
}

$qemuVersion = (& docker run --rm $RunnerImage --version | Select-Object -First 1)

$receipt = [ordered]@{
    schema = "VERA_OS_VM_QUALIFICATION_V1"
    qualified = $true
    observed_at = (Get-Date).ToString("o")
    iso = $iso
    iso_sha256 = ((Get-FileHash $iso -Algorithm SHA256).Hash.ToLowerInvariant())
    qemu = $qemuVersion
    acceleration = "TCG_SOFTWARE_EMULATION"
    network = "NONE"
    marker = $marker
    portfolio_total = 84
    portfolio_integrated = 79
    portfolio_excluded = 5
    ambient_protected_effect_authority = $false
    host_partition_table_modified = $false
    claim_ceiling = "VM_BOOT_AND_GUEST_COMPOSITION_VALIDATION_ONLY_NOT_BARE_METAL_INSTALL_NOT_RUNTIME_EFFECT_AUTHORITY"
}

$receiptPath = Join-Path $artifacts "veraos-vm-qualification.json"
$receipt | ConvertTo-Json -Depth 6 | Set-Content -Encoding UTF8 $receiptPath
$receipt | ConvertTo-Json -Depth 6
