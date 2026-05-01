@echo off
REM Pings Supabase health endpoint to prevent Free-tier auto-suspension.
REM Supabase Free tier suspends projects after 7 days of inactivity. This
REM script makes a single GET request, which counts as activity and resets
REM the timer.
REM
REM Schedule via Windows Task Scheduler:
REM   Trigger:  Daily at 03:00 (low-traffic hour)
REM   Action:   Start a program → this .bat file
REM
REM See docs/RUNBOOK.md → "Supabase suspended" section.

setlocal enabledelayedexpansion

REM Read SUPABASE_URL from config.json. Fall back to known project URL.
set "PROJECT_URL=https://gmfefvjdmgzluwffzrzj.supabase.co"

REM curl with -s (silent), -o nul (discard body), -w (write status code only).
REM 5s connect + 10s total timeout — if Supabase is down we want fast failure.
for /f %%i in ('curl -s -o nul -w "%%{http_code}" --connect-timeout 5 --max-time 10 "%PROJECT_URL%/auth/v1/health" 2^>nul') do set "STATUS=%%i"

REM Log to scripts\supabase_keepalive.log so we can audit later.
set "LOG_FILE=%~dp0supabase_keepalive.log"
echo %DATE% %TIME% status=%STATUS% >> "%LOG_FILE%"

REM Trim log to last 100 lines so it doesn't grow forever.
powershell -NoProfile -Command "if (Test-Path '%LOG_FILE%') { $lines = Get-Content '%LOG_FILE%' -Tail 100; $lines | Set-Content '%LOG_FILE%' -Encoding UTF8 }" 2>nul

REM Status 200/204/401 = the API is up (401 just means no auth, which is fine
REM — we only care that Supabase is reachable). Anything else is a problem.
if "%STATUS%"=="200" exit /b 0
if "%STATUS%"=="204" exit /b 0
if "%STATUS%"=="401" exit /b 0

REM Failure path — alert via the existing alert.py if it exists.
if exist "%~dp0..\alert.py" (
    python "%~dp0..\alert.py" "Supabase keep-alive failed: HTTP %STATUS%" >> "%LOG_FILE%" 2>&1
)
exit /b 1
