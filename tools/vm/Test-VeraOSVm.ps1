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
$buildReceiptPath = Join-Path $artifacts "veraos-build-result.json"
if (-not (Test-Path $kernel)) { throw "Missing VeraOS kernel: $kernel" }
if (-not (Test-Path $rootfs)) { throw "Missing VeraOS rootfs: $rootfs" }
if (-not (Test-Path $buildReceiptPath)) { throw "Missing VeraOS build receipt: $buildReceiptPath" }

$currentHead = (& git -C $repo rev-parse HEAD | Select-Object -First 1)
$sourceStatus = @(& git -C $repo status --porcelain=v1)
if ($sourceStatus.Count -gt 0) {
    throw "VeraOS qualification requires a clean source tree for exact-head provenance"
}

$buildReceipt = Get-Content $buildReceiptPath -Raw | ConvertFrom-Json
if ($buildReceipt.Schema -ne "VERA_OS_BUILDROOT_BUILD_RESULT_V1") {
    throw "Unexpected VeraOS build receipt schema"
}
if ($buildReceipt.SourceHead -ne $currentHead) {
    throw "VeraOS build receipt source head does not match current source head"
}

$buildProfile = [string]$buildReceipt.BuildProfile
$browserPackaged = [bool]$buildReceipt.BrowserPackaged
if ($buildProfile -eq "CORE_BOOT") {
    if ($buildReceipt.Defconfig -ne "veraos_x86_64_defconfig" -or $browserPackaged) {
        throw "CORE_BOOT build receipt is internally inconsistent"
    }
} elseif ($buildProfile -eq "BROWSER") {
    if ($buildReceipt.Defconfig -ne "veraos_x86_64_browser_defconfig" -or -not $browserPackaged) {
        throw "BROWSER build receipt is internally inconsistent"
    }
} else {
    throw "Unknown VeraOS build profile: $buildProfile"
}

$kernelSha256 = ((Get-FileHash $kernel -Algorithm SHA256).Hash.ToLowerInvariant())
$rootfsSha256 = ((Get-FileHash $rootfs -Algorithm SHA256).Hash.ToLowerInvariant())
if ($buildReceipt.KernelSha256 -ne $kernelSha256) { throw "VeraOS kernel hash does not match build receipt" }
if ($buildReceipt.RootfsSha256 -ne $rootfsSha256) { throw "VeraOS rootfs hash does not match build receipt" }
$buildReceiptSha256 = ((Get-FileHash $buildReceiptPath -Algorithm SHA256).Hash.ToLowerInvariant())

$dockerfile = Join-Path $repo "tools\vm\qemu-runner.Dockerfile"
& docker build -t $RunnerImage -f $dockerfile $repo
if ($LASTEXITCODE -ne 0) { throw "QEMU runner image build failed" }

$overlay = Join-Path $logs "veraos-qualification-overlay.qcow2"
Remove-Item $overlay -Force -ErrorAction SilentlyContinue
$qemuImgArgs = @(
    "run", "--rm",
    "--entrypoint", "qemu-img",
    "--mount", "type=bind,source=$artifacts,target=/artifacts,readonly",
    "--mount", "type=bind,source=$logs,target=/logs",
    $RunnerImage,
    "create", "-f", "qcow2", "-F", "raw",
    "-b", "/artifacts/veraos-rootfs.ext2",
    "/logs/veraos-qualification-overlay.qcow2"
)
& docker @qemuImgArgs
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $overlay)) {
    throw "VeraOS disposable qualification overlay creation failed"
}

$append = "root=/dev/vda rw console=ttyS0,115200 init=/sbin/vera-init"
# Windows PowerShell Start-Process joins ArgumentList entries into a command line.
# Quote the QEMU kernel command line explicitly so it remains one docker argument.
$quotedAppend = '"' + $append + '"'
$compositionPath = Join-Path $repo "architecture\portfolio\VERA_OS_PORTFOLIO_COMPOSITION_V1.json"
$implementationPlanPath = Join-Path $repo "architecture\portfolio\VERA_OS_PORTFOLIO_IMPLEMENTATION_PLAN_V1.json"
if (-not (Test-Path $implementationPlanPath)) { throw "Missing VeraOS portfolio implementation plan" }
$sourceComposition = Get-Content $compositionPath -Raw | ConvertFrom-Json
$portfolioTotal = @($sourceComposition.repositories).Count
$portfolioIntegrated = @($sourceComposition.repositories | Where-Object { $_.disposition -eq "INTEGRATED" }).Count
$portfolioExcluded = @($sourceComposition.repositories | Where-Object { $_.disposition -eq "EXCLUDED" }).Count
$expectedBoot = "VERAOS_BOOT_READY_V1 pid=1 base=VERA total=$portfolioTotal integrated=$portfolioIntegrated excluded=$portfolioExcluded portfolio_plan_validated=true cognition_required=false browser_first_class=true ambient_protected_effect_authority=false"

