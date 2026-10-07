param(
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")),
    [string]$ArtifactRoot = "D:\VeraOS\vm\artifacts",
    [string]$LogRoot = "D:\VeraOS\vm\logs",
    [int]$TimeoutSeconds = 300,
    [int]$MemoryMiB = 12288,
    [int]$CpuCount = 4,
    [string]$RunnerImage = "veraos-qemu-runner:local"
)

$ErrorActionPreference = "Stop"

$repo = [System.IO.Path]::GetFullPath($RepoRoot)
$artifacts = [System.IO.Path]::GetFullPath($ArtifactRoot)
$logs = [System.IO.Path]::GetFullPath($LogRoot)
New-Item -ItemType Directory -Force $logs | Out-Null

$kernel = Join-Path $artifacts "veraos-bzImage"
$rootfs = Join-Path $artifacts "veraos-rootfs.ext2"
if (-not (Test-Path $kernel)) { throw "Missing VeraOS kernel: $kernel" }
if (-not (Test-Path $rootfs)) { throw "Missing VeraOS rootfs: $rootfs" }

$dockerfile = Join-Path $repo "tools\vm\qemu-runner.Dockerfile"
& docker build -t $RunnerImage -f $dockerfile $repo
if ($LASTEXITCODE -ne 0) { throw "QEMU runner image build failed" }

$name = "veraos-vm-qualification"
& docker rm -f $name *> $null

$stdout = Join-Path $logs "veraos-vm.stdout.log"
$stderr = Join-Path $logs "veraos-vm.stderr.log"
Remove-Item $stdout,$stderr -Force -ErrorAction SilentlyContinue

$append = "root=/dev/vda rw console=ttyS0,115200 init=/sbin/vera-init"
# Windows PowerShell Start-Process joins ArgumentList entries into a command line.
# Quote the QEMU kernel command line explicitly so it remains one docker argument.
$quotedAppend = '"' + $append + '"'
$dockerArgs = @(
    "run", "--rm", "--name", $name,
    "--mount", "type=bind,source=$artifacts,target=/artifacts,readonly",
    $RunnerImage,
    "-m", "$MemoryMiB",
    "-smp", "$CpuCount",
    "-accel", "tcg",
    "-machine", "q35",
    "-kernel", "/artifacts/veraos-bzImage",
    "-drive", "file=/artifacts/veraos-rootfs.ext2,format=raw,if=virtio",
    "-append", $quotedAppend,
    "-nic", "none",
    "-nographic",
    "-no-reboot"
)

$process = Start-Process -FilePath "docker.exe" -ArgumentList $dockerArgs -PassThru -NoNewWindow -RedirectStandardOutput $stdout -RedirectStandardError $stderr

$expected = "VERAOS_BOOT_READY_V1 pid=1 base=VERA total=84 integrated=79 excluded=5 cognition_required=false browser_first_class=true ambient_protected_effect_authority=false"
$deadline = (Get-Date).AddSeconds($TimeoutSeconds)
$marker = $null

try {
    while ((Get-Date) -lt $deadline) {
        $text = ""
        if (Test-Path $stdout) { $text += Get-Content $stdout -Raw -ErrorAction SilentlyContinue }
        if (Test-Path $stderr) { $text += Get-Content $stderr -Raw -ErrorAction SilentlyContinue }
        if ($text -match [regex]::Escape($expected)) {
            $marker = $expected
            break
        }
        if ($process.HasExited) { break }
        Start-Sleep -Milliseconds 500
        $process.Refresh()
    }
}
finally {
    & docker stop -t 1 $name *> $null
    if (-not $process.HasExited) { $process.WaitForExit(5000) | Out-Null }
}

if (-not $marker) {
    $tail = ""
    if (Test-Path $stdout) { $tail += (Get-Content $stdout -Tail 160 | Out-String) }
    if (Test-Path $stderr) { $tail += (Get-Content $stderr -Tail 160 | Out-String) }
    throw "VeraOS VM qualification marker not observed. Tail: $tail"
}

$qemuVersion = (& docker run --rm $RunnerImage --version | Select-Object -First 1)

$receipt = [ordered]@{
    schema = "VERA_OS_VM_QUALIFICATION_V2"
    qualified = $true
    observed_at = (Get-Date).ToString("o")
    product_base = "VERA"
    linux_role = "KERNEL_DRIVER_HARDWARE_SUBSTRATE"
    image_builder = "BUILDROOT_2024_02_4"
    kernel_sha256 = ((Get-FileHash $kernel -Algorithm SHA256).Hash.ToLowerInvariant())
    rootfs_sha256 = ((Get-FileHash $rootfs -Algorithm SHA256).Hash.ToLowerInvariant())
    qemu = $qemuVersion
    acceleration = "TCG_SOFTWARE_EMULATION"
    network = "NONE"
    memory_mib = $MemoryMiB
    cpu_count = $CpuCount
    marker = $marker
    build_profile = "CORE_BOOT"
    browser_packaged = $false
    browser_profile_defconfig = "veraos_x86_64_browser_defconfig"
    browser_runtime_qualified = $false
    ambient_protected_effect_authority = $false
    host_partition_table_modified = $false
    claim_ceiling = "VM_BOOT_AND_GUEST_COMPOSITION_VALIDATION_ONLY_NOT_BROWSER_RUNTIME_NOT_BARE_METAL_NOT_PROTECTED_EFFECT"
}

$receiptPath = Join-Path $artifacts "veraos-vm-qualification.json"
$receipt | ConvertTo-Json -Depth 6 | Set-Content -Encoding UTF8 $receiptPath
$receipt | ConvertTo-Json -Depth 6
