param([Parameter(Mandatory = $true)][string]$RepoRoot)
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

# Static pin consistency only: never imports or executes resident components.
$paths = @(
    "architecture/portfolio/VERA_OS_PORTFOLIO_COMPOSITION_V1.json",
    "architecture/capabilities/VERA_OS_PORTFOLIO_CAPABILITY_MAP_V1.json",
    "architecture/portfolio/VERA_OS_PORTFOLIO_IMPLEMENTATION_PLAN_V1.json"
)
$inventories = @()
foreach ($relative in $paths) {
    $path = Join-Path $RepoRoot $relative
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Missing resident boot source manifest: $relative"
    }
    $document = Get-Content -LiteralPath $path -Raw -Encoding UTF8 | ConvertFrom-Json
    $rows = @($document.repositories)
    if ($rows.Count -eq 0 -or $null -eq $document.repositories) {
        throw "Empty resident boot source inventory: $relative"
    }
    $heads = @{}
    foreach ($row in $rows) {
        $name = [string]$row.repository
        $head = [string]$row.exact_head
        if ($name -notmatch '^[^/]+/[^/]+$' -or
            $head -cnotmatch '^[0-9a-f]{40}$') {
            throw "Invalid resident boot source binding in $relative"
        }
        if ($heads.ContainsKey($name)) {
            throw "Duplicate resident boot source repository: $name"
        }
        $heads[$name] = $head
    }
    $inventories += ,$heads
}
$expected = $inventories[0]
foreach ($other in $inventories[1..2]) {
    if ($other.Count -ne $expected.Count) {
        throw "Resident boot source inventory count mismatch"
    }
    foreach ($repository in $expected.Keys) {
        if (-not $other.ContainsKey($repository) -or
            $other[$repository] -cne $expected[$repository]) {
            throw "Resident boot exact-head mismatch: $repository"
        }
    }
}
Write-Output "VERAOS_BOOT_PINSET_ALIGNED_V1 repositories=$($expected.Count) static_only=true"
