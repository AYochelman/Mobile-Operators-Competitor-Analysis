@echo off
REM ===================================================================
REM  Restart the Flask server so it reloads backend code (db.py / app.py).
REM
REM  Flask is launched ELEVATED by the Task Scheduler task "CellularComparison"
REM  (flask_watchdog.bat), so a normal shell cannot kill it. You MUST run this
REM  script as administrator:  right-click restart_flask.bat -> "Run as administrator".
REM
REM  It kills whatever process is LISTENING on port 5000; flask_watchdog.bat then
REM  relaunches `python app.py` (with the new code) within ~15 seconds.
REM ===================================================================

setlocal
set "FLASKPID="
for /f "tokens=5" %%a in ('netstat -aon ^| findstr "LISTENING" ^| findstr ":5000"') do set "FLASKPID=%%a"

if "%FLASKPID%"=="" (
  echo No process is LISTENING on port 5000 -- is Flask running?
  echo.
  pause
  exit /b 1
)

echo Flask is running on port 5000 as PID %FLASKPID%.
echo Killing it so the watchdog reloads the new code...
taskkill /F /PID %FLASKPID%

if errorlevel 1 (
  echo.
  echo *** Could not kill PID %FLASKPID% -- "Access is denied". ***
  echo You are NOT running as administrator. Right-click this file
  echo and choose "Run as administrator", then try again.
) else (
  echo.
  echo Done. The watchdog will relaunch Flask with the new code in ~15 seconds.
  echo Wait ~30s, then hard-refresh the app (Ctrl+Shift+R).
)
echo.
pause
endlocal
