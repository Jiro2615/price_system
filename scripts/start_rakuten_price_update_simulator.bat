@echo off
setlocal

cd /d "%~dp0"
set "SCRIPT=%~dp0start_rakuten_price_update_simulator.ps1"

if not exist "%SCRIPT%" (
  echo start_rakuten_price_update_simulator.ps1 not found.
  echo %SCRIPT%
  pause
  exit /b 1
)

echo Launch mode: Rakuten price update simulator loop
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT%"

echo.
echo ExitCode: %ERRORLEVEL%
pause
endlocal
