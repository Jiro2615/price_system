@echo off
setlocal

cd /d "%~dp0"
set "SCRIPT=%~dp0start_rakuten_update_worker.ps1"

if not exist "%SCRIPT%" (
  echo start_rakuten_update_worker.ps1 not found.
  echo %SCRIPT%
  pause
  exit /b 1
)

echo Launch mode: Rakuten update worker execute once
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT%" -Once

echo.
echo ExitCode: %ERRORLEVEL%
pause
endlocal
