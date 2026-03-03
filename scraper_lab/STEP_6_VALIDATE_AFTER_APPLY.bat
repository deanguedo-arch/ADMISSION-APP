@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "REPO_ROOT=%SCRIPT_DIR%.."
pushd "%REPO_ROOT%" >nul

echo Running post-apply validation...
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File ".\tools\validate-canonical.ps1"
if errorlevel 1 goto :fail

if not exist ".\.venv\Scripts\python.exe" (
  echo Missing Python venv at .\.venv\Scripts\python.exe
  echo Run .\tools\setup-python.ps1 first.
  popd >nul
  exit /b 1
)

.\.venv\Scripts\python.exe .\tools\validate-dataset.py
if errorlevel 1 goto :fail

.\.venv\Scripts\python.exe .\tools\build-review-queue.py
if errorlevel 1 goto :fail

echo.
echo Validation complete.
popd >nul
exit /b 0

:fail
echo.
echo Validation failed.
popd >nul
exit /b 1

