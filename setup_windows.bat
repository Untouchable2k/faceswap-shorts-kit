@echo off
REM One-time setup for the face-swap kit on Windows 10/11.
REM Usage: double-click, or from a terminal:
REM    setup_windows.bat            (auto: NVIDIA -> cuda, otherwise directml for AMD/Intel GPUs)
REM    setup_windows.bat cpu        (force CPU)
REM    setup_windows.bat cuda       (force NVIDIA CUDA)
REM    setup_windows.bat directml   (any DirectX 12 GPU: AMD / Intel / NVIDIA)
REM Needs: internet, ~20 GB disk. No admin needed. Everything installs inside this folder.
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul
set "PYTHONUTF8=1"
set "FACEFUSION_VERSION=3.9.2"
set "PYTHON_VERSION=3.12"
set "CUDA_VERSION=12.8"
REM curl flags so a flaky connection retries instead of killing the whole install.
set "CURL_RETRY=--retry 5 --retry-delay 5 --retry-connrefused"

cd /d "%~dp0"
set "KIT=%CD%"
set "LOGFILE=%KIT%\setup_log.txt"
> "%LOGFILE%" echo Face-Swap Kit setup started %DATE% %TIME%

if not "%KIT%"=="%KIT: =%" (
  echo ERROR: the folder path contains a space: %KIT%
  echo Move this folder somewhere like C:\faceswap and run again.
  goto :fail
)

where curl >nul 2>nul || (
  echo ERROR: "curl" is missing. Update Windows ^(Windows 10 version 1803 or newer, or Windows 11^) and run again.
  goto :fail
)
where tar >nul 2>nul || (
  echo ERROR: "tar" is missing. Update Windows ^(Windows 10 version 1803 or newer, or Windows 11^) and run again.
  goto :fail
)

REM --- Pre-flight checks: catch the Windows-specific gotchas before we spend 10-30 minutes ---
call :log "Checking folder location, disk space and internet"

echo %KIT% | findstr /i "OneDrive" >nul
if not errorlevel 1 (
  echo WARNING: this folder is inside OneDrive ^(%KIT%^).
  echo OneDrive can lock files mid-download and sync huge model files, which breaks setup.
  echo Recommended: move this folder to C:\faceswap and run setup again.
  choice /c YN /m "Continue anyway from inside OneDrive"
  if errorlevel 2 goto :fail
)

for /f "usebackq delims=" %%A in (`powershell -NoProfile -Command "[bool]('%KIT%' -match '[^\x00-\x7F]')" 2^>nul`) do set "NONASCII=%%A"
if /i "%NONASCII%"=="True" (
  echo WARNING: the folder path has non-English/accented characters:
  echo   %KIT%
  echo Some Python/AI tools still mishandle these. If setup fails strangely,
  echo move this folder to a simple path like C:\faceswap and try again.
)

for /f "usebackq delims=" %%A in (`powershell -NoProfile -Command "[math]::Round((Get-PSDrive -Name ('%KIT:~0,1%')).Free/1GB)" 2^>nul`) do set "FREEGB=%%A"
if defined FREEGB (
  if %FREEGB% LSS 20 (
    echo WARNING: drive %KIT:~0,1%: has only %FREEGB% GB free. This kit needs about 20 GB.
    choice /c YN /m "Continue anyway"
    if errorlevel 2 goto :fail
  ) else (
    call :log "Disk space OK: %FREEGB% GB free on %KIT:~0,1%:"
  )
)

curl -s -o nul --max-time 8 https://github.com
if errorlevel 1 (
  echo ERROR: can't reach github.com. Check your internet connection ^(and that no
  echo VPN/firewall/antivirus is blocking curl.exe^), then run this again.
  goto :fail
)

set "MODE=%~1"
if "%MODE%"=="" set "MODE=auto"
if /i "%MODE%"=="auto" (
  where nvidia-smi >nul 2>nul && (set "MODE=cuda") || (set "MODE=directml")
)
call :log "Mode: %MODE%"

if not exist tools mkdir tools
if not exist clips mkdir clips
if not exist me mkdir me
if not exist output mkdir output

