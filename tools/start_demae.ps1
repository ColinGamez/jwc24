<# Launch the current Demae experiment in the existing shared Dolphin profile.
   Does not create another profile or overwrite controller/network settings. #>
[CmdletBinding()]
param(
    [string]$DolphinExe = 'C:\Users\Colin\Desktop\Wii\Dolphin-JWC24-Mail\Dolphin-JWC24-Mail.exe',
    [switch]$PhoneOrdering,
    [switch]$PhoneQrDiagnostic,
    [switch]$DirectoryPreview,
    [switch]$TownParserCapture
)
$ErrorActionPreference = 'Stop'
$repoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$sharedProfile = Join-Path $env:APPDATA 'Dolphin Emulator'
$pythonExe = Join-Path $repoRoot '.venv\Scripts\python.exe'
if ($TownParserCapture -and -not $DirectoryPreview) {
    throw 'TownParserCapture requires DirectoryPreview.'
}
if ($DirectoryPreview -and ($PhoneOrdering -or $PhoneQrDiagnostic)) {
    throw 'DirectoryPreview cannot be combined with phone launch modes.'
}
$testWad = Join-Path $repoRoot 'private\demae\phone-native\HCHJ-native-flow-restored-v8.wad'
if (-not (Test-Path -LiteralPath $testWad -PathType Leaf) -or
    (Get-FileHash -LiteralPath $testWad -Algorithm SHA256).Hash -ne 'de1b89de5a67fddff6841ad616fff596b1dd1de20db7db5fc48ac41203c3290a') {
    throw 'Restored native-flow WAD is missing or its fingerprint does not match.'
}
if ($PhoneOrdering) {
    Write-Warning 'Checkout handoff is not integrated yet. Launching the native restaurant flow; the home button will not open a QR shortcut.'
}
if ($DirectoryPreview) {
    $testWad = Join-Path $repoRoot 'private\demae\phone-native\HCHJ-directory-modal-candidate-v7.wad'
    if (-not (Test-Path -LiteralPath $testWad -PathType Leaf) -or
        (Get-FileHash -LiteralPath $testWad -Algorithm SHA256).Hash -ne 'f7e05616eb367c7ec83ff3fef13a69859e305c12c170d5614112441d9add92b1') {
        throw 'Directory preview WAD is missing or its fingerprint does not match.'
    }
}
if ($PhoneQrDiagnostic) {
    $testWad = Join-Path $repoRoot 'private\demae\phone-native\HCHJ-phone-modal-v7.wad'
    if (-not (Test-Path -LiteralPath $testWad -PathType Leaf)) { throw 'Phone modal WAD is not built.' }
    if ((Get-FileHash -LiteralPath $testWad -Algorithm SHA256).Hash -ne 'bd9db4a57aa51de74360c4335682f07f2fab5c316b78d5daafd1aef80a5edba1') {
        throw 'Phone modal WAD fingerprint does not match the staged build.'
    }
    $entryFile = Join-Path $repoRoot 'private\demae\phone-entry-url.txt'
    try {
        $phoneOrigin = ([Uri](Get-Content -LiteralPath $entryFile -Raw)).GetLeftPart([UriPartial]::Authority)
        $phoneHealth = Invoke-WebRequest -UseBasicParsing -Uri ($phoneOrigin + '/health') -TimeoutSec 2
        $mailHealth = Invoke-RestMethod -Uri 'http://127.0.0.1:8081/healthz' -TimeoutSec 2
        if ($phoneHealth.StatusCode -ne 200 -or $phoneHealth.Content -ne 'JWC24 Demae phone handoff ready' -or $mailHealth.status -ne 'ok' -or $mailHealth.service -ne 'mail') {
            throw 'Service health mismatch'
        }
    } catch { throw 'Phone handoff and shared mail services must be ready before this launch.' }
}
$postalDatabase = Join-Path $repoRoot 'private\demae\postal\postal.sqlite'
foreach ($file in @($DolphinExe, $pythonExe, $testWad, (Join-Path $sharedProfile 'Config\Dolphin.ini'))) {
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { throw "Missing required file: $file" }
}
$runningDolphins = @(Get-CimInstance Win32_Process | Where-Object { $_.Name -like 'Dolphin*.exe' })
if ($runningDolphins.Count) { throw 'Dolphin is already running; no existing instance was stopped.' }
$listeners = @(Get-NetTCPConnection -LocalPort 18085 -State Listen -ErrorAction SilentlyContinue)
foreach ($listener in $listeners) {
    $owner = Get-CimInstance Win32_Process -Filter "ProcessId=$($listener.OwningProcess)"
    if (-not $owner.CommandLine.Contains('demae_fixture_server.py')) { throw 'Fixture port belongs to another process.' }
}
foreach ($ownerId in @($listeners | Select-Object -ExpandProperty OwningProcess -Unique)) {
    Stop-Process -Id $ownerId
}
$logPrefix = Join-Path $repoRoot ('private\demae\fixtures\server-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
$fixtureArguments = 'tools/demae_fixture_server.py --port 18085'
if (Test-Path -LiteralPath $postalDatabase -PathType Leaf) {
    $fixtureArguments += ' --postal-database "' + $postalDatabase + '"'
}
if ($DirectoryPreview) {
    $registry = Join-Path $repoRoot 'private\demae\postal\replacement-area-registry.json'
    $catalogs = Join-Path $repoRoot 'private\demae\hotpepper'
    $directoryDatabase = Join-Path $repoRoot 'private\demae\demae.sqlite'
    if (Test-Path -LiteralPath $catalogs -PathType Container) {
        & $pythonExe (Join-Path $repoRoot 'tools\build_demae_database.py')
        if ($LASTEXITCODE -ne 0) { throw 'Demae database refresh failed; existing archive was retained.' }
    }
    foreach ($required in @($postalDatabase, $registry, $directoryDatabase)) {
        if (-not (Test-Path -LiteralPath $required)) { throw "Missing directory preview input: $required" }
    }
    $fixtureArguments += ' --town-registry "' + $registry + '" --directory-database "' + $directoryDatabase + '" --directory-all-shops'
    $imageCache = Join-Path $repoRoot 'private\demae\directory-image-cache'
    $fixtureArguments += ' --directory-image-cache "' + $imageCache + '"'
}
Start-Process -FilePath $pythonExe -ArgumentList $fixtureArguments -WorkingDirectory $repoRoot -WindowStyle Hidden -RedirectStandardOutput ($logPrefix + '.stdout.log') -RedirectStandardError ($logPrefix + '.stderr.log') | Out-Null
$fixtureReady = $false
$readinessTimer = [Diagnostics.Stopwatch]::StartNew()
while ($readinessTimer.Elapsed.TotalSeconds -lt 90) {
    try {
        $reply = Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:18085/nwapi.php?action=webApi_Authkey&platform=wii' -TimeoutSec 1
        if ($reply.StatusCode -eq 200 -and $reply.Headers['X-JWC24-Scope'] -eq 'synthetic-offline-fixture') {
            $health = Invoke-RestMethod -Uri 'http://127.0.0.1:18085/health' -TimeoutSec 1
            $expectedPrefectures = 0
            if (Test-Path -LiteralPath $postalDatabase -PathType Leaf) { $expectedPrefectures = 47 }
            if ($health.service -ne 'jwc24-demae-fixture' -or $health.schema_version -ne 1 -or $health.municipality_prefectures -ne $expectedPrefectures) {
                throw 'Fixture capabilities do not match this launch.'
            }
            if ($DirectoryPreview -and (-not $health.town_navigation -or -not $health.directory_categories -or -not $health.directory_shop_preview -or $health.ordering_supported)) {
                throw 'Directory preview service capabilities do not match the read-only client.'
            }
            if ($DirectoryPreview -and $health.directory_image_sources -lt 1) {
                throw 'Directory preview image backend is not configured.'
            }
            if ($DirectoryPreview -and (-not $health.directory_all_shops -or $health.directory_restaurants -lt 1)) {
                throw 'Catalog-wide directory responses are not configured.'
            }
            $fixtureReady = $true
            break
        }
    } catch { }
    Start-Sleep -Milliseconds 100
}
$readinessTimer.Stop()
if (-not $fixtureReady) { throw 'Updated fixture server did not become ready; Dolphin was not started.' }
$dolphinArguments = @('-u', ('"' + $sharedProfile + '"'), '-e', ('"' + $testWad + '"'), '-C', 'Dolphin.General.GDBPort=-1')
if ($TownParserCapture) {
    if (Get-NetTCPConnection -LocalPort 55020 -State Listen -ErrorAction SilentlyContinue) {
        throw 'Town-parser diagnostic port is already in use.'
    }
    $dolphinArguments[-1] = 'Dolphin.General.GDBPort=55020'
    $capturePrefix = Join-Path $repoRoot ('private\demae\town-capture-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
    $captureArguments = 'tools/capture_dolphin_error.py --port 55020 --timeout 300 --breakpoint 0x800D7E90 --pointer-bytes 1024 --register-memory r3:0:0xE00 --register-memory r1:0:0x1000 --memory 0x800000D0:0x40 --memory 0x803C5590:0x100 --output "' + $capturePrefix + '.json"'
    Start-Process -FilePath $pythonExe -ArgumentList $captureArguments -WorkingDirectory $repoRoot -WindowStyle Hidden -RedirectStandardOutput ($capturePrefix + '.stdout.log') -RedirectStandardError ($capturePrefix + '.stderr.log') | Out-Null
}
if ($PhoneQrDiagnostic -or $DirectoryPreview) { $dolphinArguments += @('-C', 'Dolphin.Core.EnableCheats=False') }
Start-Process -FilePath $DolphinExe -ArgumentList $dolphinArguments -WindowStyle Normal
Write-Output 'Started Demae with the existing shared Dolphin profile; fixture compatibility remains experimental.'
