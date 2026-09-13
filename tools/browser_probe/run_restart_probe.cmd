@echo off
call "%~dp0run_probe.cmd" --restart-every 50 --cycles 3 --rounds 1 %*
exit /b %errorlevel%
