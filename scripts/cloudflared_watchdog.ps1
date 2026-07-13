# MOCA - cloudflared tunnel watchdog
# Keeps the Cloudflare Tunnel alive (api.mocaintel.com -> localhost:5000). Mirrors the
# Flask/Vite/ngrok watchdogs: infinite loop, relaunch 10s after any exit. This REPLACES
# ngrok as the public ingress. Reads the tunnel + ingress config from
# C:\Users\<user>\.cloudflared\config.yml (tunnel 'moca').

$ErrorActionPreference = "Continue"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$LogFile   = Join-Path $ScriptDir "cloudflared_watchdog.log"
$CF        = Join-Path $ScriptDir "cloudflared.exe"

function Write-Log {
    param([string]$Message)
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "$ts  $Message" | Out-File -FilePath $LogFile -Append -Encoding utf8
}

# 2026-07-13: mocaintel.com TAKEDOWN (employer request) - api.mocaintel.com must stay
# offline, so the tunnel is disabled at the script level (the MOCA-Cloudflared task
# still fires at logon but exits immediately here; disabling the task itself needs
# elevation). To bring the tunnel back: delete scripts/TUNNEL_DISABLED.flag.
if (Test-Path (Join-Path $ScriptDir "TUNNEL_DISABLED.flag")) {
    Write-Log "TUNNEL_DISABLED.flag present -- mocaintel takedown in effect, NOT starting cloudflared."
    exit 0
}

while ($true) {
    Write-Log "cloudflared tunnel 'moca' starting..."
    & $CF tunnel run moca
    Write-Log "cloudflared exited (code $LASTEXITCODE). Restarting in 10 seconds..."
    Start-Sleep -Seconds 10
}
