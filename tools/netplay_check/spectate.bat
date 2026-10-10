@echo off
rem MSD WINDOWS S1XLV netplay acceptance (N5.5): Spectate a match.
rem   spectate.bat                      searches the LAN for a room
rem   spectate.bat IP:PORT              direct, example: spectate.bat 203.0.113.7:47631
rem   spectate.bat SERVER:PORT CODE     rendezvous, example: spectate.bat 203.0.113.9:47632 K7P2QX
cd /d "%~dp0..\.."
if "%~1"=="" (
  "windows_runtime\python.exe" "tools\netplay_check\netplay_check.py" spectate
) else if "%~2"=="" (
  "windows_runtime\python.exe" "tools\netplay_check\netplay_check.py" spectate --address %1
) else (
  "windows_runtime\python.exe" "tools\netplay_check\netplay_check.py" spectate --server %1 --code %2
)
pause
