@echo off
setlocal

cd /d "%~dp0"

echo Launching Offline Snapshot local preview...
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File ".\offline_snapshot\start-preview.ps1" -Mode auto -Port 5180 -OpenBrowser
set EXITCODE=%ERRORLEVEL%

if not "%EXITCODE%"=="0" (
  echo.
  echo Preview failed with exit code %EXITCODE%.
  echo Press any key to close this window.
  pause >nul
)

endlocal
exit /b %EXITCODE%
