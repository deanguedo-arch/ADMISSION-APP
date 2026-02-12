@echo off
cd /d "%~dp0"
call ".\scripts\SYNC_ALL.cmd" %*
exit /b %errorlevel%
