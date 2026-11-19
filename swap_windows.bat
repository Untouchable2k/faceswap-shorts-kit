@echo off
REM Swap your face into every video in clips -> output. Extra options: swap_windows.bat --help
chcp 65001 >nul
set "PYTHONUTF8=1"
if not exist "%~dp0tools\env\python.exe" (
  echo The kit is not installed yet. Double-click setup_windows.bat first.
  pause
  exit /b 1
)
"%~dp0tools\env\python.exe" "%~dp0swap.py" %*
pause
