# MOCA - Daily backup to Google Drive
# Backs up config.json + SQLite DB + data/banners to the synced Google Drive folder.
# SQLite is copied via the .backup command to avoid DB locks during scraping.

$ErrorActionPreference = "Stop"

# Derive project root from script location (avoids non-ASCII chars in source)
$ScriptDir   = Split-Path -Parent $MyInvocation.MyCommand.Definition
$ProjectRoot = Split-Path -Parent $ScriptDir
$LogFile     = Join-Path $ScriptDir "backup.log"
$AlertScript = Join-Path $ScriptDir "alert.py"
$Warnings    = [System.Collections.ArrayList]::new()

function Write-Log {
    param([string]$Message)
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "$ts  $Message" | Out-File -FilePath $LogFile -Append -Encoding utf8
}

function Send-Alert {
    param([string]$Subject, [string]$Body)
    if (Test-Path $AlertScript) {
        try {
            & python $AlertScript $Subject $Body 2>&1 | Out-Null
            Write-Log "Alert email sent: $Subject"
        } catch {
            Write-Log "Alert email FAILED to send: $_"
        }
    }
}

# Catch any uncaught terminating error and email the admin before dying
trap {
    $err = $_ | Out-String
    Write-Log "FATAL: $err"
    Send-Alert "MOCA Backup CRASHED" "Backup script crashed unexpectedly.`n`n$err"
    exit 1
}

# ---- Pre-flight: ensure Google Drive is running (auto-start if dead) ----
if (-not (Get-Process -Name "GoogleDriveFS" -ErrorAction SilentlyContinue)) {
    Write-Log "Pre-flight: GoogleDriveFS is DOWN, attempting restart..."
    $driveBase = "C:\Program Files\Google\Drive File Stream"
    if (Test-Path $driveBase) {
        $latestVer = Get-ChildItem $driveBase -Directory | Where-Object { $_.Name -match '^\d' } | Sort-Object Name -Descending | Select-Object -First 1
        if ($latestVer) {
            $exe = Join-Path $latestVer.FullName "GoogleDriveFS.exe"
            if (Test-Path $exe) {
                Start-Process -FilePath $exe -WindowStyle Hidden
                Start-Sleep -Seconds 20  # Give mount time to come up
                if (Get-Process -Name "GoogleDriveFS" -ErrorAction SilentlyContinue) {
                    Write-Log "Pre-flight: GoogleDriveFS restarted successfully"
                    [void]$Warnings.Add("Google Drive was down at backup start; auto-restarted before proceeding.")
                } else {
                    Write-Log "Pre-flight: Restart FAILED"
                }
            }
        }
    }
}

# ---- 1. Locate Google Drive sync root ----
$CandidatePaths = @(
    "F:\My Drive\MOCA",
    "G:\My Drive\MOCA",
    "H:\My Drive\MOCA",
    "I:\My Drive\MOCA",
    "F:\Shared drives\MOCA",
    "C:\Users\yoche\My Drive\MOCA",
    "C:\Users\yoche\Google Drive\MOCA"
)

$DrivePath = $null
foreach ($p in $CandidatePaths) {
    if (Test-Path $p) { $DrivePath = $p; break }
}

if (-not $DrivePath) {
    $errMsg = "Google Drive MOCA folder not found. Checked: $($CandidatePaths -join ', ')"
    Write-Log "ERROR: $errMsg"
    Send-Alert "MOCA Backup FAILED - Drive not found" "The backup script could not locate the MOCA folder in Google Drive.`n`n$errMsg`n`nCheck that Google Drive for Desktop is running and the MOCA folder exists in My Drive."
    exit 1
}

Write-Log "Using Drive path: $DrivePath"

# ---- 2. Create dated backup folder ----
$Today       = Get-Date -Format "yyyy-MM-dd"
$BackupDir   = Join-Path $DrivePath $Today
New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null

