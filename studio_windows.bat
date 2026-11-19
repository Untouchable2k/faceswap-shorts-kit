@echo off
REM Opens the Face-Swap Studio (step-by-step app) in your browser. Keep this window open while using it.
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
echo Starting the Face-Swap Studio... your browser opens in a moment. Keep this window open.
"%~dp0tools\env\python.exe" "%~dp0studio.py" %*
if errorlevel 1 (
  echo.
  echo The Studio stopped with an error ^(see above^). Common causes: no internet
  echo during a model download, out of GPU memory, or an outdated GPU driver.
  echo See README_START_HERE.txt ^(TROUBLESHOOTING^) for details.
)
pause
