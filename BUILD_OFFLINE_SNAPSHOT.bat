@echo off
setlocal
cd /d "%~dp0"

title Build Offline Snapshot
echo.
echo ==========================================
echo Build Offline Admissions Snapshot
echo ==========================================
echo.

set "PY=.\.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

echo Using Python: %PY%
echo.
"%PY%" ".\offline_snapshot\build_snapshot.py" %*
set "EXITCODE=%ERRORLEVEL%"

echo.
if not "%EXITCODE%"=="0" (
  echo Build failed with exit code %EXITCODE%.
) else (
  echo Build completed successfully.
  echo Output: .\offline_snapshot\site\index.html
)
echo Press any key to close this window.
pause >nul

endlocal
exit /b %EXITCODE%
