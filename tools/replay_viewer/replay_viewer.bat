@echo off
rem MSD WINDOWS S1XLV replay viewer (N5.5): play a .msdreplay file. Drag a replay onto this file, or run it to play the newest replay.
cd /d "%~dp0..\.."
"windows_runtime\python.exe" "tools\replay_viewer\replay_viewer.py" %*
if errorlevel 1 pause
