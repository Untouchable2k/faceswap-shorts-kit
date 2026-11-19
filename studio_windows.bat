@echo off
REM Opens the Face-Swap Studio (step-by-step app) in your browser. Keep this window open while using it.
chcp 65001 >nul
set "PYTHONUTF8=1"
if not exist "%~dp0tools\env\python.exe" (
  echo The kit is not installed yet. Double-click setup_windows.bat first.
  pause
  exit /b 1
)
echo Starting the Face-Swap Studio... your browser opens in a moment. Keep this window open.
"%~dp0tools\env\python.exe" "%~dp0studio.py" %*
pause
