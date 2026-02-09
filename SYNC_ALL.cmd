@echo off
powershell -ExecutionPolicy Bypass -File ".\tools\sync-all-to-sheets.ps1" %*
