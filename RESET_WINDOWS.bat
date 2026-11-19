@echo off
REM Removes the installed environment (tools\, facefusion\) so setup_windows.bat
REM can rebuild it from scratch. Your clips, face photos and output are NOT touched.
setlocal EnableExtensions
cd /d "%~dp0"
echo This will DELETE:
echo   %CD%\tools
echo   %CD%\facefusion
echo Your clips, me, and output folders are kept.
choice /c YN /m "Delete these and start fresh"
if errorlevel 2 (
  echo Cancelled, nothing was deleted.
  pause
  exit /b 0
)
if exist tools rmdir /s /q tools
if exist facefusion rmdir /s /q facefusion
echo Done. Run setup_windows.bat to reinstall.
pause
