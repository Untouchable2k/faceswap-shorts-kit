@echo off
REM One-time setup for the face-swap kit on Windows 10/11.
REM Usage: double-click, or from a terminal:
REM    setup_windows.bat            (auto: NVIDIA -> cuda, otherwise directml for AMD/Intel GPUs)
REM    setup_windows.bat cpu        (force CPU)
REM    setup_windows.bat cuda       (force NVIDIA CUDA)
REM    setup_windows.bat directml   (any DirectX 12 GPU: AMD / Intel / NVIDIA)
REM Needs: internet, ~10 GB disk. No admin needed. Everything installs inside this folder.
setlocal EnableExtensions
chcp 65001 >nul
set "PYTHONUTF8=1"
set "FACEFUSION_VERSION=3.9.2"
set "PYTHON_VERSION=3.12"
set "CUDA_VERSION=12.8"

cd /d "%~dp0"
set "KIT=%CD%"
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

set "MODE=%~1"
if "%MODE%"=="" set "MODE=auto"
if /i "%MODE%"=="auto" (
  where nvidia-smi >nul 2>nul && (set "MODE=cuda") || (set "MODE=directml")
)
echo ==^> Mode: %MODE%

if not exist tools mkdir tools
if not exist clips mkdir clips
if not exist me mkdir me
if not exist output mkdir output

REM 1) Miniforge (private conda) ----------------------------------------------
if not exist "%KIT%\tools\miniforge\Scripts\conda.exe" (
  echo ==^> Downloading Miniforge
  curl -L --fail -o "%KIT%\tools\miniforge.exe" https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Windows-x86_64.exe || goto :fail
  echo ==^> Installing Miniforge into tools\miniforge ^(takes a few minutes, no window appears^)
  start /wait "" "%KIT%\tools\miniforge.exe" /InstallationType=JustMe /RegisterPython=0 /AddToPath=0 /NoRegistry=1 /NoShortcuts=1 /S /D=%KIT%\tools\miniforge
  del "%KIT%\tools\miniforge.exe"
)
set "CONDA=%KIT%\tools\miniforge\Scripts\conda.exe"
if not exist "%CONDA%" ( echo ERROR: Miniforge install failed. & goto :fail )

REM 2) Python + ffmpeg (+ CUDA runtime libraries) -----------------------------
set "PKGS=python=%PYTHON_VERSION% ffmpeg pip deno"
if /i "%MODE%"=="cuda" set "PKGS=%PKGS% cuda-runtime=%CUDA_VERSION% cudnn=9"
if not exist "%KIT%\tools\env\python.exe" (
  echo ==^> Creating environment
  "%CONDA%" create -y -p "%KIT%\tools\env" -c conda-forge %PKGS% || goto :fail
) else (
  echo ==^> Environment exists, making sure packages are present
  "%CONDA%" install -y -p "%KIT%\tools\env" -c conda-forge %PKGS% || goto :fail
)
set "PY=%KIT%\tools\env\python.exe"

REM 3) FaceFusion ---------------------------------------------------------------
if not exist "%KIT%\facefusion\facefusion.py" (
  echo ==^> Downloading FaceFusion %FACEFUSION_VERSION%
  curl -L --fail -o "%KIT%\tools\facefusion.zip" https://github.com/facefusion/facefusion/archive/refs/tags/%FACEFUSION_VERSION%.zip || goto :fail
  if not exist facefusion mkdir facefusion
  tar -xf "%KIT%\tools\facefusion.zip" -C "%KIT%\facefusion" --strip-components=1 || goto :fail
  del "%KIT%\tools\facefusion.zip"
)

set "ORT=default"
if /i "%MODE%"=="cuda" set "ORT=cuda@12"
if /i "%MODE%"=="directml" set "ORT=directml"
if /i "%MODE%"=="openvino" set "ORT=openvino"
echo ==^> Installing FaceFusion python packages (%ORT%)
set "CONDA_PREFIX=%KIT%\tools\env"
set "PATH=%KIT%\tools\env;%KIT%\tools\env\Library\bin;%KIT%\tools\env\Scripts;%PATH%"
pushd "%KIT%\facefusion"
"%PY%" install.py %ORT% || (popd & goto :fail)
popd
echo ==^> Installing/updating video downloader (yt-dlp)
"%PY%" -m pip install -U "yt-dlp[default]" || goto :fail
> "%KIT%\tools\mode.txt" echo %MODE%

REM 4) Self-test ----------------------------------------------------------------
echo ==^> Self-test
"%PY%" "%KIT%\swap.py" --check || goto :fail

echo.
echo ============================================================
echo  SETUP DONE.  Next time just double-click studio_windows.bat
echo ============================================================
choice /c YN /m "Start the Face-Swap Studio now"
if errorlevel 2 exit /b 0
call "%KIT%\studio_windows.bat"
exit /b 0

:fail
echo.
echo SETUP FAILED. Read the messages above and README_START_HERE.txt (TROUBLESHOOTING).
pause
exit /b 1
