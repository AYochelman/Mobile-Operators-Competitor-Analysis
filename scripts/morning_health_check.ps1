# MOCA - Morning health check (every 10 min via Task Scheduler)
# Verifies the three runtime services and restarts whichever is down:
#   - Flask (port 5000)  -> relaunches via flask_watchdog.bat
#   - ngrok public EDGE  -> https://<reserved-domain>/api/ping must return {"ok":true};
#                           recovers by recycling the MOCA-Ngrok scheduled task. Probed at
#                           most hourly while healthy (each probe spends ngrok's monthly
#                           request quota), see "Edge probe budget" below
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
# A port must miss this many extra probes, $ConfirmDelaySeconds apart, before it counts as DOWN.
$ConfirmProbes       = 3
$ConfirmDelaySeconds = 5

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
    # A real TCP connect, not Get-NetTCPConnection -State Listen: after the 2026-10-29 reboot
    # Windows reported every listener with State=0 (not a valid enum value), the -State filter
    # matched nothing, and this check spawned a new Flask+Vite watchdog pair every 10 min while
    # both were up. Vite binds ::1 only (localhost), Flask 127.0.0.1 - so try both loopbacks.
    param([int]$Port)
    foreach ($addr in '127.0.0.1', '::1') {
        $client = New-Object System.Net.Sockets.TcpClient($(if ($addr -eq '::1') { 'InterNetworkV6' } else { 'InterNetwork' }))
        try {
            if ($client.ConnectAsync($addr, $Port).Wait(2000) -and $client.Connected) { return $true }
        } catch {
        } finally {
            $client.Dispose()
        }
    }
    return $false
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
    # Confirm before relaunching (2026-10-30): one 2s connect is not proof of DOWN. At 07:50
    # the box was so loaded this run started 36s late and the ngrok probe timed out; the single
    # Vite connect missed, and the "restart" opened a 2nd Vite on 5174 next to the healthy one
    # (the tell: "SUCCESS after 2s" - a fresh Vite takes ~30s). Re-probe for ~20s first.
    for ($i = 1; $i -le $ConfirmProbes; $i++) {
        Start-Sleep -Seconds $ConfirmDelaySeconds
        if (Test-Port $Port) {
            Write-Log "$Name (port $Port): UP (missed first probe, answered on recheck $i/$ConfirmProbes)"
            return $null
        }
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

# IPv6 GOTCHA (2026-09-18): the ngrok edge publishes an AAAA record and this box gets
# global IPv6 addresses from the router, but IPv6 has NO working upstream here (curl -6 to
# google times out too). .NET's HttpWebRequest (Invoke-WebRequest) tries the IPv6 address
# first and burns the whole timeout, so the old probe reported DOWN for an hour while curl
# (Happy Eyeballs -> IPv4) answered fine -- and every 10 minutes the "recovery" recycled a
# perfectly healthy tunnel. The probe therefore uses the Windows-bundled curl.exe pinned to
# IPv4 (-4); Invoke-WebRequest stays only as a fallback when curl.exe is missing.
$CurlExe = Join-Path $env:SystemRoot "System32\curl.exe"

function Invoke-EdgeProbe {
    # Returns the response body (string) or throws with a short reason.
    if (Test-Path $CurlExe) {
        $out = & $CurlExe -4 -s -S -m 15 -H "ngrok-skip-browser-warning: true" -w "`n%{http_code}" $NgrokEdgeUrl 2>&1
        if ($LASTEXITCODE -ne 0) { throw "curl exit $LASTEXITCODE`: $(($out | Out-String).Trim())" }
        $lines = @(($out | Out-String).Trim() -split "`n")
        $code  = $lines[-1].Trim()
        $body  = ($lines[0..([Math]::Max(0, $lines.Count - 2))] -join "`n").Trim()
        if ($code -ne '200') { throw "HTTP $code`: $body" }
        return $body
    }
    $resp = Invoke-WebRequest -Uri $NgrokEdgeUrl -Headers @{ "ngrok-skip-browser-warning" = "true" } -UseBasicParsing -TimeoutSec 15
    return [string]$resp.Content
}

function Test-NgrokEdge {
    # Returns 'up' only when the PUBLIC url answers with {"ok":true}, i.e. Flask was reached
    # THROUGH the tunnel. Retries give a transient blip a chance to pass (no alert spam).
    # Returns 'quota' when ngrok refuses because the account's MONTHLY usage limit is spent
    # (ERR_NGROK_727, 2026-11-27): nothing on this box can fix that, so callers must not
    # recycle the tunnel over it. Anything else is 'down'.
    # Callers compare the result to 'up' - every one of these strings is truthy.
    param([int]$Attempts = 1, [int]$DelaySeconds = 10)
    for ($i = 1; $i -le $Attempts; $i++) {
        try {
            $body = Invoke-EdgeProbe
            if ($body -match '"ok"\s*:\s*true') { return 'up' }
            Write-Log "ngrok edge probe ${i}/${Attempts}: HTTP 200 but body is not {""ok"":true}: $body"
        } catch {
            $msg = "$($_.Exception.Message)"
            if ($msg -match 'ERR_NGROK_727|limit for the month') {
                Write-Log "ngrok edge probe ${i}/${Attempts}: the ngrok account's monthly usage limit is spent (ERR_NGROK_727)"
                return 'quota'
            }
            # ngrok's error pages are ~25 lines of HTML: keep the error code and a short head.
            $code = if ($msg -match '(ERR_NGROK_\d+)') { " [$($Matches[1])]" } else { '' }
            $flat = ($msg -replace '\s+', ' ')
            Write-Log "ngrok edge probe ${i}/${Attempts}:$code $($flat.Substring(0, [Math]::Min(300, $flat.Length)))"
        }
        if ($i -lt $Attempts) { Start-Sleep -Seconds $DelaySeconds }
    }
    return 'down'
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

# ---- Edge probe budget (2026-11-27) ----
# Every edge probe is a real request through ngrok, and the free plan allows 20,000 a month.
# Probing every 10 minutes cost 144 requests a day (~4,300 a month, about half of October's
# total); on 2026-11-27 the account ran out and ngrok refused ALL traffic until the monthly
# reset (ERR_NGROK_727), so the live site had no API at all. Now the edge is probed at most
# once an hour while the last result was good, and every run only while something looks
# wrong: the last probe failed, the MOCA-Ngrok task is not Running, or the watchdog log shows
# a crash loop (both are local checks and cost nothing).
# A spent quota is not an outage this box can fix: no recycle, one alert a day, an hourly
# probe to notice the reset, and a recovery alert when traffic flows again.
$EdgeProbeIntervalMinutes = 60
$EdgeStateFile = Join-Path $ScriptDir "ngrok_edge.state"   # *.state is gitignored
$StampFormat   = 'yyyy-MM-dd HH:mm:ss'

function Read-EdgeState {
    $s = @{ last_probe = ''; last_status = ''; quota_since = ''; quota_alert_day = '' }
    if (Test-Path $EdgeStateFile) {
        try {
            $j = Get-Content $EdgeStateFile -Raw -ErrorAction Stop | ConvertFrom-Json
            foreach ($k in @($s.Keys)) { if ($null -ne $j.$k) { $s[$k] = [string]$j.$k } }
        } catch { Write-Log "ngrok edge state unreadable, starting fresh: $_" }
    }
    return $s
}

function Save-EdgeState {
    param([hashtable]$State)
    try { ($State | ConvertTo-Json) | Set-Content -Path $EdgeStateFile -Encoding UTF8 -ErrorAction Stop }
    catch { Write-Log "ngrok edge state could not be saved: $_" }
}

function Register-NgrokQuota {
    # Spent monthly quota: remember since when, and alert at most once per calendar day.
    param([hashtable]$State)
    $today = (Get-Date).ToString('yyyy-MM-dd')
    if (-not $State.quota_since) { $State.quota_since = (Get-Date).ToString($StampFormat) }
    Write-Log "ngrok edge: monthly usage limit spent since $($State.quota_since) -- NOT recycling (it cannot help); next probe in ~$EdgeProbeIntervalMinutes min"
    if ($State.quota_alert_day -ne $today) {
        $State.quota_alert_day = $today
        [void]$results.Add(@{ status = 'failed'; name = 'ngrok monthly limit'; port = 443; reason = "the ngrok account's monthly usage limit is spent (ERR_NGROK_727, since $($State.quota_since)). ngrok refuses all traffic, so the live site has no API until the limit resets (date on dashboard.ngrok.com/billing). Recycling cannot help and is skipped; this alert repeats once a day." })
    } else {
        Write-Log "ngrok edge: monthly-limit alert already sent today"
    }
}

$edgeState   = Read-EdgeState
$taskState   = "$((Get-ScheduledTask -TaskName $NgrokTask -ErrorAction SilentlyContinue).State)"
$crashHint   = Test-NgrokCrashLoop
$lastProbeAt = $null
if ($edgeState.last_probe) {
    try { $lastProbeAt = [datetime]::ParseExact($edgeState.last_probe, $StampFormat, [System.Globalization.CultureInfo]::InvariantCulture) } catch {}
}
$probeReason = $null
if (-not $lastProbeAt) { $probeReason = 'no previous probe' }
elseif (((Get-Date) - $lastProbeAt).TotalMinutes -ge ($EdgeProbeIntervalMinutes - 2)) { $probeReason = 'hourly' }   # -2: the task starts a few seconds late
elseif ($edgeState.last_status -eq 'down') { $probeReason = 'last probe failed' }
elseif ($taskState -ne 'Running') { $probeReason = "task state '$taskState'" }
elseif ($crashHint) { $probeReason = 'watchdog crash-loop lines' }

if (-not $probeReason) {
    Write-Log "ngrok edge: probe skipped (last result '$($edgeState.last_status)' at $($lastProbeAt.ToString('HH:mm')), next ~$($lastProbeAt.AddMinutes($EdgeProbeIntervalMinutes).ToString('HH:mm')); task Running, no crash loop)"
} else {
$edgeState.last_probe  = (Get-Date).ToString($StampFormat)
$edge = Test-NgrokEdge -Attempts 3 -DelaySeconds 10
$edgeState.last_status = $edge
if ($edge -eq 'quota') {
    Register-NgrokQuota $edgeState
} elseif ($edge -eq 'up') {
    Write-Log "ngrok edge ($NgrokEdgeUrl): UP (probe reason: $probeReason)"
    if ($edgeState.quota_since) {
        Write-Log "ngrok edge: monthly usage limit has reset -- traffic flows again (blocked since $($edgeState.quota_since))"
        [void]$results.Add(@{ status = 'restarted'; name = "ngrok monthly limit reset, edge serving again (blocked since $($edgeState.quota_since))"; port = 443 })
        $edgeState.quota_since = ''; $edgeState.quota_alert_day = ''
    }
    # Hygiene: the edge being up does not mean the STATE is healthy. If the tunnel is
    # held by a stray (non-task) agent, the task's watchdog crash-loops on the single
    # free-tier session (endless exit-code-1 lines in ngrok_watchdog.log) and a future
    # zombie would survive a plain task recycle. Detect that from the watchdog LOG
    # (elevation-independent) and from the task state, then reconcile to a clean
    # task-owned agent.
    $crashLoop = $crashHint
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
        $after = Test-NgrokEdge -Attempts 6 -DelaySeconds 5
        $edgeState.last_status = $after
        if ($after -eq 'up') {
            Write-Log "ngrok hygiene recycle: SUCCESS (edge back up, task-owned)"
            [void]$results.Add(@{ status = 'restarted'; name = 'ngrok tunnel (hygiene recycle)'; port = 443 })
        } elseif ($after -eq 'quota') {
            Register-NgrokQuota $edgeState
        } else {
            Write-Log "ngrok hygiene recycle: FAILED (edge did not come back)"
            [void]$results.Add(@{ status = 'failed'; name = 'ngrok tunnel (hygiene recycle)'; port = 443; reason = 'edge did not come back after recycle; check ngrok_watchdog.log' })
        }
    }
} else {
    Write-Log "ngrok edge: DOWN (all probes failed; probe reason: $probeReason)"
    if (-not (Test-Port 5000)) {
        # Flask itself is dead locally - the edge cannot answer and recycling the tunnel
        # will not help. The Flask block above already tried to restart it (and alerts).
        Write-Log "ngrok edge: skipping tunnel recycle -- Flask (port 5000) is down locally, fix that first"
        [void]$results.Add(@{ status = 'failed'; name = 'ngrok edge'; port = 443; reason = 'edge down because Flask is down locally' })
    } else {
        Write-Log "ngrok edge: recycling scheduled task '$NgrokTask' (also clears zombie agents)"
        Invoke-NgrokRecycle
        $after = Test-NgrokEdge -Attempts 9 -DelaySeconds 5
        $edgeState.last_status = $after
        if ($after -eq 'up') {
            Write-Log "ngrok recycle: SUCCESS (edge is back up)"
            [void]$results.Add(@{ status = 'restarted'; name = 'ngrok tunnel'; port = 443 })
        } elseif ($after -eq 'quota') {
            Register-NgrokQuota $edgeState
        } else {
            Write-Log "ngrok recycle: FAILED (edge still down after task recycle)"
            [void]$results.Add(@{ status = 'failed'; name = 'ngrok tunnel'; port = 443; reason = 'edge still down after task recycle (agent version/auth/plan issue? check ngrok_watchdog.log)' })
        }
    }
}
Save-EdgeState $edgeState
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
