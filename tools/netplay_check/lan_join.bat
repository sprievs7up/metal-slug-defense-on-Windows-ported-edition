@echo off
rem MSD WINDOWS S1XLV netplay acceptance (N4): LAN join (searches the LAN for a host)
cd /d "%~dp0..\.."
"windows_runtime\python.exe" "tools\netplay_check\netplay_check.py" join
pause
