# MOCA - Morning health check (every 10 min via Task Scheduler)
# Verifies the three runtime services and restarts whichever is down:
#   - Flask (port 5000)  -> relaunches via flask_watchdog.bat
#   - ngrok public EDGE  -> https://<reserved-domain>/api/ping must return {"ok":true};
#                           recovers by recycling the MOCA-Ngrok scheduled task
#   - Vite  (port 5173)  -> relaunches via vite_watchdog.bat
# Sends a Telegram + email alert via alert.py if anything was restarted or failed.

$ErrorActionPreference = "Continue"
$ProgressPreference    = "SilentlyContinue"

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
        # Poll every 2s instead of one big sleep -- recover as soon as the port comes up,
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

# ---- Public API ingress: ngrok (EDGE probe) ----
# 2026-07-13: mocaintel.com is OFFLINE (employer request) - cloudflared/api.mocaintel.com
# is intentionally down. The public ingress is the reserved ngrok domain below.
# 2026-08-05: probe the PUBLIC EDGE end-to-end, NOT the agent's local API (port 4040).
# ERR_NGROK_121 incident (2026-08-05): ngrok raised the free-tier minimum agent version,
# the 3.3.1 agent's edge session died but the local process and port 4040 stayed up
# (zombie) -> the old port check reported UP while the production API was down for hours.
# Only a request that traverses the real edge catches that failure class.
# Recovery goes through the MOCA-Ngrok scheduled task (ENABLED 2026-08-05): ending the
# task kills its whole process tree, then any LEFTOVER watchdog/agent outside the task
# tree (e.g. direct-launched by an older version of this script) is killed too, so a
# zombie agent can never survive a recovery cycle. Do NOT direct-launch the watchdog
# from here anymore - that is what created untracked stray watchdogs in the first place.
# ELEVATION NOTE: this task runs at RunLevel Limited while MOCA-Ngrok runs Highest, so
# the elevated watchdog's CommandLine is INVISIBLE here (WMI returns null) - never gate
# logic on counting watchdog processes. schtasks /end|/run go through the Scheduler
# service and work on the elevated task anyway; the process sweep in Invoke-NgrokRecycle
# is best-effort and only needs to kill non-elevated strays (the only kind this script
# ever created).

$NgrokTask    = "MOCA-Ngrok"
$NgrokEdgeUrl = "https://terra-nonrestrained-overpiteously.ngrok-free.dev/api/ping"

# PS 5.1 safety: make sure TLS 1.2 is enabled for the HTTPS probe
[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12

function Test-NgrokEdge {
    # $true only when the PUBLIC url answers with {"ok":true}, i.e. Flask was reached
    # THROUGH the tunnel. Retries give a transient blip a chance to pass (no alert spam).
    param([int]$Attempts = 1, [int]$DelaySeconds = 10)
    for ($i = 1; $i -le $Attempts; $i++) {
        try {
            $resp = Invoke-WebRequest -Uri $NgrokEdgeUrl -Headers @{ "ngrok-skip-browser-warning" = "true" } -UseBasicParsing -TimeoutSec 15
            if ($resp.Content -match '"ok"\s*:\s*true') { return $true }
            Write-Log "ngrok edge probe ${i}/${Attempts}: HTTP $($resp.StatusCode) but body is not {""ok"":true}: $($resp.Content)"
        } catch {
            Write-Log "ngrok edge probe ${i}/${Attempts}: $($_.Exception.Message)"
        }
        if ($i -lt $Attempts) { Start-Sleep -Seconds $DelaySeconds }
    }
    return $false
}

function Get-NgrokWatchdogProcs {
    # Only sees processes whose CommandLine is readable from this (Limited) context,
    # i.e. non-elevated strays. The elevated task-owned watchdog reads as null and is
    # deliberately not matched - it is handled by schtasks /end, not by Stop-Process.
    Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -like '*ngrok_watchdog.ps1*' }
}

function Test-NgrokCrashLoop {
    # The watchdog logs "ngrok exited (code N)" and relaunches every 10s. A healthy
    # agent writes ONE "starting" line and then stays silent for as long as the tunnel
    # lives. Several exit lines within the last few minutes therefore mean the task's
    # watchdog is stuck in a relaunch loop - typically fighting a stray/zombie agent
    # for the single free-tier session, or ngrok cannot start at all.
    $wdLog = Join-Path $ScriptDir "ngrok_watchdog.log"
    if (-not (Test-Path $wdLog)) { return $false }
    $cutoff = (Get-Date).AddMinutes(-3)
    $recentExits = 0
    foreach ($line in @(Get-Content $wdLog -Tail 40 -ErrorAction SilentlyContinue)) {
        if ($line -match '^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+ngrok exited') {
            try {
                if ([datetime]::ParseExact($Matches[1], 'yyyy-MM-dd HH:mm:ss', [System.Globalization.CultureInfo]::InvariantCulture) -ge $cutoff) { $recentExits++ }
            } catch {}
        }
    }
    return ($recentExits -ge 3)
}

function Get-NgrokLastExitStamp {
    # Timestamp string of the newest "ngrok exited" line (or '' if none in the tail).
    $wdLog = Join-Path $ScriptDir "ngrok_watchdog.log"
    $last = ''
    foreach ($line in @(Get-Content $wdLog -Tail 40 -ErrorAction SilentlyContinue)) {
        if ($line -match '^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+ngrok exited') { $last = $Matches[1] }
    }
    return $last
}

