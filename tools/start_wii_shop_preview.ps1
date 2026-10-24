<# Start the prepared private Shop profile and its loopback catalog service. #>
[CmdletBinding()]
param(
    [string]$DolphinExe = 'C:\Users\Colin\Desktop\Wii\Dolphin-JWC24-Mail\Dolphin.exe',
    [string]$Profile,
    [switch]$ServerOnly
)
$ErrorActionPreference = 'Stop'
$repoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
if (-not $Profile) { $Profile = Join-Path $repoRoot 'private\wii_shop\preview-profile' }
$Profile = (Resolve-Path -LiteralPath $Profile).Path
$privateRoot = Join-Path $repoRoot 'private'
if (-not $Profile.StartsWith($privateRoot + '\', [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Only a prepared private profile can be launched.'
}
$python = Join-Path $repoRoot '.venv\Scripts\python.exe'
$catalog = Join-Path $repoRoot 'private\wii_shop\mariocube-catalog-ids.json'
$titleMetadata = Join-Path $repoRoot 'private\wii_shop\title-metadata-v2\metadata.json'
$titleArtworkManifest = Join-Path $repoRoot 'private\wii_shop\title-artwork-v4\manifest.json'
$catalogCaptureManifest = Join-Path $repoRoot 'private\wii_shop\frontend-japan-catalog-v2\manifest.private.json'
$markerFile = Join-Path $Profile 'preview-profile.json'
$marker = Get-Content -LiteralPath $markerFile -Raw | ConvertFrom-Json
$content = Join-Path $Profile 'Wii\title\00010002\48414241\content'
foreach ($check in @(@('0000005e.app', $marker.patched_dol_sha256), @('0000005f.app', $marker.patched_archive_sha256))) {
    if ((Get-FileHash -LiteralPath (Join-Path $content $check[0]) -Algorithm SHA256).Hash -ne $check[1]) {
        throw 'Prepared Shop content fingerprint differs; refusing launch.'
    }
}
$ini = Get-Content -LiteralPath (Join-Path $Profile 'Config\Dolphin.ini')
$nandLines = @($ini | Where-Object { $_ -match '^NANDRootPath\s*=' })
if ($nandLines.Count -ne 1 -or [IO.Path]::GetFullPath(($nandLines[0] -split '=',2)[1].Trim()).TrimEnd('\') -ne (Join-Path $Profile 'Wii')) {
    throw 'Profile NAND does not point to its private Wii directory.'
}
if (-not $ServerOnly -and @(Get-Process *Dolphin* -ErrorAction SilentlyContinue).Count) {
    throw 'Dolphin is already running; no existing instance was stopped.'
}
if (-not $ServerOnly) {
    $credentials = Join-Path $Profile 'Wii\keys.bin'
    if (-not (Test-Path -LiteralPath $credentials -PathType Leaf) -or (Get-Item -LiteralPath $credentials).Length -ne 1024) {
        throw 'Prepare your own vWii credentials in the private profile before launching.'
    }
}
$listeners = @(Get-NetTCPConnection -LocalPort 18443 -State Listen -ErrorAction SilentlyContinue)
if (-not $listeners.Count) {
    $logs = Join-Path $Profile 'preview-logs'
    New-Item -ItemType Directory -Path $logs -Force | Out-Null
    $stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssffffZ')
    $arguments = @('-u', '-m', 'jwc24.wii_shop_server', '--catalog', ('"'+$catalog+'"'),
        '--cert', ('"'+(Join-Path $Profile 'tls\server.pem')+'"'),
        '--key', ('"'+(Join-Path $Profile 'tls\server.key')+'"'))
    Start-Process -FilePath $python -ArgumentList $arguments -WorkingDirectory $repoRoot -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $logs "$stamp.stdout.log") -RedirectStandardError (Join-Path $logs "$stamp.stderr.log") | Out-Null
    $listenDeadline = [DateTime]::UtcNow.AddSeconds(15)
    while (-not @(Get-NetTCPConnection -LocalPort 18443 -State Listen -ErrorAction SilentlyContinue).Count) {
        if ([DateTime]::UtcNow -ge $listenDeadline) { throw 'Local Shop preview did not start; inspect the private preview logs.' }
        Start-Sleep -Milliseconds 200
    }
}
Push-Location $repoRoot
try {
    $healthJson = & $python -m jwc24.wii_shop_server --check --root (Join-Path $Profile 'tls\root.pem')
    if ($LASTEXITCODE -ne 0) { throw 'Local TLS preview health check failed; Dolphin was not launched.' }
    $health = $healthJson | ConvertFrom-Json
    if (-not $health.archived_artwork) { throw 'The running service does not have archived Shop artwork enabled.' }
    if (-not $health.native_original_scripts) { throw 'Restart the preview service with the unchanged native Shop scripts pack.' }
    if (-not $health.captured_keyboard_script) { throw 'Restart the preview service with the reviewed captured keyboard script.' }
    if (-not $health.captured_home_layout) { throw 'Restart the preview service with the reviewed historical home layout.' }
    if (-not $health.captured_catalog_layout -or $health.captured_catalog_manifest_sha256 -ne (Get-FileHash -LiteralPath $catalogCaptureManifest -Algorithm SHA256).Hash.ToLowerInvariant()) {
        throw 'Restart the preview service with the matching historical catalog capture.'
    }
    if (-not $health.historical_title_metadata -or $health.historical_title_metadata_sha256 -ne (Get-FileHash -LiteralPath $titleMetadata -Algorithm SHA256).Hash.ToLowerInvariant()) {
        throw 'Restart the preview service with the matching historical title metadata.'
    }
    if ($health.title_artwork_source -ne 'https://archive.org/details/WiiShopChannelBackup' -or $health.title_artwork_manifest_sha256 -ne (Get-FileHash -LiteralPath $titleArtworkManifest -Algorithm SHA256).Hash.ToLowerInvariant()) {
        throw 'Restart the preview service with the matching historical title artwork pack.'
    }
    if ($health.catalog_sha256 -ne (Get-FileHash -LiteralPath $catalog -Algorithm SHA256).Hash.ToLowerInvariant()) {
        throw 'Running preview has a different catalog snapshot.'
    }
} finally { Pop-Location }
if ($ServerOnly) { Write-Output "Local Shop preview ready: $($health.titles) titles"; return }
if (-not (Test-Path -LiteralPath $DolphinExe -PathType Leaf)) { throw 'Dolphin executable is missing.' }
Start-Process -FilePath $DolphinExe -ArgumentList @('-u', ('"'+$Profile+'"'), '-n', '0001000248414241', '-C', 'Dolphin.Movie.DumpFrames=False') `
    -WorkingDirectory (Split-Path -Parent $DolphinExe) -WindowStyle Normal | Out-Null
Write-Output "Started the private Shop preview with $($health.titles) catalog titles."
