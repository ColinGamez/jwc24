$ErrorActionPreference = "Stop"
$workspace = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
$logDirectory = Join-Path $workspace "private\logs"
New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$log = Join-Path $logDirectory "hbnj-update-$stamp.log"

Push-Location $workspace
try {
    $env:PYTHONIOENCODING = "utf-8"
    & py -3 "tools\update_hbnj_daily.py" *>&1 | Tee-Object -FilePath $log
    if ($LASTEXITCODE -ne 0) {
        throw "HBNJ updater exited with code $LASTEXITCODE"
    }
}
finally {
    Pop-Location
}
