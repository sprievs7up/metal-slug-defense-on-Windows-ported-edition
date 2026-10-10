@echo off
rem MSD WINDOWS S1XLV netplay acceptance (N4): Run the rendezvous server on this computer (UDP 47632)
cd /d "%~dp0..\.."
"windows_runtime\python.exe" "tools\netplay_check\netplay_check.py" server
pause
