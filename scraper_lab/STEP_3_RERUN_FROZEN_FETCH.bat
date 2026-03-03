@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "REPO_ROOT=%SCRIPT_DIR%.."
pushd "%REPO_ROOT%" >nul

set "CYCLE_ID=%~1"

if "%CYCLE_ID%"=="" if exist "%SCRIPT_DIR%CURRENT_CYCLE.txt" (
  for /f "usebackq delims=" %%A in ("%SCRIPT_DIR%CURRENT_CYCLE.txt") do set "CYCLE_ID=%%A"
)

if "%CYCLE_ID%"=="" (
  set /p CYCLE_ID=Enter cycle ID to rerun, example lab-1: 
)

if "%CYCLE_ID%"=="" (
  echo Cycle ID is required.
  popd >nul
  exit /b 1
)

>"%SCRIPT_DIR%CURRENT_CYCLE.txt" echo %CYCLE_ID%
echo Re-running with frozen fetch for cycle: %CYCLE_ID%
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File ".\scraper_lab\run.ps1" -CycleId "%CYCLE_ID%" -ReuseFrozenFetch %2 %3 %4 %5 %6 %7 %8 %9
set "EXIT_CODE=%ERRORLEVEL%"

popd >nul
exit /b %EXIT_CODE%
