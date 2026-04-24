# MOCA - Google Drive health monitor
# Runs 2x/day to verify Google Drive for Desktop is alive and syncing.
# Auto-restarts Drive if the process is dead.
# Sends alert if repeated failures or filesystem issues.

$ErrorActionPreference = "Continue"

$ScriptDir   = Split-Path -Parent $MyInvocation.MyCommand.Definition
$LogFile     = Join-Path $ScriptDir "drive_monitor.log"
$StateFile   = Join-Path $ScriptDir "drive_monitor.state"
$AlertScript = Join-Path $ScriptDir "alert.py"
$DriveExe    = "C:\Program Files\Google\Drive File Stream\launch.bat"
$DriveRoot   = "F:\My Drive\MOCA"
$HeartbeatFile = Join-Path $DriveRoot ".heartbeat"

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
    }
}

# Persistent state: track consecutive failures so we don't spam on transient issues
function Get-State {
    if (Test-Path $StateFile) {
        try { return Get-Content $StateFile -Raw | ConvertFrom-Json }
        catch { return @{ fail_streak = 0 } }
    }
    return @{ fail_streak = 0 }
}

function Set-State {
    param($State)
    $State | ConvertTo-Json | Out-File -FilePath $StateFile -Encoding utf8
}

function Find-DriveExe {
    # Find the actual latest version of GoogleDriveFS.exe
    $base = "C:\Program Files\Google\Drive File Stream"
    if (-not (Test-Path $base)) { return $null }
    $versionDirs = Get-ChildItem $base -Directory | Where-Object { $_.Name -match '^\d' } | Sort-Object Name -Descending
    foreach ($d in $versionDirs) {
        $exe = Join-Path $d.FullName "GoogleDriveFS.exe"
        if (Test-Path $exe) { return $exe }
    }
    return $null
}

Write-Log "===== Drive monitor start ====="
$state = Get-State
$issues = [System.Collections.ArrayList]::new()
$actionsTaken = [System.Collections.ArrayList]::new()

# ---- Check 1: Process alive ----
$driveProc = Get-Process -Name "GoogleDriveFS" -ErrorAction SilentlyContinue
if (-not $driveProc) {
    [void]$issues.Add("GoogleDriveFS process not running")
    Write-Log "Process check: DOWN"

    # Attempt auto-restart
    $exe = Find-DriveExe
    if ($exe) {
        try {
            Start-Process -FilePath $exe -WindowStyle Hidden
            Write-Log "Attempted to restart: $exe"
            Start-Sleep -Seconds 15
            $driveProc = Get-Process -Name "GoogleDriveFS" -ErrorAction SilentlyContinue
            if ($driveProc) {
                [void]$actionsTaken.Add("Auto-restarted GoogleDriveFS successfully")
                Write-Log "Auto-restart: SUCCESS"
                $issues.Clear()  # Recovered -- not an issue anymore
            } else {
                [void]$issues.Add("Auto-restart of GoogleDriveFS FAILED (process did not come up)")
                Write-Log "Auto-restart: FAILED"
            }
        } catch {
            [void]$issues.Add("Auto-restart threw error: $_")
            Write-Log "Auto-restart exception: $_"
        }
    } else {
        [void]$issues.Add("Could not locate GoogleDriveFS.exe to restart it")
    }
} else {
    Write-Log "Process check: OK (pid=$($driveProc[0].Id))"
}

# ---- Check 2: Drive mount accessible ----
if (-not (Test-Path "F:\My Drive")) {
    [void]$issues.Add("Drive mount point F:\My Drive is not accessible. Drive may be offline or not logged in.")
    Write-Log "Mount check: DOWN"
} else {
    Write-Log "Mount check: OK"

    # ---- Check 3: MOCA folder accessible ----
    if (-not (Test-Path $DriveRoot)) {
        [void]$issues.Add("MOCA folder missing at $DriveRoot. Someone may have deleted or renamed it.")
        Write-Log "MOCA folder check: MISSING"
    } else {
        Write-Log "MOCA folder check: OK"

        # ---- Check 4: Can write to Drive (filesystem sync alive) ----
        try {
            $now = Get-Date -Format "yyyy-MM-ddTHH:mm:ss"
            "$now  monitor heartbeat" | Out-File -FilePath $HeartbeatFile -Encoding utf8
            Start-Sleep -Seconds 2
            if (Test-Path $HeartbeatFile) {
                $written = Get-Item $HeartbeatFile
                $age = ((Get-Date) - $written.LastWriteTime).TotalSeconds
                if ($age -gt 30) {
                    [void]$issues.Add("Heartbeat file write succeeded but timestamp is $([math]::Round($age,0))s old - filesystem may be stale")
                } else {
                    Write-Log "Heartbeat write: OK"
                }
            } else {
                [void]$issues.Add("Heartbeat file disappeared immediately after write - Drive filesystem is unstable")
            }
        } catch {
            [void]$issues.Add("Cannot write heartbeat to Drive: $_")
            Write-Log "Heartbeat write FAILED: $_"
        }
    }
}

# ---- Decide whether to alert ----
$state = Get-State
if ($issues.Count -gt 0) {
    $state.fail_streak = [int]$state.fail_streak + 1
    Write-Log "Fail streak now: $($state.fail_streak)"

    # Alert on first failure AND escalate at streaks of 3 and 6
    $shouldAlert = ($state.fail_streak -eq 1) -or ($state.fail_streak -eq 3) -or ($state.fail_streak -eq 6) -or ($state.fail_streak -ge 12)
    if ($shouldAlert) {
        $subject = "MOCA Drive Monitor - PROBLEM (failure #$($state.fail_streak))"
        $body    = "Google Drive monitor detected issues at $(Get-Date -Format 'yyyy-MM-dd HH:mm').`n`n"
        $body   += "Issues:`n"
        foreach ($i in $issues) { $body += "  - $i`n" }
        if ($actionsTaken.Count -gt 0) {
            $body += "`nActions taken:`n"
            foreach ($a in $actionsTaken) { $body += "  - $a`n" }
        }
        $body += "`nConsecutive failures so far: $($state.fail_streak)"
        $body += "`nIf this repeats, the scheduled daily backup may not reach the cloud."
        $body += "`n`nCheck $LogFile for history."
        Send-Alert $subject $body
    }
} else {
    if ($state.fail_streak -gt 0) {
        # Recovered after a previous failure
        Send-Alert "MOCA Drive Monitor - RECOVERED" "Google Drive is healthy again after $($state.fail_streak) failed check(s)."
        Write-Log "Recovery alert sent (previous streak: $($state.fail_streak))"
    }
    $state.fail_streak = 0
    Write-Log "All checks OK."
}

Set-State $state
Write-Log "===== Drive monitor end ====="
if ($issues.Count -gt 0) { exit 1 } else { exit 0 }
