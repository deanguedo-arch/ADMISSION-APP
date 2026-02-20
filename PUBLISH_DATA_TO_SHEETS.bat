@echo off
setlocal
cd /d "%~dp0"

title Publish Admissions Data To Sheets
echo.
echo ==============================================
echo Publish Admissions Data To Google Sheets
echo ==============================================
echo.
echo This will run refresh + validation + sync.
echo.
echo 1. Fast publish (skip scrape)  [Recommended]
echo 2. Full publish (run scrape)
echo.
set "MODE=1"
set /p MODE=Choose 1 or 2 [1]:

if "%MODE%"=="" set "MODE=1"

set "RUN_ARGS="
set "MODE_LABEL="

if "%MODE%"=="1" (
  set "RUN_ARGS=-SkipScrape"
  set "MODE_LABEL=FAST"
)
if "%MODE%"=="2" (
  set "RUN_ARGS="
  set "MODE_LABEL=FULL"
)
if "%MODE_LABEL%"=="" (
  echo.
  echo Invalid choice "%MODE%". Use 1 or 2.
  echo Press any key to close this window.
  pause >nul
  exit /b 1
)

echo.
echo Running %MODE_LABEL% publish...
echo Command: .\scripts\RUN_ALL.cmd %RUN_ARGS%
echo.

call ".\scripts\RUN_ALL.cmd" %RUN_ARGS%
set "EXITCODE=%ERRORLEVEL%"

echo.
if not "%EXITCODE%"=="0" (
  echo Publish failed with exit code %EXITCODE%.
) else (
  echo Publish completed successfully.
)
echo Press any key to close this window.
pause >nul

endlocal
exit /b %EXITCODE%
