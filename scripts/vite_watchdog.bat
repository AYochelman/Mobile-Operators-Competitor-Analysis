@echo off
setlocal

rem Derive paths from the script's own location so this works on any drive/folder.
rem %~dp0 = ...\scripts\ (with trailing backslash)
set "SCRIPTDIR=%~dp0"
set "WORKDIR=%SCRIPTDIR%..\mass-market-app"
set "LOGFILE=%SCRIPTDIR%vite_watchdog.log"

:loop
echo [%date% %time%] Vite starting... >> "%LOGFILE%"
cd /d "%WORKDIR%"
npm run dev
echo [%date% %time%] Vite exited (code %errorlevel%). Restarting in 10 seconds... >> "%LOGFILE%"
timeout /t 10 /nobreak > nul
goto loop
