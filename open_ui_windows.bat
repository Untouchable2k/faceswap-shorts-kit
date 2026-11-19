@echo off
REM Opens the FaceFusion web interface in your browser (expert mode).
chcp 65001 >nul
set "PYTHONUTF8=1"
if not exist "%~dp0tools\env\python.exe" (
  echo The kit is not installed yet. Double-click setup_windows.bat first.
  pause
  exit /b 1
)
"%~dp0tools\env\python.exe" "%~dp0swap.py" --ui
pause
