@echo off
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File ".\tools\sync-elective-rules.ps1" %*
exit /b %errorlevel%
