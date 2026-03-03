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
  set /p CYCLE_ID=Enter cycle ID to open, example lab-1: 
)

if "%CYCLE_ID%"=="" (
  echo Cycle ID is required.
  popd >nul
  exit /b 1
)

set "RUN_DIR=.\scraper_lab\runs\%CYCLE_ID%"
if not exist "%RUN_DIR%\diff" if exist "%RUN_DIR%\canonical334\diff" (
  set "RUN_DIR=%RUN_DIR%\canonical334"
)
if not exist "%RUN_DIR%" (
  echo Run folder not found: %RUN_DIR%
  popd >nul
  exit /b 1
)

echo Opening diff files for cycle: %CYCLE_ID%
start "" "%RUN_DIR%\diff\gate_report.md"
if exist "%RUN_DIR%\diff\original_vs_new_summary.md" start "" "%RUN_DIR%\diff\original_vs_new_summary.md"
if exist "%RUN_DIR%\diff\original_vs_new_field_changes.csv" start "" "%RUN_DIR%\diff\original_vs_new_field_changes.csv"
if exist "%RUN_DIR%\diff\original_vs_new_missing_programs.csv" start "" "%RUN_DIR%\diff\original_vs_new_missing_programs.csv"
if exist "%RUN_DIR%\diff\proposed_removals.csv" start "" "%RUN_DIR%\diff\proposed_removals.csv"
start "" "%RUN_DIR%\diff\coverage_diff.csv"
start "" "%RUN_DIR%\diff\field_changes.csv"
start "" explorer "%RUN_DIR%\diff"

popd >nul
exit /b 0
