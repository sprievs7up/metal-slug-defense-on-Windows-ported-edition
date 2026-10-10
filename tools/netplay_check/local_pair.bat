@echo off
rem MSD WINDOWS S1XLV netplay acceptance (N4, N5, N5.5, N6a): two clients on this computer, host and join run as two separate game processes
rem Usage: double-click and choose a test number, or run "local_pair.bat 1" (0 runs tests 1-5, 7, 8 and 9)
cd /d "%~dp0..\.."
"windows_runtime\python.exe" "tools\netplay_check\netplay_check.py" local-pair %*
pause
