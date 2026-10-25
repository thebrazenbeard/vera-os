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

function Assert-NoLinkedAncestor {
    param([string]$Path)
    $cursor = [System.IO.Path]::GetFullPath($Path)
    while ($cursor) {
        $item = Get-Item -LiteralPath $cursor -Force -ErrorAction SilentlyContinue
        if ($item -and (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0)) {
            throw "Linked/junction path not admitted for VM qualification: $cursor"
        }
        $parent = [System.IO.Path]::GetDirectoryName($cursor)
        if (-not $parent -or $parent -eq $cursor) { break }
        $cursor = $parent
    }
}

Assert-NoLinkedAncestor $repo
Assert-NoLinkedAncestor $artifacts
Assert-NoLinkedAncestor $logs
New-Item -ItemType Directory -Force $logs | Out-Null
Assert-NoLinkedAncestor $logs
if (-not (Test-Path -LiteralPath $artifacts -PathType Container)) {
    throw "Missing VeraOS artifact directory: $artifacts"
}

# Every invocation owns a new log directory and Docker identity. Never delete
# or truncate evidence from a prior run or a same-named ambient container.
$runId = [guid]::NewGuid().ToString("N")
$runLogs = Join-Path $logs "veraos-qualification-$runId"
if (Test-Path -LiteralPath $runLogs) { throw "Run directory collision: $runLogs" }
New-Item -ItemType Directory -Path $runLogs -ErrorAction Stop | Out-Null
Assert-NoLinkedAncestor $runLogs

$kernel = Join-Path $artifacts "veraos-bzImage"
$rootfs = Join-Path $artifacts "veraos-rootfs.ext2"
$buildReceiptPath = Join-Path $artifacts "veraos-build-result.json"
if (-not (Test-Path $kernel)) { throw "Missing VeraOS kernel: $kernel" }
if (-not (Test-Path $rootfs)) { throw "Missing VeraOS rootfs: $rootfs" }
if (-not (Test-Path $buildReceiptPath)) { throw "Missing VeraOS build receipt: $buildReceiptPath" }

# Exact built source is earlier than the qualification-tooling commit.
# Refuse a guest boot on any branch that has changed Buildroot or runtime code.
$validator = Join-Path $repo "tools\vm\Verify-VeraOSBuildSource.py"
$imageSource = "a2a91017876df7ca1677ad4afefd7b45dd80165f"
$bound = & python $validator --repo-root $repo --image-source-head $imageSource
if ($LASTEXITCODE -ne 0) {
    throw "VeraOS image source is not an exact unchanged ancestor"
}
$binding = ($bound | Out-String | ConvertFrom-Json)
$currentHead = $binding.qualification_tool_head

