@echo off
rem MSD WINDOWS S1XLV netplay acceptance (N4): Remote join, example: remote_join.bat 203.0.113.9:47632 K7P2QX
if "%2"=="" (
  echo Usage: remote_join.bat SERVER:PORT CODE
  echo Remote join, example: remote_join.bat 203.0.113.9:47632 K7P2QX
  pause
  exit /b 1
)
cd /d "%~dp0..\.."
"windows_runtime\python.exe" "tools\netplay_check\netplay_check.py" rdv-join --server %1 --code %2
pause
