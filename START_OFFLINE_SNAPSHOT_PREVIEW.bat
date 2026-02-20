@echo off
setlocal

cd /d "%~dp0"

echo Updating Offline Snapshot...
echo.

set "PY=.\.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

"%PY%" ".\offline_snapshot\build_snapshot.py"
set BUILD_EXIT=%ERRORLEVEL%
if not "%BUILD_EXIT%"=="0" (
  echo.
  echo Snapshot build failed with exit code %BUILD_EXIT%.
  echo Press any key to close this window.
  pause >nul
  endlocal
  exit /b %BUILD_EXIT%
)

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
