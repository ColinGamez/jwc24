$ErrorActionPreference = "Stop"

$applicationId = Read-Host "Paste Rakuten Application ID"
$secureAccessKey = Read-Host "Paste Rakuten Access Key (hidden)" -AsSecureString
$affiliateId = Read-Host "Paste Rakuten Affiliate ID (optional; press Enter to skip)"

if ([string]::IsNullOrWhiteSpace($applicationId)) {
    throw "Application ID is required."
}

$credential = [Net.NetworkCredential]::new("", $secureAccessKey)
$accessKey = $credential.Password
if ([string]::IsNullOrWhiteSpace($accessKey)) {
    throw "Access Key is required."
}

$env:JWC24_RAKUTEN_APPLICATION_ID = $applicationId.Trim()
$env:JWC24_RAKUTEN_ACCESS_KEY = $accessKey
$env:JWC24_RAKUTEN_AFFILIATE_ID = $affiliateId.Trim()

try {
    & ".venv\Scripts\python.exe" "tools\import_rakuten_catalog.py" "Wii" `
        --output "private\wii_no_ma\shop\rakuten.json" --pages 2
    if ($LASTEXITCODE -ne 0) {
        throw "Rakuten importer exited with code $LASTEXITCODE."
    }
    Write-Host ""
    Write-Host "Rakuten catalog setup completed successfully." -ForegroundColor Green
}
finally {
    $env:JWC24_RAKUTEN_ACCESS_KEY = $null
    $accessKey = $null
    $credential = $null
    $secureAccessKey.Dispose()
}

Read-Host "Press Enter to close"
