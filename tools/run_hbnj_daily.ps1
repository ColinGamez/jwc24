$ErrorActionPreference = "Stop"
$workspace = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
$logDirectory = Join-Path $workspace "private\logs"
New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$log = Join-Path $logDirectory "hbnj-update-$stamp.log"

Push-Location $workspace
try {
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    [Console]::OutputEncoding = $utf8
    $OutputEncoding = $utf8
    $env:PYTHONIOENCODING = "utf-8"
    # Windows PowerShell promotes native stderr to an ErrorRecord. This Python
    # installation emits a harmless prefix warning on stderr, so temporarily
    # allow the process to finish and judge success by its actual exit code.
    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    & py -3 "tools\update_hbnj_daily.py" *>&1 | Tee-Object -FilePath $log
    $updaterExitCode = $LASTEXITCODE
    $ErrorActionPreference = $previousErrorActionPreference
    if ($updaterExitCode -ne 0) {
        throw "HBNJ updater exited with code $updaterExitCode"
    }
}
finally {
    Pop-Location
}
