# scripts/backup_restore_test.ps1
#
# Quarterly DR drill — verifies that the latest Google Drive backup is
# actually restorable. Without this, we don't know if backup_to_drive.ps1
# is producing usable archives.
#
# Run manually every 3 months, or schedule via Task Scheduler with trigger
# "First Sunday of every 3rd month at 04:00".
#
# Usage:
#   .\backup_restore_test.ps1                    # test latest backup
#   .\backup_restore_test.ps1 -BackupZip <path>  # test a specific zip
#
# Exit codes:
#   0 — backup verified
#   1 — restore failed (see alerts)

param(
    [string]$BackupZip = "",
    [string]$DriveBackupRoot = "G:\My Drive\MOCA-backups",
    [string]$TempRoot = "$env:TEMP\moca-restore-test"
)

$ErrorActionPreference = "Stop"
$failures = @()

function Test-Step {
    param([string]$Name, [scriptblock]$Block)
    try {
        & $Block
        Write-Host "  PASS — $Name" -ForegroundColor Green
    } catch {
        Write-Host "  FAIL — $Name : $_" -ForegroundColor Red
        $script:failures += "$Name : $_"
    }
}

Write-Host "MOCA backup restore test starting..." -ForegroundColor Cyan
Write-Host ""

# ─── Step 1: Locate latest backup ─────────────────────────────────────────────
if (-not $BackupZip) {
    if (-not (Test-Path $DriveBackupRoot)) {
        Write-Host "ERROR: Google Drive backup root not found at $DriveBackupRoot" -ForegroundColor Red
        Write-Host "Is GoogleDriveFS mounted? Check scripts/drive_monitor.ps1" -ForegroundColor Yellow
        exit 1
    }
    $latest = Get-ChildItem $DriveBackupRoot -Filter "*.zip" |
              Sort-Object LastWriteTime -Descending |
              Select-Object -First 1
    if (-not $latest) {
        Write-Host "ERROR: No .zip backups found in $DriveBackupRoot" -ForegroundColor Red
        exit 1
    }
    $BackupZip = $latest.FullName
}

$ageDays = ((Get-Date) - (Get-Item $BackupZip).LastWriteTime).TotalDays
Write-Host "Backup: $BackupZip"
Write-Host "Age:    $([math]::Round($ageDays, 1)) days"
Write-Host ""

if ($ageDays -gt 7) {
    Write-Host "WARNING: backup is more than 7 days old" -ForegroundColor Yellow
    $script:failures += "Backup older than 7 days ($([math]::Round($ageDays, 1)) days)"
}

# ─── Step 2: Extract to temp folder ───────────────────────────────────────────
if (Test-Path $TempRoot) { Remove-Item $TempRoot -Recurse -Force }
New-Item -ItemType Directory -Path $TempRoot -Force | Out-Null

Test-Step "Extract zip" {
    Expand-Archive -Path $BackupZip -DestinationPath $TempRoot -Force
}

# ─── Step 3: Verify expected files ────────────────────────────────────────────
$expected = @("config.json", "data\plans.db")
foreach ($f in $expected) {
    $full = Join-Path $TempRoot $f
    Test-Step "File exists: $f" {
        if (-not (Test-Path $full)) { throw "missing" }
        if ((Get-Item $full).Length -eq 0) { throw "empty" }
    }
}

# ─── Step 4: SQLite integrity ─────────────────────────────────────────────────
$dbPath = Join-Path $TempRoot "data\plans.db"
$sqliteExe = Get-Command sqlite3 -ErrorAction SilentlyContinue
if (-not $sqliteExe) {
    Write-Host "  SKIP — SQLite integrity check (sqlite3.exe not on PATH)" -ForegroundColor Yellow
    Write-Host "         Install via: winget install SQLite.SQLite" -ForegroundColor Yellow
} else {
    Test-Step "SQLite PRAGMA integrity_check" {
        $result = & sqlite3 $dbPath "PRAGMA integrity_check;"
        if ($result -ne "ok") { throw "result was: $result" }
    }

    Test-Step "Plans table has rows (>= 100)" {
        $count = & sqlite3 $dbPath "SELECT COUNT(*) FROM plans;"
        if ([int]$count -lt 100) { throw "only $count plans found" }
    }

    Test-Step "All 8 domestic carriers present" {
        $carriers = & sqlite3 $dbPath "SELECT DISTINCT carrier FROM plans;"
        $required = @("partner", "pelephone", "hotmobile", "cellcom", "mobile019", "xphone", "wecom", "neptucom")
        foreach ($c in $required) {
            if ($carriers -notcontains $c) { throw "missing carrier: $c" }
        }
    }
}

# ─── Step 5: Verify config.json shape ─────────────────────────────────────────
Test-Step "config.json parseable + has required keys" {
    $cfg = Get-Content (Join-Path $TempRoot "config.json") -Raw | ConvertFrom-Json
    $required = @("api_key", "telegram_bot_token", "telegram_chat_id")
    foreach ($k in $required) {
        if (-not $cfg.$k) { throw "missing key: $k" }
    }
}

# ─── Step 6: Verify banner PNGs (best-effort) ─────────────────────────────────
$bannerDir = Join-Path $TempRoot "data\banners"
if (Test-Path $bannerDir) {
    Test-Step "Banner PNGs exist (at least 4)" {
        $count = (Get-ChildItem $bannerDir -Filter "*.png").Count
        if ($count -lt 4) { throw "only $count banner PNGs found" }
    }
} else {
    Write-Host "  SKIP — banners/ folder not in this backup (acceptable)" -ForegroundColor Yellow
}

# ─── Cleanup ──────────────────────────────────────────────────────────────────
Remove-Item $TempRoot -Recurse -Force -ErrorAction SilentlyContinue

# ─── Report ───────────────────────────────────────────────────────────────────
Write-Host ""
if ($failures.Count -eq 0) {
    Write-Host "ALL CHECKS PASSED — backup is restorable." -ForegroundColor Green
    exit 0
} else {
    Write-Host "FAILED CHECKS:" -ForegroundColor Red
    $failures | ForEach-Object { Write-Host "  - $_" -ForegroundColor Red }
    Write-Host ""
    Write-Host "Send alert via alert.py..." -ForegroundColor Yellow
    $alertScript = Join-Path $PSScriptRoot "..\alert.py"
    if (Test-Path $alertScript) {
        $msg = "MOCA backup restore test FAILED: " + ($failures -join "; ")
        & python $alertScript $msg
    }
    exit 1
}
