@echo off
setlocal

cd /d "%~dp0.."
if errorlevel 1 exit /b 1

echo.
echo ==========================================
echo Admissions Checker: RUN_ALL (refresh+sync)
echo ==========================================

call ".\scripts\REFRESH_ALL.cmd" %*
if errorlevel 1 (
  echo.
  echo ERROR: REFRESH_ALL failed.
  exit /b %errorlevel%
)

call ".\scripts\SYNC_ALL.cmd"
if errorlevel 1 (
  echo.
  echo ERROR: SYNC_ALL failed.
  exit /b %errorlevel%
)

echo.
echo === RUN_ALL OK ===
exit /b 0