REM 1) Miniforge (private conda) ----------------------------------------------
if not exist "%KIT%\tools\miniforge\Scripts\conda.exe" (
  call :log "Downloading Miniforge"
  curl -L --fail %CURL_RETRY% -o "%KIT%\tools\miniforge.exe" https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Windows-x86_64.exe || goto :fail
  call :log "Installing Miniforge into tools\miniforge (takes a few minutes, no window appears)"
  start /wait "" "%KIT%\tools\miniforge.exe" /InstallationType=JustMe /RegisterPython=0 /AddToPath=0 /NoRegistry=1 /NoShortcuts=1 /S /D=%KIT%\tools\miniforge
  del "%KIT%\tools\miniforge.exe"
)
set "CONDA=%KIT%\tools\miniforge\Scripts\conda.exe"
if not exist "%CONDA%" ( echo ERROR: Miniforge install failed. & goto :fail )

REM 2) Python + ffmpeg (+ CUDA runtime libraries) -----------------------------
set "PKGS=python=%PYTHON_VERSION% ffmpeg pip deno"
if /i "%MODE%"=="cuda" set "PKGS=%PKGS% cuda-runtime=%CUDA_VERSION% cudnn=9"
if exist "%KIT%\tools\env\python.exe" "%KIT%\tools\env\python.exe" --version >nul 2>nul
if not exist "%KIT%\tools\env\python.exe" (
  call :log "Creating environment"
  "%CONDA%" create -y -p "%KIT%\tools\env" -c conda-forge %PKGS% || goto :fail
) else if errorlevel 1 (
  echo The existing Python environment looks broken. Removing it and rebuilding...
  rmdir /s /q "%KIT%\tools\env"
  "%CONDA%" create -y -p "%KIT%\tools\env" -c conda-forge %PKGS% || goto :fail
) else (
  call :log "Environment exists, making sure packages are present"
  "%CONDA%" install -y -p "%KIT%\tools\env" -c conda-forge %PKGS% || goto :fail
)
set "PY=%KIT%\tools\env\python.exe"

REM 3) FaceFusion ---------------------------------------------------------------
if not exist "%KIT%\facefusion\facefusion.py" (
  call :log "Downloading FaceFusion %FACEFUSION_VERSION%"
  curl -L --fail %CURL_RETRY% -o "%KIT%\tools\facefusion.zip" https://github.com/facefusion/facefusion/archive/refs/tags/%FACEFUSION_VERSION%.zip || goto :fail
  if not exist facefusion mkdir facefusion
  tar -xf "%KIT%\tools\facefusion.zip" -C "%KIT%\facefusion" --strip-components=1 || goto :fail
  del "%KIT%\tools\facefusion.zip"
)

set "ORT=default"
if /i "%MODE%"=="cuda" set "ORT=cuda@12"
if /i "%MODE%"=="directml" set "ORT=directml"
if /i "%MODE%"=="openvino" set "ORT=openvino"
call :log "Installing FaceFusion python packages (%ORT%)"
set "CONDA_PREFIX=%KIT%\tools\env"
set "PATH=%KIT%\tools\env;%KIT%\tools\env\Library\bin;%KIT%\tools\env\Scripts;%PATH%"
pushd "%KIT%\facefusion"
"%PY%" install.py %ORT% || (popd & goto :fail)
popd
call :log "Installing/updating video downloader (yt-dlp)"
"%PY%" -m pip install -U "yt-dlp[default]" || goto :fail
> "%KIT%\tools\mode.txt" echo %MODE%

REM 4) Self-test ----------------------------------------------------------------
call :log "Self-test"
"%PY%" "%KIT%\swap.py" --check || goto :fail

echo.
echo ============================================================
echo  SETUP DONE.  Next time just double-click studio_windows.bat
echo ============================================================
choice /c YN /m "Start the Face-Swap Studio now"
if errorlevel 2 exit /b 0
call "%KIT%\studio_windows.bat"
exit /b 0

:log
echo ==^> %~1
>>"%LOGFILE%" echo ==^> %~1
exit /b 0

:fail
echo.
echo SETUP FAILED. Read the messages above and README_START_HERE.txt (TROUBLESHOOTING).
echo A copy of the key steps was saved to: %LOGFILE%
echo If you ask an AI assistant for help, paste README_START_HERE.txt, setup_log.txt,
echo and the exact error text shown above.
pause
exit /b 1
