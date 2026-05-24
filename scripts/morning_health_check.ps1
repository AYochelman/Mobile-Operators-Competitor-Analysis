# MOCA - Morning health check (06:00 daily)
# Verifies the three runtime services are listening and restarts whichever is down:
#   - Flask  (port 5000) -> relaunches via flask_watchdog.bat
#   - ngrok  (port 4040) -> relaunches `ngrok http 5000` in a cmd window
#   - Vite   (port 5173) -> relaunches via vite_watchdog.bat
# Sends a Telegram + email alert via alert.py if anything was restarted or failed.

$ErrorActionPreference = "Continue"

$ScriptDir     = Split-Path -Parent $MyInvocation.MyCommand.Definition
$ProjectRoot   = Split-Path -Parent $ScriptDir
$LogFile       = Join-Path $ScriptDir "morning_health_check.log"
$AlertScript   = Join-Path $ScriptDir "alert.py"
$FlaskWatchdog = Join-Path $ScriptDir "flask_watchdog.bat"
$ViteWatchdog  = Join-Path $ScriptDir "vite_watchdog.bat"
$ViteWorkDir   = Join-Path $ProjectRoot "mass-market-app"

function Write-Log {
    param([string]$Message)
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "$ts  $Message" | Out-File -FilePath $LogFile -Append -Encoding utf8
}

function Send-Alert {
    param([string]$Subject, [string]$Body)
    if (Test-Path $AlertScript) {
        & python $AlertScript $Subject $Body 2>&1 | Out-Null
        Write-Log "Alert dispatched: $Subject"
    } else {
        Write-Log "alert.py missing -- alert NOT dispatched: $Subject"
    }
}

function Test-Port {
    param([int]$Port)
    $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    return [bool]$conn
}

function Restart-Service {
    param(
        [string]$Name,
        [int]$Port,
        [scriptblock]$Launcher,
        [int]$WaitSeconds = 30
    )
    if (Test-Port $Port) {
        Write-Log "$Name (port $Port): UP"
        return $null
    }
    Write-Log "$Name (port $Port): DOWN -- attempting restart"
    try {
        & $Launcher
        # Poll every 2s instead of one big sleep — recover as soon as the port comes up,
        # and avoid false-failing on a service that's just slow to bind.
        $deadline = (Get-Date).AddSeconds($WaitSeconds)
        $elapsed  = 0
        while ((Get-Date) -lt $deadline) {
            Start-Sleep -Seconds 2
            $elapsed += 2
            if (Test-Port $Port) {
                Write-Log "$Name restart: SUCCESS (after ${elapsed}s)"
                return @{ status = 'restarted'; name = $Name; port = $Port }
            }
        }
        Write-Log "$Name restart: FAILED (port $Port still not listening after ${WaitSeconds}s)"
        return @{ status = 'failed';    name = $Name; port = $Port; reason = "port did not come up after ${WaitSeconds}s" }
    } catch {
        Write-Log "$Name restart EXCEPTION: $_"
        return @{ status = 'failed';    name = $Name; port = $Port; reason = "$_" }
    }
}

Write-Log "===== Morning health check start ====="

$results = [System.Collections.ArrayList]::new()

# ---- Flask (5000) ----
# Wait window is generous: cold start has to import Playwright + APScheduler + 40 scrapers.
$r = Restart-Service -Name "Flask" -Port 5000 -WaitSeconds 30 -Launcher {
    Start-Process cmd -ArgumentList "/k `"$FlaskWatchdog`"" -WorkingDirectory $ProjectRoot
}
if ($r) { [void]$results.Add($r) }

# ---- ngrok (4040) ----
# 6s was too tight: ngrok has to read config, dial out to ngrok cloud, register
# the tunnel, and only then open the local 4040 web UI port. Give it 20s.
$r = Restart-Service -Name "ngrok" -Port 4040 -WaitSeconds 20 -Launcher {
    Start-Process cmd -ArgumentList "/k ngrok http 5000"
}
if ($r) { [void]$results.Add($r) }

# ---- Vite (5173) ----
$r = Restart-Service -Name "Vite" -Port 5173 -WaitSeconds 30 -Launcher {
    Start-Process cmd -ArgumentList "/k `"$ViteWatchdog`"" -WorkingDirectory $ViteWorkDir
}
if ($r) { [void]$results.Add($r) }

# ---- Alert if anything was restarted or failed ----
$restarted = $results | Where-Object { $_.status -eq 'restarted' }
$failed    = $results | Where-Object { $_.status -eq 'failed' }

if ($restarted.Count -gt 0 -or $failed.Count -gt 0) {
    if ($failed.Count -gt 0) {
        $subject = "MOCA Morning Health Check - PROBLEMS"
    } else {
        $subject = "MOCA Morning Health Check - auto-recovered"
    }

    $body = "Morning health check at $(Get-Date -Format 'yyyy-MM-dd HH:mm').`n`n"
    if ($restarted.Count -gt 0) {
        $body += "Restarted (auto-recovered):`n"
        foreach ($r in $restarted) { $body += "  - $($r.name) (port $($r.port))`n" }
    }
    if ($failed.Count -gt 0) {
        $body += "`nFailed to restart:`n"
        foreach ($r in $failed) { $body += "  - $($r.name) (port $($r.port)): $($r.reason)`n" }
        $body += "`nManual intervention required."
    }
    $body += "`nLog: $LogFile"
    Send-Alert $subject $body
}

Write-Log "===== Morning health check end (restarted=$($restarted.Count) failed=$($failed.Count)) ====="
if ($failed.Count -gt 0) { exit 1 } else { exit 0 }
