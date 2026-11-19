@echo off
REM Swap your face into every video in clips -> output. Extra options: swap_windows.bat --help
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul
set "PYTHONUTF8=1"
if not exist "%~dp0tools\env\python.exe" (
  echo The kit is not installed yet. Double-click setup_windows.bat first.
  pause
  exit /b 1
)
"%~dp0tools\env\python.exe" --version >nul 2>nul
if errorlevel 1 (
  echo The installed Python environment looks broken ^(tools\env^).
  echo Run RESET_WINDOWS.bat, then setup_windows.bat again.
  pause
  exit /b 1
)
"%~dp0tools\env\python.exe" "%~dp0swap.py" %*
pause
