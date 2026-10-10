@echo off
rem MSD WINDOWS S1XLV netplay acceptance (N4): Direct-connect host, asks the router to forward UDP 47631 (UPnP)
cd /d "%~dp0..\.."
"windows_runtime\python.exe" "tools\netplay_check\netplay_check.py" host --upnp
pause
