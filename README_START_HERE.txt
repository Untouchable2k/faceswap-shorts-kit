FACE-SWAP KIT FOR YOUTUBE SHORTS  -  START HERE
================================================

What it does: puts YOUR face (from photos) onto the person in video clips, then
makes a vertical 1080x1920 video ready for YouTube Shorts. Runs on your own
computer (free, open source: FaceFusion 3.9.2). Works on Windows 10/11 and Linux.

WINDOWS, starting from zero? Read START_WINDOWS.txt first (step by step).

-------------------------------------------------------------------------------
QUICK START
-------------------------------------------------------------------------------
1. Put this whole folder somewhere WITHOUT SPACES in the path.
     Windows: C:\faceswap          Linux: ~/faceswap

2. Run the setup ONCE (needs internet, ~10 GB free disk, 10-30 minutes):
     Windows: double-click  setup_windows.bat
     Linux:   open a terminal in this folder and run:  bash setup_linux.sh
   It must end with "CHECK PASSED" and "SETUP DONE".

3. EASY WAY: open the Studio app (recommended)
     Windows: double-click  studio_windows.bat   (keep the black window open)
     Linux:   bash studio_linux.sh
   Your browser opens the Face-Swap Studio. Do the 5 tabs in order; each one
   tells you exactly what to do next:
     1 Get video     paste a link OR upload a file. Tick "I own / have permission".
     2 Cut           play the video, press "Set START here" / "Set END here"
                     (or drag the sliders), check first/last frame, press Cut.
     3 Your face     add 10-20 photos, press "Check my photos". Bad photos are
                     marked with a warning and skipped automatically.
     4 Who to replace  press "Find people in this video": you get one picture
                     per person. TICK everyone who should get your face (one
                     person, the same person in two looks, or several people
                     for "3 of me"). Each uses their own best close-up.
                     Clothes don't matter, only faces are compared.
     5 Make it       "Test on one frame" first, look closely, then "Make my Short".
                     Afterwards it reports what % of the video was swapped and where not.
                     The vertical crop centres on the chosen person automatically.
   Finished Shorts are saved in the  output  folder.

   BATCH WAY (many clips at once, no clicking): steps 4-5 below.

4. Put your videos in the  clips  folder (.mp4 .mov .mkv .webm), and 10-20
   photos of YOUR face in the  me  folder (.jpg/.png). For accuracy:
     - sharp, well lit, face clearly visible, only you in the photo
     - mostly looking at the camera, plus a few slight left/right turns
     - no sunglasses, hands, hats or hair covering the face
     - a few different expressions (neutral, smiling, talking)
     - similar lighting to your clips helps a lot

5. Run the batch swap:
     Windows: double-click  swap_windows.bat
     Linux:   bash swap_linux.sh
   Finished Shorts appear in  output  as  <clipname>_short.mp4

The first run downloads the AI models (~1-2 GB), so it takes longer once.

-------------------------------------------------------------------------------
WHERE TO GET VIDEOS (Studio step 1: paste the link)
-------------------------------------------------------------------------------
Links work from 1000+ sites (via yt-dlp): YouTube + Shorts, TikTok, Instagram,
X/Twitter, Reddit, Imgur, Streamable, Vimeo, Twitch clips, Kick, Dailymotion,
Facebook, Bilibili, Tumblr ... Instagram and private videos need you logged in:
log in to the site in your browser, then pick that browser in "Use my browser
login" (Firefox works most reliably; on Windows close Chrome/Edge first).
Instagram alternative: download the reel at https://www.snapgram.io/ (link is
in Studio step 1), then upload the file in step 1.
SAFEST for monetized channels (free to reuse, no copyright strikes):
  pexels.com/videos   pixabay.com/videos   mixkit.co   coverr.co
Clips from other creators/TV/movies belong to them; you need permission.

-------------------------------------------------------------------------------
BATCH OPTIONS  (add after the command, e.g.  bash swap_linux.sh --quality fast)
         On Windows open a terminal in this folder and type e.g.
         swap_windows.bat --face left
-------------------------------------------------------------------------------
--quality best       (default) most accurate, slowest
--quality balanced   good and about 2x faster
--quality fast       quick preview to test a clip
--face largest       (default) replace the biggest face in the frame
--face left / right / top   replace the left-most / right-most / top face
--face all           replace every face
--fit                vertical video WITHOUT cropping (blurred background bars)
--no-vertical        keep the clip's original size/shape
--redo               redo clips that already have an output (otherwise skipped)
--check              only test the installation

Batch mode crops the CENTRE of wide clips. If the face is off-centre, use
--fit or the Studio (which centres on the person).

