@echo off
setlocal

set PYTHON="C:\Users\yoche\AppData\Local\Programs\Python\Python313\python.exe"
set APP="D:\השוואת MASS MARKET\app.py"
set WORKDIR=D:\השוואת MASS MARKET
set LOGFILE="D:\השוואת MASS MARKET\scripts\flask_watchdog.log"

:loop
echo [%date% %time%] Flask starting... >> %LOGFILE%
cd /d %WORKDIR%
%PYTHON% %APP%
echo [%date% %time%] Flask exited (code %errorlevel%). Restarting in 15 seconds... >> %LOGFILE%
timeout /t 15 /nobreak > nul
goto loop