# ---- 3. Backup config.json ----
$ConfigSrc = Join-Path $ProjectRoot "config.json"
if (Test-Path $ConfigSrc) {
    Copy-Item $ConfigSrc -Destination (Join-Path $BackupDir "config.json") -Force
    Write-Log "Copied config.json"
} else {
    Write-Log "WARN: config.json not found"
    [void]$Warnings.Add("config.json not found at $ConfigSrc")
}

# ---- 4. Backup SQLite DB safely (using sqlite3 .backup) ----
$DbSrc  = Join-Path $ProjectRoot "data\plans.db"
$DbDst  = Join-Path $BackupDir "plans.db"

if (Test-Path $DbSrc) {
    try {
        # Pass paths via env vars to avoid quoting / Hebrew encoding issues
        $env:MOCA_DB_SRC = $DbSrc
        $env:MOCA_DB_DST = $DbDst
        $pythonCmd = @"
import sqlite3, os, sys
try:
    src = sqlite3.connect(os.environ['MOCA_DB_SRC'])
    dst = sqlite3.connect(os.environ['MOCA_DB_DST'])
    with dst:
        src.backup(dst)
    src.close(); dst.close()
    sys.stdout.write('OK')
except Exception as e:
    sys.stderr.write(repr(e))
    sys.exit(1)
"@
        $result = $pythonCmd | python 2>&1
        Remove-Item env:MOCA_DB_SRC -ErrorAction SilentlyContinue
        Remove-Item env:MOCA_DB_DST -ErrorAction SilentlyContinue

        if ($LASTEXITCODE -eq 0 -and (Test-Path $DbDst)) {
            $size = (Get-Item $DbDst).Length
            Write-Log "Copied plans.db (safe backup) - $size bytes"
        } else {
            Copy-Item $DbSrc -Destination $DbDst -Force
            Write-Log "WARN: sqlite3 backup failed ($result), used plain copy"
            [void]$Warnings.Add("SQLite safe-backup failed; used plain copy (risk of inconsistency during active scraping). Details: $result")
        }
    } catch {
        Copy-Item $DbSrc -Destination $DbDst -Force
        Write-Log "WARN: Fallback to plain copy - $_"
        [void]$Warnings.Add("SQLite safe-backup errored; used plain copy. Error: $_")
    }
} else {
    Write-Log "WARN: plans.db not found"
    [void]$Warnings.Add("plans.db not found at $DbSrc")
}

# ---- 5. Backup latest banners (today only) ----
$BannersSrc = Join-Path $ProjectRoot "data\banners"
if (Test-Path $BannersSrc) {
    $BannersDst = Join-Path $BackupDir "banners"
    New-Item -ItemType Directory -Force -Path $BannersDst | Out-Null
    Get-ChildItem $BannersSrc -Filter "*.png" | Copy-Item -Destination $BannersDst -Force
    $count = (Get-ChildItem $BannersDst -Filter "*.png").Count
    Write-Log "Copied $count banner PNGs"
}

# ---- 6. Rotation - keep only last 14 days of dated folders ----
$Cutoff = (Get-Date).AddDays(-14)
Get-ChildItem $DrivePath -Directory | Where-Object {
    $_.Name -match '^\d{4}-\d{2}-\d{2}$' -and [datetime]::ParseExact($_.Name, 'yyyy-MM-dd', $null) -lt $Cutoff
} | ForEach-Object {
    Remove-Item $_.FullName -Recurse -Force
    Write-Log "Rotated (deleted) old backup: $($_.Name)"
}

Write-Log "Backup complete."

# Send alert if any warnings accumulated (partial success)
if ($Warnings.Count -gt 0) {
    $body = "The MOCA daily backup completed with warnings:`n`n"
    foreach ($w in $Warnings) { $body += "- $w`n" }
    $body += "`nCheck $LogFile for full details."
    Send-Alert "MOCA Backup Completed WITH WARNINGS" $body
}

exit 0
