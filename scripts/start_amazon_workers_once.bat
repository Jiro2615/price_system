@echo off
setlocal

cd /d "%~dp0"
set "SCRIPT=%~dp0start_amazon_workers.ps1"

if not exist "%SCRIPT%" (
  echo start_amazon_workers.ps1 not found.
  echo %SCRIPT%
  pause
  exit /b 1
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT%" -PopupInput -Once

echo.
echo ExitCode: %ERRORLEVEL%
pause
endlocal
