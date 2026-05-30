@echo off
setlocal

rem Derive project root from the script's own location so this works on any drive/folder.
rem %~dp0 = directory containing this .bat (with trailing backslash) = ...\scripts\
set "SCRIPTDIR=%~dp0"
set "WORKDIR=%SCRIPTDIR%.."
set "APP=%WORKDIR%\app.py"
set "LOGFILE=%SCRIPTDIR%flask_watchdog.log"
set "APPLOG=%SCRIPTDIR%flask_app.log"
set "PYTHON=python"

:loop
echo [%date% %time%] Flask starting... >> "%LOGFILE%"
echo [%date% %time%] ===== Flask starting ===== >> "%APPLOG%"
cd /d "%WORKDIR%"
%PYTHON% -u "%APP%" >> "%APPLOG%" 2>&1
echo [%date% %time%] Flask exited (code %errorlevel%). Restarting in 15 seconds... >> "%LOGFILE%"
echo [%date% %time%] ===== Flask exited (code %errorlevel%) ===== >> "%APPLOG%"
timeout /t 15 /nobreak > nul
goto loop