function Invoke-VeraBootPass {
    param(
        [int]$Pass,
        [string]$ExpectedPersistence
    )

    $name = "veraos-vm-qualification-$Pass"
    $existingContainer = (& docker ps -aq --filter "name=^/$name$" | Select-Object -First 1)
    if ($existingContainer) {
        & docker rm -f $existingContainer | Out-Null
    }

    $stdout = Join-Path $logs "veraos-vm-pass$Pass.stdout.log"
    $stderr = Join-Path $logs "veraos-vm-pass$Pass.stderr.log"
    Remove-Item $stdout,$stderr -Force -ErrorAction SilentlyContinue

    $dockerArgs = @(
        "run", "--rm", "--name", $name,
        "--mount", "type=bind,source=$artifacts,target=/artifacts,readonly",
        "--mount", "type=bind,source=$logs,target=/logs",
        $RunnerImage,
        "-m", "$MemoryMiB",
        "-smp", "$CpuCount",
        "-accel", "tcg",
        "-machine", "q35",
        "-kernel", "/artifacts/veraos-bzImage",
        "-drive", "file=/logs/veraos-qualification-overlay.qcow2,format=qcow2,if=virtio",
        "-append", $quotedAppend,
        "-nic", "none",
        "-nographic",
        "-no-reboot"
    )

    $process = Start-Process -FilePath "docker.exe" -ArgumentList $dockerArgs -PassThru -NoNewWindow -RedirectStandardOutput $stdout -RedirectStandardError $stderr
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $bootMarker = $null
    $persistenceMarker = $null

    try {
        while ((Get-Date) -lt $deadline) {
            $text = ""
            if (Test-Path $stdout) { $text += Get-Content $stdout -Raw -ErrorAction SilentlyContinue }
            if (Test-Path $stderr) { $text += Get-Content $stderr -Raw -ErrorAction SilentlyContinue }
            if ($text -match [regex]::Escape($expectedBoot)) {
                $bootMarker = $expectedBoot
            }
            if ($text -match [regex]::Escape($ExpectedPersistence)) {
                $persistenceMarker = $ExpectedPersistence
            }
            if ($bootMarker -and $persistenceMarker) {
                break
            }
            if ($process.HasExited) { break }
            Start-Sleep -Milliseconds 500
            $process.Refresh()
        }
    }
    finally {
        $runningContainer = (& docker ps -q --filter "name=^/$name$" | Select-Object -First 1)
        if ($runningContainer) {
            & docker stop -t 1 $runningContainer | Out-Null
        }
        if (-not $process.HasExited) { $process.WaitForExit(5000) | Out-Null }
    }

    if (-not $bootMarker -or -not $persistenceMarker) {
        $tail = ""
        if (Test-Path $stdout) { $tail += (Get-Content $stdout -Tail 160 | Out-String) }
        if (Test-Path $stderr) { $tail += (Get-Content $stderr -Tail 160 | Out-String) }
        throw "VeraOS VM qualification pass $Pass markers not observed. Tail: $tail"
    }

    [pscustomobject]@{
        pass = $Pass
        boot_marker = $bootMarker
        persistence_marker = $persistenceMarker
        stdout = $stdout
        stderr = $stderr
    }
}

$firstPersistence = "VERAOS_PERSISTENCE_READY_V1 boot_ordinal=1 previous_boot_ordinal=0 canonical_memory=false supabase_replacement=false"
$secondPersistence = "VERAOS_PERSISTENCE_READY_V1 boot_ordinal=2 previous_boot_ordinal=1 canonical_memory=false supabase_replacement=false"
$firstBoot = Invoke-VeraBootPass -Pass 1 -ExpectedPersistence $firstPersistence
$secondBoot = Invoke-VeraBootPass -Pass 2 -ExpectedPersistence $secondPersistence

$qemuVersion = (& docker run --rm $RunnerImage --version | Select-Object -First 1)

$receipt = [ordered]@{
    schema = "VERA_OS_VM_QUALIFICATION_V3"
    qualified = $true
    observed_at = (Get-Date).ToString("o")
    product_base = "VERA"
    linux_role = "KERNEL_DRIVER_HARDWARE_SUBSTRATE"
    image_builder = "BUILDROOT_2024_02_4"
    source_head = $currentHead
    source_tree_clean = $true
    build_receipt_sha256 = $buildReceiptSha256
    kernel_sha256 = $kernelSha256
    rootfs_sha256 = $rootfsSha256
    qemu = $qemuVersion
    acceleration = "TCG_SOFTWARE_EMULATION"
    network = "NONE"
    memory_mib = $MemoryMiB
    cpu_count = $CpuCount
    marker = $secondBoot.boot_marker
    portfolio_total = $portfolioTotal
    portfolio_integrated = $portfolioIntegrated
    portfolio_excluded = $portfolioExcluded
    portfolio_implementation_plan_validated = $true
    lifecycle_persistence_marker = $secondBoot.persistence_marker
    lifecycle_persistence_qualified = $true
    restart_persistence_qualified = $true
    restart_boot_passes = 2
    persistence_markers = @(
        $firstBoot.persistence_marker,
        $secondBoot.persistence_marker
    )
    canonical_memory_qualified = $false
    supabase_replacement_qualified = $false
    qualification_disk = "DISPOSABLE_QCOW2_OVERLAY"
    build_profile = $buildProfile
    browser_packaged = $browserPackaged
    browser_profile_defconfig = "veraos_x86_64_browser_defconfig"
    browser_runtime_qualified = $false
    ambient_protected_effect_authority = $false
    host_partition_table_modified = $false
    claim_ceiling = "VM_BOOT_RESTART_LIFECYCLE_PERSISTENCE_GUEST_COMPOSITION_AND_PORTFOLIO_IMPLEMENTATION_PLAN_VALIDATION_ONLY_NOT_CANONICAL_MEMORY_NOT_SUPABASE_REPLACEMENT_NOT_BROWSER_RUNTIME_NOT_BARE_METAL_NOT_PROTECTED_EFFECT"
}

$receiptPath = Join-Path $artifacts "veraos-vm-qualification.json"
$receipt | ConvertTo-Json -Depth 6 | Set-Content -Encoding UTF8 $receiptPath
$receipt | ConvertTo-Json -Depth 6
