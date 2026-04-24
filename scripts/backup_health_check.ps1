# MOCA - Monthly backup health check
# Verifies the backup system is actually producing usable snapshots.
# Sends an email if anything looks wrong.

$ErrorActionPreference = "Continue"

$ScriptDir   = Split-Path -Parent $MyInvocation.MyCommand.Definition
$ProjectRoot = Split-Path -Parent $ScriptDir
$LogFile     = Join-Path $ScriptDir "health_check.log"
$AlertScript = Join-Path $ScriptDir "alert.py"
$DriveRoot   = "F:\My Drive\MOCA"
$Issues      = [System.Collections.ArrayList]::new()
$Info        = [System.Collections.ArrayList]::new()

function Write-Log {
    param([string]$Message)
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "$ts  $Message" | Out-File -FilePath $LogFile -Append -Encoding utf8
}

function Send-Alert {
    param([string]$Subject, [string]$Body)
    if (Test-Path $AlertScript) {
        & python $AlertScript $Subject $Body 2>&1 | Out-Null
    }
}

Write-Log "===== Health check start ====="

# ---- Check 1: Google Drive folder accessible ----
if (-not (Test-Path $DriveRoot)) {
    [void]$Issues.Add("Google Drive MOCA folder not accessible at $DriveRoot. Is Google Drive for Desktop running?")
} else {
    [void]$Info.Add("Google Drive MOCA folder accessible.")

    # ---- Check 2: Recent backup exists (within 2 days) ----
    $recentBackups = Get-ChildItem $DriveRoot -Directory |
        Where-Object { $_.Name -match '^\d{4}-\d{2}-\d{2}$' } |
        Sort-Object Name -Descending

    if ($recentBackups.Count -eq 0) {
        [void]$Issues.Add("No dated backup folders found in $DriveRoot.")
    } else {
        $latest     = $recentBackups[0]
        $latestDate = [datetime]::ParseExact($latest.Name, 'yyyy-MM-dd', $null)
        $ageDays    = ((Get-Date).Date - $latestDate).Days

        [void]$Info.Add("Latest backup: $($latest.Name) ($ageDays days ago)")
        [void]$Info.Add("Total snapshots retained: $($recentBackups.Count)")

        if ($ageDays -gt 2) {
            [void]$Issues.Add("Latest backup is $ageDays days old. Expected a fresh backup every day.")
        }

        # ---- Check 3: Latest backup contains required files ----
        $requiredFiles = @("config.json", "plans.db")
        foreach ($f in $requiredFiles) {
            $p = Join-Path $latest.FullName $f
            if (-not (Test-Path $p)) {
                [void]$Issues.Add("Missing '$f' in latest backup ($($latest.Name)).")
            } else {
                $size = (Get-Item $p).Length
                if ($size -lt 100) {
                    [void]$Issues.Add("'$f' in latest backup is suspiciously small: $size bytes.")
                } else {
                    [void]$Info.Add("$f OK ($([math]::Round($size/1KB,1)) KB)")
                }
            }
        }

        # ---- Check 4: SQLite integrity of the latest backup ----
        $latestDb = Join-Path $latest.FullName "plans.db"
        if (Test-Path $latestDb) {
            try {
                $env:MOCA_HC_DB = $latestDb
                $pythonCmd = @"
import sqlite3, os, sys
try:
    c = sqlite3.connect(os.environ['MOCA_HC_DB'])
    result = c.execute('PRAGMA integrity_check').fetchone()[0]
    counts = {}
    for tbl in ('plans','abroad_plans','global_plans','content_plans','changes','news_articles'):
        try:
            counts[tbl] = c.execute(f'SELECT COUNT(*) FROM {tbl}').fetchone()[0]
        except sqlite3.OperationalError:
            counts[tbl] = -1
    c.close()
    sys.stdout.write(f'integrity={result}|' + '|'.join(f'{k}={v}' for k,v in counts.items()))
except Exception as e:
    sys.stderr.write(repr(e))
    sys.exit(1)
"@
                $dbResult = $pythonCmd | python 2>&1
                Remove-Item env:MOCA_HC_DB -ErrorAction SilentlyContinue

                if ($LASTEXITCODE -ne 0) {
                    [void]$Issues.Add("SQLite integrity check FAILED: $dbResult")
                } else {
                    if ($dbResult -notmatch 'integrity=ok') {
                        [void]$Issues.Add("SQLite integrity check returned: $dbResult")
                    } else {
                        [void]$Info.Add("SQLite integrity OK")
                        # Parse table counts for info
                        $parts = ($dbResult -split '\|') | Where-Object { $_ -match '=' -and $_ -notmatch 'integrity' }
                        foreach ($p in $parts) {
                            [void]$Info.Add("  $p rows")
                        }
                    }
                }
            } catch {
                [void]$Issues.Add("Could not run SQLite integrity check: $_")
            }
        }
    }
}

# ---- Check 5: Daily backup task is enabled ----
try {
    $task = Get-ScheduledTask -TaskName "MOCA Daily Backup" -ErrorAction Stop
    if ($task.State -eq "Disabled") {
        [void]$Issues.Add("Scheduled task 'MOCA Daily Backup' is DISABLED.")
    } else {
        $taskInfo = Get-ScheduledTaskInfo -TaskName "MOCA Daily Backup"
        [void]$Info.Add("Scheduled task state: $($task.State), next run: $($taskInfo.NextRunTime), last result: $($taskInfo.LastTaskResult)")
        if ($taskInfo.LastTaskResult -ne 0 -and $taskInfo.LastTaskResult -ne 267011) {  # 267011 = task never run yet
            [void]$Issues.Add("Last scheduled task run exited with code $($taskInfo.LastTaskResult).")
        }
    }
} catch {
    [void]$Issues.Add("Scheduled task 'MOCA Daily Backup' not found: $_")
}

# ---- Log everything ----
foreach ($i in $Info)   { Write-Log "INFO:  $i" }
foreach ($i in $Issues) { Write-Log "ISSUE: $i" }

# ---- Build report body ----
$report = "MOCA Backup Health Check Report`n"
$report += "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm')`n"
$report += "=" * 50 + "`n`n"

if ($Issues.Count -eq 0) {
    $report += "STATUS: HEALTHY - all checks passed.`n`n"
} else {
    $report += "STATUS: ISSUES FOUND ($($Issues.Count))`n`n"
    $report += "Issues:`n"
    foreach ($i in $Issues) { $report += "  - $i`n" }
    $report += "`n"
}

$report += "Details:`n"
foreach ($i in $Info) { $report += "  - $i`n" }

# ---- Email the report ----
if ($Issues.Count -gt 0) {
    Send-Alert "MOCA Backup Health Check - ISSUES FOUND" $report
    Write-Log "Alert email sent (issues found)."
} else {
    # Also send monthly "all good" confirmation so you know the health-check itself is alive
    Send-Alert "MOCA Backup Health Check - OK" $report
    Write-Log "Monthly OK email sent."
}

Write-Log "===== Health check end ====="
if ($Issues.Count -gt 0) { exit 1 } else { exit 0 }
