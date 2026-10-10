@echo off
rem MSD WINDOWS S1XLV netplay acceptance (N4): LAN / direct host (waits for the opponent on UDP 47631, answers LAN discovery on UDP 47630)
cd /d "%~dp0..\.."
"windows_runtime\python.exe" "tools\netplay_check\netplay_check.py" host
pause
