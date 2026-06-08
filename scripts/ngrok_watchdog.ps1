# MOCA - ngrok tunnel watchdog
# Keeps the public API tunnel alive on the RESERVED domain. If ngrok exits or the
# tunnel drops, relaunch after 10s. Mirrors flask_watchdog / vite_watchdog so the
# tunnel gets the SAME crash-recovery guarantee as Flask and Vite.
#
# Why this exists: previously ngrok was launched once (cmd /c) with no loop, so a
# mid-day ngrok death left the whole API unreachable until the next 06:00 health
# check -- and that recovery used a bare `ngrok http 5000` WITHOUT --domain, which
# would come up on a RANDOM url and break the deployed frontend. This script always
# binds the reserved domain, so the public URL never changes across restarts.

$ErrorActionPreference = "Continue"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$LogFile   = Join-Path $ScriptDir "ngrok_watchdog.log"
$Domain    = "terra-nonrestrained-overpiteously.ngrok-free.dev"

function Write-Log {
    param([string]$Message)
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "$ts  $Message" | Out-File -FilePath $LogFile -Append -Encoding utf8
}

while ($true) {
    Write-Log "ngrok starting (domain=$Domain)..."
    & ngrok http 5000 --domain=$Domain
    Write-Log "ngrok exited (code $LASTEXITCODE). Restarting in 10 seconds..."
    Start-Sleep -Seconds 10
}