function Invoke-NgrokRecycle {
    # Clean tunnel restart through the scheduled task:
    # enable (no-op if already enabled) -> end task (kills its process tree) ->
    # kill leftover watchdogs/agents outside the task tree -> run task.
    schtasks /change /tn $NgrokTask /enable 2>&1 | Out-Null
    schtasks /end /tn $NgrokTask 2>&1 | Out-Null
    Start-Sleep -Seconds 2
    foreach ($p in @(Get-NgrokWatchdogProcs)) {
        try { Stop-Process -Id $p.ProcessId -Force -ErrorAction Stop; Write-Log "ngrok recycle: killed leftover watchdog PID $($p.ProcessId)" }
        catch { Write-Log "ngrok recycle: could not kill leftover watchdog PID $($p.ProcessId): $_" }
    }
    foreach ($p in @(Get-Process ngrok -ErrorAction SilentlyContinue)) {
        try { Stop-Process -Id $p.Id -Force -ErrorAction Stop; Write-Log "ngrok recycle: killed leftover ngrok agent PID $($p.Id)" }
        catch { Write-Log "ngrok recycle: could not kill leftover ngrok agent PID $($p.Id): $_" }
    }
    schtasks /run /tn $NgrokTask 2>&1 | Out-Null
}

if (Test-NgrokEdge -Attempts 3 -DelaySeconds 10) {
    Write-Log "ngrok edge ($NgrokEdgeUrl): UP"
    # Hygiene: the edge being up does not mean the STATE is healthy. If the tunnel is
    # held by a stray (non-task) agent, the task's watchdog crash-loops on the single
    # free-tier session (endless exit-code-1 lines in ngrok_watchdog.log) and a future
    # zombie would survive a plain task recycle. Detect that from the watchdog LOG
    # (elevation-independent) and from the task state, then reconcile to a clean
    # task-owned agent.
    $taskState = "$((Get-ScheduledTask -TaskName $NgrokTask -ErrorAction SilentlyContinue).State)"
    $crashLoop = Test-NgrokCrashLoop
    if ($crashLoop) {
        # Confirm the loop is CURRENT before recycling: a live relaunch loop appends a
        # new "ngrok exited" line every ~10s. Right after a recycle fixed things, the
        # old exit lines still sit inside the 3-minute window (e.g. a manual run 15s
        # before a scheduled one) - don't bounce a healthy tunnel over a stale corpse.
        $stampBefore = Get-NgrokLastExitStamp
        Start-Sleep -Seconds 25
        $crashLoop = ((Get-NgrokLastExitStamp) -ne $stampBefore)
        if (-not $crashLoop) { Write-Log "ngrok hygiene: crash-loop lines are stale (no new exits in 25s) -- already recovered, skipping recycle" }
    }
    if ($taskState -ne 'Running' -or $crashLoop) {
        Write-Log "ngrok hygiene: task state '$taskState', crash-loop=$crashLoop -- recycling to a single task-owned agent"
        Invoke-NgrokRecycle
        if (Test-NgrokEdge -Attempts 6 -DelaySeconds 5) {
            Write-Log "ngrok hygiene recycle: SUCCESS (edge back up, task-owned)"
            [void]$results.Add(@{ status = 'restarted'; name = 'ngrok tunnel (hygiene recycle)'; port = 443 })
        } else {
            Write-Log "ngrok hygiene recycle: FAILED (edge did not come back)"
            [void]$results.Add(@{ status = 'failed'; name = 'ngrok tunnel (hygiene recycle)'; port = 443; reason = 'edge did not come back after recycle; check ngrok_watchdog.log' })
        }
    }
} else {
    Write-Log "ngrok edge: DOWN (all probes failed)"
    if (-not (Test-Port 5000)) {
        # Flask itself is dead locally - the edge cannot answer and recycling the tunnel
        # will not help. The Flask block above already tried to restart it (and alerts).
        Write-Log "ngrok edge: skipping tunnel recycle -- Flask (port 5000) is down locally, fix that first"
        [void]$results.Add(@{ status = 'failed'; name = 'ngrok edge'; port = 443; reason = 'edge down because Flask is down locally' })
    } else {
        Write-Log "ngrok edge: recycling scheduled task '$NgrokTask' (also clears zombie agents)"
        Invoke-NgrokRecycle
        if (Test-NgrokEdge -Attempts 9 -DelaySeconds 5) {
            Write-Log "ngrok recycle: SUCCESS (edge is back up)"
            [void]$results.Add(@{ status = 'restarted'; name = 'ngrok tunnel'; port = 443 })
        } else {
            Write-Log "ngrok recycle: FAILED (edge still down after task recycle)"
            [void]$results.Add(@{ status = 'failed'; name = 'ngrok tunnel'; port = 443; reason = 'edge still down after task recycle (agent version/auth/plan issue? check ngrok_watchdog.log)' })
        }
    }
}

# ---- Vite (5173) ----
$r = Restart-Service -Name "Vite" -Port 5173 -WaitSeconds 30 -Launcher {
    Start-Process cmd -ArgumentList "/k `"$ViteWatchdog`"" -WorkingDirectory $ViteWorkDir
}
if ($r) { [void]$results.Add($r) }

# ---- Alert if anything was restarted or failed ----
# @() so a single hashtable result counts as 1 item, not its number of keys.
$restarted = @($results | Where-Object { $_.status -eq 'restarted' })
$failed    = @($results | Where-Object { $_.status -eq 'failed' })

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
