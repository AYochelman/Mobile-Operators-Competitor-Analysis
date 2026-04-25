@echo off
setlocal

set WORKDIR=D:\השוואת MASS MARKET\mass-market-app
set LOGFILE="D:\השוואת MASS MARKET\scripts\vite_watchdog.log"

:loop
echo [%date% %time%] Vite starting... >> %LOGFILE%
cd /d %WORKDIR%
npm run dev
echo [%date% %time%] Vite exited (code %errorlevel%). Restarting in 10 seconds... >> %LOGFILE%
timeout /t 10 /nobreak > nul
goto loop
