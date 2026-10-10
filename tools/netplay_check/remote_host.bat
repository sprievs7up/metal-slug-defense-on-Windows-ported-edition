@echo off
rem MSD WINDOWS S1XLV netplay acceptance (N4): Remote host via rendezvous server, example: remote_host.bat 203.0.113.9:47632
if "%1"=="" (
  echo Usage: remote_host.bat SERVER:PORT
  echo Remote host via rendezvous server, example: remote_host.bat 203.0.113.9:47632
  pause
  exit /b 1
)
cd /d "%~dp0..\.."
"windows_runtime\python.exe" "tools\netplay_check\netplay_check.py" rdv-host --server %1
pause
