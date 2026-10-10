@echo off
rem MSD WINDOWS S1XLV netplay acceptance (N5.5): Re-simulate a replay and compare it with the recorded checksums
rem Example: replay_check.bat "verification\netplay_check\20261010_120000_host\replays\xxx.msdreplay"
if "%~1"=="" (
  echo Usage: replay_check.bat REPLAY_FILE
  echo Re-simulate a replay without a window and compare it with the checksums recorded in the match
  pause
  exit /b 1
)
cd /d "%~dp0..\.."
"windows_runtime\python.exe" "tools\netplay_check\netplay_check.py" replay %1 --seek-test
pause