Expert mode (FaceFusion's own full interface, every setting):
  open_ui_windows.bat  or  bash open_ui_linux.sh

-------------------------------------------------------------------------------
TIPS FOR ACCURATE, BELIEVABLE RESULTS
-------------------------------------------------------------------------------
- Clips where the face is big, front-facing and well lit work best.
- Very fast motion, extreme side profiles, heavy blur, or faces smaller than
  ~100 px swap poorly. Choose clips carefully; that matters more than settings.
- Pick clips where the person's face shape, skin tone and hair are close to
  yours. The swap replaces the face, not the hair or head shape.
- Always watch the result before uploading. If it flickers or shows the wrong
  person, try --face left/right or use the browser interface.

-------------------------------------------------------------------------------
YOUTUBE RULES (ignore these and your channel can get struck)
-------------------------------------------------------------------------------
- When uploading, set "Altered or synthetic content" to YES. YouTube requires
  this for realistic face swaps; unlabeled ones can be removed or held back.
- Only use clips you own or have permission to use. Copyright claims are the
  #1 reason face-swap channels die.
- Only put on YOUR OWN face, or a face whose owner agreed. Never use it to make
  a real person seem to say or do something they did not.

-------------------------------------------------------------------------------
TROUBLESHOOTING
-------------------------------------------------------------------------------
"path contains a space"  -> move the folder (e.g. C:\faceswap) and rerun setup.
"CHECK FAILED ... wanted CUDAExecutionProvider" (NVIDIA):
    - update the NVIDIA driver (version 550 or newer), reboot, rerun setup.
    - still failing: run setup again with "cpu" (slow but works), or on
      Windows try "directml".
Windows: "VCRUNTIME140.dll missing" -> install the Microsoft Visual C++
    Redistributable (x64) from microsoft.com, then rerun setup.
"Failed to allocate memory" / out of GPU memory -> handled automatically: the
    number of frames processed in parallel is picked from FREE graphics memory,
    and if it still runs out, the run restarts with half as many (until 1).
    If even 1 fails: close games/video apps/browser tabs with video, and run
    only ONE studio (each extra terminal running it can hold a swap).
Wrong person swapped -> Studio step 4 (pick the person), or --face left/right/top.
Face looks jittery / shimmers -> Step 5 "Smoothness": Normal (default) or
    Strong. Batch: --smooth strong. It smooths ONLY the swapped faces (other
    people and the background are left as they are), restarts at every scene
    cut, and lets real movement through. Measured: Normal removes all the
    extra jitter the swap adds; adds ~2 min per 50 s of video.
Someone you did NOT pick got your face -> use "Find people" + tick boxes in
    Step 4: everyone NOT ticked is protected (a face only gets yours if it
    looks more like a ticked person than like any unticked one). Picking a
    moment by hand has no protection.
Face flickers / barely sticks -> Studio step 4: use "Find close-ups" and pick
    the BIGGEST view of the person. Then Step 5 > Advanced > Face matching:
    raise it a little (0.4 -> 0.45) if your face is MISSING in some shots,
    lower it if OTHER people get your face. Clips that cut between many
    shots/angles (old TV, compilations) work worst; trim to the close-up part.
Link download fails -> rerun setup (updates the downloader; sites change
    often), or log in via "Use my browser login", or download the video
    yourself and upload the file.
Studio doesn't open -> go to http://127.0.0.1:7860 in your browser.
Studio started twice / old tabs dead -> just start it again: every start
    closes studios already running from this folder (and any swap they were
    doing), then opens fresh at http://127.0.0.1:7860. Close old browser tabs.
    To run two on purpose: set STUDIO_KEEP_OTHERS=1 and GRADIO_SERVER_PORT=7861.
Setup interrupted -> just run the setup script again; it continues.
Start completely fresh -> delete the "tools" and "facefusion" folders, rerun setup.

-------------------------------------------------------------------------------
FOR AI ASSISTANTS (paste this whole file into ChatGPT/Claude/etc. for help)
-------------------------------------------------------------------------------
You are helping a user run this kit. Facts about it:

LAYOUT (all paths relative to the kit folder):
  setup_linux.sh / setup_windows.bat   one-time installer. Arg: auto (default) |
                                       cpu | cuda | directml (Windows) | rocm (Linux)
                                       | openvino. Safe to rerun; resumes.
  studio_linux.sh / studio_windows.bat  Gradio wizard (studio.py) on
                                       http://127.0.0.1:7860: link download
                                       (yt-dlp) or upload -> trim (ffmpeg) ->
                                       photo check -> pick person (reference
                                       mode) -> test frame -> make Short.
  faces_helper.py      face detection with FaceFusion's own models (used by
                       the studio so face numbering matches FaceFusion)
  swap_linux.sh / swap_windows.bat     batch run: python swap.py <args>
  open_ui_linux.sh / open_ui_windows.bat   FaceFusion Gradio UI (swap.py --ui)
  swap.py              driver script; --help lists options
  clips/  me/  output/ input videos / source face photos / results
  tools/miniforge      private Miniforge (conda). Not added to PATH/registry.
  tools/env            conda env: Python 3.12, ffmpeg, pip, deno (JS runtime
                       yt-dlp needs for YouTube), yt-dlp; for cuda also
                       conda-forge cuda-runtime=12.8 + cudnn=9
  tools/mode.txt       chosen backend (cuda/cpu/directml/rocm/openvino)
  facefusion/          FaceFusion 3.9.2 source (github.com/facefusion/facefusion),
                       installed with `python install.py cuda@12` (onnxruntime-gpu
                       1.24.4) or default/directml/rocm/openvino.