$buildReceipt = Get-Content $buildReceiptPath -Raw | ConvertFrom-Json
if ($buildReceipt.Schema -ne "VERA_OS_BUILDROOT_BUILD_RESULT_V1") {
    throw "Unexpected VeraOS build receipt schema"
}
if ($buildReceipt.SourceHead -ne $imageSource -or
    $buildReceipt.QualificationToolHead -ne $currentHead -or
    -not $buildReceipt.ImageBuildSourceUnchanged) {
    throw "VeraOS image build source and current qualification-tooling head are not cross-bound"
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
} elseif ($buildProfile -eq "RESIDENT_BROWSER") {
    if ($buildReceipt.Defconfig -ne "veraos_x86_64_resident_browser_defconfig" -or
        $buildReceipt.BuildrootVersion -ne "2025.02.18" -or
        $buildReceipt.BuildrootCommit -ne "d030e36bbc9669230c015be971b14b6e062cfdde" -or
        -not $browserPackaged -or
        $buildReceipt.ResidentCoreSourceStaged -ne $true -or
        $buildReceipt.ResidentCoreImportQualified -ne $false) {
        throw "RESIDENT_BROWSER build receipt is inconsistent or overclaims runtime"
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
# Never replace a globally shared mutable runner tag. Resolve the unique
# build tag to an immutable image ID and run by ID for all qualification steps.
$runnerTag = "$RunnerImage-$runId"
& docker build -t $runnerTag -f $dockerfile $repo
if ($LASTEXITCODE -ne 0) { throw "QEMU runner image build failed" }
$runnerImageId = [string](& docker image inspect --format '{{.Id}}' $runnerTag | Select-Object -First 1)
$runnerImageId = $runnerImageId.Trim()
if ($LASTEXITCODE -ne 0 -or $runnerImageId -notmatch '^sha256:[0-9a-f]{64}$') {
    throw "QEMU runner image has no immutable Docker image ID"
}

$overlay = Join-Path $runLogs "veraos-qualification-overlay.qcow2"
$qemuImgArgs = @(
    "run", "--rm", "--network", "none",
    "--entrypoint", "qemu-img",
    "--mount", "type=bind,source=$artifacts,target=/artifacts,readonly",
    "--mount", "type=bind,source=$runLogs,target=/logs",
    $runnerImageId,
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

    $name = "veraos-vm-$runId-$Pass"
    $cidPath = Join-Path $runLogs "pass$Pass.cid"
    $stdout = Join-Path $runLogs "veraos-vm-pass$Pass.stdout.log"
    $stderr = Join-Path $runLogs "veraos-vm-pass$Pass.stderr.log"

    $dockerArgs = @(
        "run", "--rm", "--network", "none",
        "--cidfile", $cidPath, "--name", $name,
        "--label", "veraos.qualifier.run=$runId",
        "--mount", "type=bind,source=$artifacts,target=/artifacts,readonly",
        "--mount", "type=bind,source=$runLogs,target=/logs",
        $runnerImageId,
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
    $dwellStart = $null
    $dwellQualified = $false
    $fatalMarker = $false

    $ownedContainerId = $null
    try {
        while ((Get-Date) -lt $deadline) {
            $text = ""
            if (Test-Path $stdout) { $text += Get-Content $stdout -Raw -ErrorAction SilentlyContinue }
            if (Test-Path $stderr) { $text += Get-Content $stderr -Raw -ErrorAction SilentlyContinue }
            if ($text -match '(?im)Kernel panic|Oops:|BUG: unable to handle kernel') {
                $fatalMarker = $true
                break
            }
            if ($text -match [regex]::Escape($expectedBoot)) {
                $bootMarker = $expectedBoot
            }
            if ($text -match [regex]::Escape($ExpectedPersistence)) {
                $persistenceMarker = $ExpectedPersistence
            }
            if ($bootMarker -and $persistenceMarker) {
                # A marker printed immediately before a crash is not a
                # qualified boot. Require five seconds of continued process
                # liveness after both markers are present.
                if ($process.HasExited) { break }
                if (-not $dwellStart) { $dwellStart = Get-Date }
                if (((Get-Date) - $dwellStart).TotalSeconds -ge 5) {
                    $dwellQualified = $true
                    break
                }
            }
            if ($process.HasExited) { break }
            Start-Sleep -Milliseconds 500
            $process.Refresh()
        }
    }
    finally {
        # --cidfile is created by Docker for our unique run. Cleanup must use
        # only this exact ID, never a name filter that could match someone
        # else's container.
        if (Test-Path -LiteralPath $cidPath) {
            $candidateId = [IO.File]::ReadAllText($cidPath).Trim()
            if ($candidateId -match '^[0-9a-f]{64}$') { $ownedContainerId = $candidateId }
        }
        if ($ownedContainerId) {
            # JSON avoids Windows PowerShell native-argument quoting of a
            # double-quoted Go-template map key.
            $labelsJson = [string](& docker inspect --format '{{json .Config.Labels}}' $ownedContainerId 2>$null | Select-Object -First 1)
            if ($LASTEXITCODE -eq 0 -and $labelsJson) {
                $labels = $labelsJson | ConvertFrom-Json
                if ($labels.'veraos.qualifier.run' -eq $runId) {
                    & docker stop -t 1 $ownedContainerId | Out-Null
                }
            }
        }
        if (-not $process.HasExited) {
            $finished = $process.WaitForExit(5000)
            $process.Refresh()
            if (-not $finished -or -not $process.HasExited) {
                throw "VM qualification Docker process remained live after owned cleanup"
            }
        }
    }

    if (-not $ownedContainerId -or -not $bootMarker -or -not $persistenceMarker -or
        -not $dwellQualified -or $fatalMarker) {
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
        stdout_sha256 = ((Get-FileHash $stdout -Algorithm SHA256).Hash.ToLowerInvariant())
        stderr_sha256 = ((Get-FileHash $stderr -Algorithm SHA256).Hash.ToLowerInvariant())
    }
}

$firstPersistence = "VERAOS_PERSISTENCE_READY_V1 boot_ordinal=1 previous_boot_ordinal=0 canonical_memory=false supabase_replacement=false"
$secondPersistence = "VERAOS_PERSISTENCE_READY_V1 boot_ordinal=2 previous_boot_ordinal=1 canonical_memory=false supabase_replacement=false"
$firstBoot = Invoke-VeraBootPass -Pass 1 -ExpectedPersistence $firstPersistence
$secondBoot = Invoke-VeraBootPass -Pass 2 -ExpectedPersistence $secondPersistence

$qemuVersion = (& docker run --rm --network none $runnerImageId --version | Select-Object -First 1)
if ($LASTEXITCODE -ne 0) { throw "QEMU runner version query failed" }

$receiptPath = Join-Path $artifacts "veraos-vm-qualification-$runId.json"
$receipt = [ordered]@{
    schema = "VERA_OS_VM_QUALIFICATION_V3"
    qualified = $true
    observed_at = (Get-Date).ToString("o")
    run_id = $runId
    receipt_path = $receiptPath
    run_log_root = $runLogs
    host_log_acl_qualified = $false
    runner_image_tag = $runnerTag
    runner_image_id = $runnerImageId
    runner_image_source_attestation_qualified = $false
    product_base = "VERA"
    linux_role = "KERNEL_DRIVER_HARDWARE_SUBSTRATE"
    image_builder = ("BUILDROOT_" + ([string]$buildReceipt.BuildrootVersion).Replace(".", "_"))
    source_head = $imageSource
    qualification_tool_head = $currentHead
    image_build_source_unchanged = $true
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
    pass_logs = @(
        [ordered]@{
            stdout = $firstBoot.stdout; stderr = $firstBoot.stderr
            stdout_sha256 = $firstBoot.stdout_sha256; stderr_sha256 = $firstBoot.stderr_sha256
        },
        [ordered]@{
            stdout = $secondBoot.stdout; stderr = $secondBoot.stderr
            stdout_sha256 = $secondBoot.stdout_sha256; stderr_sha256 = $secondBoot.stderr_sha256
        }
    )
    canonical_memory_qualified = $false
    supabase_replacement_qualified = $false
    qualification_disk = "DISPOSABLE_QCOW2_OVERLAY"
    build_profile = $buildProfile
    browser_packaged = $browserPackaged
    browser_profile_defconfig = [string]$buildReceipt.BrowserProfileDefconfig
    resident_core_source_staged = $buildProfile -eq "RESIDENT_BROWSER"
    resident_core_import_qualified = $false
    resident_runtime_qualified = $false
    trained_model_route_qualified = $false
    offline_portfolio_guest_mount_qualified = $false
    browser_runtime_qualified = $false
    ambient_protected_effect_authority = $false
    host_partition_table_modified = $false
    claim_ceiling = "VM_BOOT_RESTART_LIFECYCLE_PERSISTENCE_GUEST_COMPOSITION_AND_PORTFOLIO_PLAN_ONLY_NOT_RESIDENT_IMPORT_NOT_COG_RENDER_NOT_LOCAL_MODEL_NOT_OFFLINE_PORTFOLIO_MOUNT_NOT_BARE_METAL_NOT_PROTECTED_EFFECT"
}

# Create a new immutable evidence file: an existing receipt, including a
# symlink, must fail instead of being truncated. The caller receives its path.
$json = $receipt | ConvertTo-Json -Depth 6
$payload = [System.Text.UTF8Encoding]::new($false).GetBytes($json + [Environment]::NewLine)
$receiptFile = [IO.File]::Open($receiptPath, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
try {
    $receiptFile.Write($payload, 0, $payload.Length)
    $receiptFile.Flush($true)
}
finally {
    $receiptFile.Dispose()
}
$json
