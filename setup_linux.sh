#!/usr/bin/env bash
# One-time setup for the face-swap kit on Linux.
# Usage:  bash setup_linux.sh            (auto-detects NVIDIA GPU, else CPU)
#         bash setup_linux.sh cpu        (force CPU)
#         bash setup_linux.sh cuda       (force NVIDIA CUDA)
#         bash setup_linux.sh rocm       (AMD GPU, experimental)
# Needs: internet, ~10 GB disk. No sudo/admin needed. Everything is installed
# inside this folder (tools/ and facefusion/), so deleting the folder removes it all.
set -euo pipefail

FACEFUSION_VERSION="3.9.2"
PYTHON_VERSION="3.12"
CUDA_VERSION="12.8"

KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$KIT"
case "$KIT" in *" "*) echo "ERROR: the folder path contains a space ($KIT). Move the kit to a path without spaces."; exit 1;; esac

MODE="${1:-auto}"
if [ "$MODE" = "auto" ]; then
  if command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi >/dev/null 2>&1; then MODE="cuda"; else MODE="cpu"; fi
fi
echo "==> Mode: $MODE"

mkdir -p tools clips me output

# 1) Miniforge (private conda) -------------------------------------------------
if [ ! -x tools/miniforge/bin/conda ]; then
  echo "==> Downloading Miniforge"
  curl -L --fail -o tools/miniforge.sh \
    "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-$(uname -m).sh"
  bash tools/miniforge.sh -b -p "$KIT/tools/miniforge"
  rm -f tools/miniforge.sh
fi
CONDA="$KIT/tools/miniforge/bin/conda"

# 2) Python + ffmpeg (+ CUDA runtime libraries) --------------------------------
PKGS=("python=$PYTHON_VERSION" "ffmpeg" "pip" "deno")
if [ "$MODE" = "cuda" ]; then PKGS+=("cuda-runtime=$CUDA_VERSION" "cudnn=9"); fi
if [ ! -x tools/env/bin/python ]; then
  echo "==> Creating environment (python, ffmpeg${MODE/cpu/}...)"
  "$CONDA" create -y -p "$KIT/tools/env" -c conda-forge "${PKGS[@]}"
else
  echo "==> Environment exists, making sure packages are present"
  "$CONDA" install -y -p "$KIT/tools/env" -c conda-forge "${PKGS[@]}"
fi
PY="$KIT/tools/env/bin/python"

# 3) FaceFusion -----------------------------------------------------------------
if [ ! -f facefusion/facefusion.py ]; then
  echo "==> Downloading FaceFusion $FACEFUSION_VERSION"
  curl -L --fail -o tools/facefusion.tar.gz \
    "https://github.com/facefusion/facefusion/archive/refs/tags/$FACEFUSION_VERSION.tar.gz"
  mkdir -p facefusion
  tar -xzf tools/facefusion.tar.gz -C facefusion --strip-components=1
  rm -f tools/facefusion.tar.gz
fi

case "$MODE" in
  cuda) ORT="cuda@12" ;;
  rocm) ORT="rocm" ;;
  openvino) ORT="openvino" ;;
  *) ORT="default" ;;
esac
echo "==> Installing FaceFusion python packages ($ORT)"
cd facefusion
CONDA_PREFIX="$KIT/tools/env" PATH="$KIT/tools/env/bin:$PATH" "$PY" install.py "$ORT"
cd "$KIT"
echo "==> Installing/updating video downloader (yt-dlp)"
"$PY" -m pip install -U "yt-dlp[default]"
echo "$MODE" > tools/mode.txt

# 4) Self-test ------------------------------------------------------------------
echo "==> Self-test"
"$PY" "$KIT/swap.py" --check

echo
echo "SETUP DONE. Next: put clips in ./clips, 10-20 photos of your face in ./me, then run:  bash studio_linux.sh  (easy app)  or  bash swap_linux.sh  (batch)"
