@echo off
setlocal
cd /d "%~dp0\..\.."
if not exist "tools\browser_probe\.venv\Scripts\python.exe" (
  echo First run: follow tools/browser_probe/README.md setup.
  pause
  exit /b 1
)
"tools\browser_probe\.venv\Scripts\python.exe" "tools\browser_probe\interaction_probe.py" %*
set "probe_result=%errorlevel%"
echo Result code: %probe_result%
pause
exit /b %probe_result%
