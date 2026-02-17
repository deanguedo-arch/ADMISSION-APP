@echo off
setlocal

cd /d "%~dp0"

echo Launching WebApp local preview (Node preferred, PowerShell fallback)...
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File ".\tools\start-webapp-preview.ps1" -Mode auto -Port 5173 -OpenBrowser
set EXITCODE=%ERRORLEVEL%

if not "%EXITCODE%"=="0" (
  echo.
  echo Preview failed with exit code %EXITCODE%.
  echo Press any key to close this window.
  pause >nul
)

endlocal
