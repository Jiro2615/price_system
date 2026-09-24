@echo off
setlocal
chcp 65001 >nul
echo Read-only Amazon delivery diagnostic. No DB update or orders.
py -3.12 "%~dp0diagnose_amazon_delivery.py" %*
if errorlevel 1 echo Diagnostic failed. Please share result.json or this error.
pause
