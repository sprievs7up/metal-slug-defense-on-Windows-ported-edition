@echo off
rem MSD WINDOWS S1XLV netplay acceptance (N4): Compare two result.json files
if "%2"=="" (
  echo Usage: compare.bat RESULT_A RESULT_B
  echo Compare two result.json files
  pause
  exit /b 1
)
cd /d "%~dp0..\.."
"windows_runtime\python.exe" "tools\netplay_check\netplay_check.py" compare %1 %2
pause
