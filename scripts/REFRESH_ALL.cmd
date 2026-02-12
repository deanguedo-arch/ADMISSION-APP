@echo off
setlocal

rem Runner-safe wrapper: repo-relative, no pause, fail-fast.
cd /d "%~dp0.."
if errorlevel 1 exit /b 1

echo.
echo === REFRESH (dataset rebuild + pipeline refresh) ===

rem Ensure venv exists and deps installed (uses pipeline\requirements.txt).
powershell -NoProfile -ExecutionPolicy Bypass -File ".\tools\setup-python.ps1"
if errorlevel 1 exit /b %errorlevel%

rem Refresh pipeline, but do NOT publish to Sheets here (sync is handled by SYNC_ALL.cmd).
set "SYNC_FLAG=-SkipSync"
echo %* | findstr /i /c:"-SkipSync" >nul
if %errorlevel%==0 set "SYNC_FLAG="
powershell -NoProfile -ExecutionPolicy Bypass -File ".\tools\refresh-all.ps1" %SYNC_FLAG% %*
if errorlevel 1 exit /b %errorlevel%

echo.
echo === REFRESH OK ===
exit /b 0
