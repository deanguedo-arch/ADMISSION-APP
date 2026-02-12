@echo off
setlocal

rem Runner-safe wrapper: repo-relative, no pause, fail-fast.
cd /d "%~dp0.."
if errorlevel 1 exit /b 1

echo.
echo === SYNC (publish to Google Sheets) ===

if not exist ".\config\sheets_sync.json" (
  echo ERROR: Missing config\sheets_sync.json.
  echo - Copy config\sheets_sync.json.example to config\sheets_sync.json and fill values,
  echo   or in GitHub Actions write it from secrets (SHEETS_WEBHOOK_URL / SHEETS_SYNC_TOKEN).
  exit /b 1
)

rem Ensure venv exists (push_to_sheets.py uses requests; pipeline uses more deps).
powershell -NoProfile -ExecutionPolicy Bypass -File ".\tools\setup-python.ps1"
if errorlevel 1 exit /b %errorlevel%

powershell -NoProfile -ExecutionPolicy Bypass -File ".\tools\sync-all-to-sheets.ps1" %*
if errorlevel 1 exit /b %errorlevel%

echo.
echo === SYNC OK ===
exit /b 0
