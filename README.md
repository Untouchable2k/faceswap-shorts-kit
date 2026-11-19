# Face-Swap Shorts Kit

Put **your face** on the person in a video clip and get a vertical **1080×1920 YouTube Short**, on your own computer with a step-by-step app in your browser. It is free and open source, built on [FaceFusion](https://github.com/facefusion/facefusion), and runs on **Windows 10/11 and Linux**.

## Quick start

| | Windows | Linux |
|---|---|---|
| 1. Download | **Code → Download ZIP**, extract to `C:\faceswap` (no spaces!) | `git clone` or download ZIP |
| 2. Install (once, 10–30 min) | double-click `setup_windows.bat` | `bash setup_linux.sh` |
| 3. Use | double-click `studio_windows.bat` | `bash studio_linux.sh` |

New to this on Windows? Follow **[START_WINDOWS.txt](START_WINDOWS.txt)**, which walks you through it step by step.
Everything else, including troubleshooting and a section for AI assistants, is in **[README_START_HERE.txt](README_START_HERE.txt)**.

Windows setup checks your folder location, free disk space and internet connection up front, retries flaky downloads, and logs its progress to `setup_log.txt`. Want to start over? Double-click `RESET_WINDOWS.bat` (your clips/photos/output are never touched).

## The Studio

1. **Get video:** paste a link (YouTube, TikTok, Instagram, X, Reddit… 1000+ sites) or upload a file.
2. **Cut:** set the start and end while the video plays.
3. **Your face:** add 10–20 photos. They are checked automatically for blur, missing faces and extra people.
4. **Who to replace:** the app finds the people in the video. Tick who gets your face (one person or several). Everyone you don't tick is protected.
5. **Make it:** test on one frame, then render. Jitter smoothing is built in, the vertical crop follows the person, and a report shows what was swapped.

There is also a batch mode (`swap_windows.bat` / `swap_linux.sh`) that processes a whole folder of clips at once.

## Requirements

- An NVIDIA GPU is recommended (8 GB+ VRAM, a recent driver). AMD/Intel works via DirectML on Windows; CPU works but is very slow.
- About 20 GB free disk space and an internet connection for the first setup.
- No admin rights are needed. Everything installs inside the kit folder.

## Use it responsibly

- Only use **your own face**, or the face of someone who agreed to it.
- Only use clips you **own or have permission** to use.
- When uploading to YouTube, set **"Altered or synthetic content" = Yes**.
- Never use it to make a real person appear to say or do something they didn't.
- FaceFusion and the AI models it downloads have their own licenses. Check them before commercial use.

`example_faces/` contains AI-generated people who do not exist (StyleGAN), for testing only.
