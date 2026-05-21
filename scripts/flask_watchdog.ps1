$ErrorActionPreference = "Continue"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$LogFile = Join-Path $PSScriptRoot "flask_watchdog.log"
$App = Join-Path $ProjectRoot "app.py"

Set-Location $ProjectRoot

while ($true) {
    $stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    "[$stamp] Flask starting..." | Add-Content -Path $LogFile -Encoding UTF8
    try { & python $App } catch { "[$stamp] Launch error: $_" | Add-Content -Path $LogFile -Encoding UTF8 }
    $stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    "[$stamp] Flask exited (code $LASTEXITCODE). Restarting in 15s..." | Add-Content -Path $LogFile -Encoding UTF8
    Start-Sleep -Seconds 15
}
