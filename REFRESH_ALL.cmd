@echo off
setlocal
cd /d "%~dp0"
call ".\scripts\REFRESH_ALL.cmd" %*
exit /b %errorlevel%
