@echo off
setlocal

cd /d "%~dp0"

echo Launching WebApp local preview (Node-only mode)...
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File ".\tools\start-webapp-preview.ps1" -Mode node -Port 5173 -OpenBrowser
set EXITCODE=%ERRORLEVEL%

if not "%EXITCODE%"=="0" (
  echo.
  echo Node preview failed. If Node is not available, use START_WEBAPP_PREVIEW.bat for auto fallback.
  echo Press any key to close this window.
  pause >nul
)

endlocal
