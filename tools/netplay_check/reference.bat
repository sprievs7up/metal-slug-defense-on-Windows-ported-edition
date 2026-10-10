@echo off
rem MSD WINDOWS S1XLV netplay acceptance (N4): Single-computer reference run (no network)
cd /d "%~dp0..\.."
"windows_runtime\python.exe" "tools\netplay_check\netplay_check.py" reference
pause
