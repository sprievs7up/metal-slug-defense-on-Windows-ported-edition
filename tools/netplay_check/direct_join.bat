@echo off
rem MSD WINDOWS S1XLV netplay acceptance (N4): Direct-connect join, example: direct_join.bat 203.0.113.7:47631
if "%1"=="" (
  echo Usage: direct_join.bat IP:PORT
  echo Direct-connect join, example: direct_join.bat 203.0.113.7:47631
  pause
  exit /b 1
)
cd /d "%~dp0..\.."
"windows_runtime\python.exe" "tools\netplay_check\netplay_check.py" join --address %1
pause