PIPELINE per clip (swap.py):
  facefusion.py headless-run --source-paths me/* --target-path clip
    --processors face_swapper [face_enhancer]
    --face-swapper-model hyperswap_1a_256 --face-swapper-pixel-boost 768x768 (best)
    --face-enhancer-model gpen_bfr_512 --face-enhancer-blend 60 (best)
    --face-selector-mode one --face-selector-order large-small (default)
    --face-mask-types box occlusion --face-mask-blur 0.3
    --execution-providers <from mode.txt>
  then ffmpeg: scale+center-crop to 1080x1920, libx264 crf 17, aac 192k.
  Outputs: output/<name>_short.mp4. Intermediate: output/_work/.
  GPU memory: --execution-thread-count = (free VRAM - 1000 - base)/per_thread,
  base/per_thread MB: fast 4400/500, balanced+best 6500/700 (measured RTX 5070),
  capped 1..8; on onnxruntime 'Failed to allocate memory' the run is killed and
  restarted with half the threads (swap.py run_facefusion).
  Existing outputs are skipped unless --redo. Failed runs retry once
  automatically (first-run model downloads can be interrupted).
  Unticked people are passed as "avoid": a face is swapped only if
  dist(chosen)/2 < reference_face_distance AND dist(chosen) < dist(avoid).
  Smoothing (swap.py smooth_swap): mask = where swap differs from original
  (blur, >4, big regions, convex fill), motion-adaptive temporal blend
  clip(change/k, min, 1), normal k=50 min=0.15, reset on scene cuts.
  Several people ticked: ff_multi.py launches FaceFusion with a patched
  select_faces that matches against ALL ticked references (frame + box from
  the cut) in one run; FaceFusion files are not modified. Each run also gets a
  private --temp-path (FaceFusion's default temp folder is per video NAME, so
  two runs on one clip collided). Note: FaceFusion compares
  interp(cosine_distance,[0,2],[0,1]) < reference_face_distance.
  Studio uses --face-selector-mode reference --face-selector-order left-right
  --reference-face-position <picked-1> --reference-frame-number <frame>
  --reference-face-distance <slider, default 0.4>, on the trimmed clip; the
  crop x-offset centres the picked face.

REQUIREMENTS: Windows 10 1803+ (has curl/tar) or Linux x86_64/aarch64 with
  bash+curl+tar. No admin/sudo. NVIDIA: driver >= 550 recommended (CUDA 12.x).
  AMD/Intel on Windows: directml. Apple macOS: NOT supported by these scripts;
  use FaceFusion's own install docs (onnxruntime with CoreML) instead.
  GPU guidance: 8 GB+ VRAM ideal for "best"; 4-6 GB use --quality balanced;
  CPU works but is very slow (minutes per second of video).

HOW TO HELP: ask the user for OS, GPU model + VRAM, and the exact error text.
  Verify with `swap.py --check` (prints python, ffmpeg, onnxruntime providers and
  a real GPU inference test). Most failures are: path with spaces, outdated
  GPU driver, missing VC++ redistributable (Windows), no internet during first
  model download, or out of VRAM (lower --quality). Do not suggest installing
  system-wide Python/CUDA; the kit is self-contained in tools/.

-------------------------------------------------------------------------------
SHARING THIS KIT
-------------------------------------------------------------------------------
Share dist/faceswap_kit.zip (about 7 MB: scripts, guides, example faces).
To rebuild it, zip everything EXCEPT tools, facefusion, clips, me, output
(setup rebuilds tools + facefusion; the rest is personal).
