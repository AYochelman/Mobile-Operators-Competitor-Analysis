$ErrorActionPreference = "Continue"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$WorkDir = Join-Path $ProjectRoot "mass-market-app"
$LogFile = Join-Path $PSScriptRoot "vite_watchdog.log"

Set-Location $WorkDir

while ($true) {
    $stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    "[$stamp] Vite starting..." | Add-Content -Path $LogFile -Encoding UTF8
    try { & npm run dev } catch { "[$stamp] Launch error: $_" | Add-Content -Path $LogFile -Encoding UTF8 }
    $stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    "[$stamp] Vite exited (code $LASTEXITCODE). Restarting in 10s..." | Add-Content -Path $LogFile -Encoding UTF8
    Start-Sleep -Seconds 10
}
