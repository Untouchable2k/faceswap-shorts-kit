#!/usr/bin/env python3
"""
Face-swap kit driver (Windows + Linux).

Takes every video in ./clips, puts the face from the photos in ./me onto it with
FaceFusion, and writes a vertical 1080x1920 YouTube Shorts version to ./output.

Normally started through swap_linux.sh / swap_windows.bat, which use the private
Python in ./tools/env. Run with --help for all options.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

KIT = Path(__file__).resolve().parent
ENV = KIT / 'tools' / 'env'
FACEFUSION = KIT / 'facefusion'
IS_WINDOWS = os.name == 'nt'

VIDEO_EXT = {'.mp4', '.mov', '.mkv', '.webm', '.m4v', '.avi'}
IMAGE_EXT = {'.jpg', '.jpeg', '.png', '.webp', '.bmp'}

# Quality presets. "best" is the default because accuracy matters most.
PRESETS = {
	'fast': {
		'pixel_boost': '256x256',
		'enhancer': None,
	},
	'balanced': {
		'pixel_boost': '512x512',
		'enhancer': ('gpen_bfr_512', '50'),
	},
	'best': {
		'pixel_boost': '768x768',
		'enhancer': ('gpen_bfr_512', '60'),
	},
}

# Which face in the clip gets replaced.
FACE_CHOICE = {
	'largest': ('one', 'large-small'),
	'left': ('one', 'left-right'),
	'right': ('one', 'right-left'),
	'top': ('one', 'top-bottom'),
	'all': ('many', 'large-small'),
}


def tool_env() -> dict:
	"""Environment that makes FaceFusion find ffmpeg and the CUDA libraries in ./tools/env."""
	env = dict(os.environ)
	env['CONDA_PREFIX'] = str(ENV)
	env['PYTHONUTF8'] = '1'  # Windows consoles are not UTF-8 by default
	env['PYTHONIOENCODING'] = 'utf-8'
	if IS_WINDOWS:
		extra = [ENV, ENV / 'Library' / 'bin', ENV / 'Scripts', ENV / 'Lib']
	else:
		extra = [ENV / 'bin']
		env['LD_LIBRARY_PATH'] = os.pathsep.join(filter(None, [str(ENV / 'lib'), env.get('LD_LIBRARY_PATH')]))
		env['CONDA_READY'] = '1'
	env['PATH'] = os.pathsep.join([str(p) for p in extra] + [env.get('PATH', '')])
	return env


def mode() -> str:
	try:
		return (KIT / 'tools' / 'mode.txt').read_text().strip()
	except OSError:
		return 'cpu'


def provider() -> str:
	if os.environ.get('FACESWAP_PROVIDER'):  # e.g. FACESWAP_PROVIDER=cpu to test without using the graphics card
		return os.environ['FACESWAP_PROVIDER']
	return {'cuda': 'cuda', 'rocm': 'rocm', 'openvino': 'openvino', 'directml': 'directml'}.get(mode(), 'cpu')


def find_ffmpeg(env: dict) -> str:
	exe = shutil.which('ffmpeg', path=env['PATH'])
	if not exe:
		sys.exit('ERROR: ffmpeg not found. Run the setup script again.')
	return exe


def check() -> None:
	"""Prove the install works, including that the GPU is really used (not silently falling back to CPU)."""
	env = tool_env()
	print('Python      :', sys.version.split()[0], '(' + sys.executable + ')')
	print('ffmpeg      :', find_ffmpeg(env))
	print('FaceFusion  :', 'OK' if (FACEFUSION / 'facefusion.py').exists() else 'MISSING')
	print('Mode        :', mode())
	code = (
		'import onnxruntime as ort, onnx, numpy as np\n'
		'from onnx import helper, TensorProto\n'
		'print("onnxruntime :", ort.__version__, ort.get_available_providers())\n'
		'g = helper.make_graph([helper.make_node("Relu", ["x"], ["y"])], "t",\n'
		'    [helper.make_tensor_value_info("x", TensorProto.FLOAT, [1])],\n'
		'    [helper.make_tensor_value_info("y", TensorProto.FLOAT, [1])])\n'
		'm = helper.make_model(g, opset_imports=[helper.make_opsetid("", 13)]); m.ir_version = 8\n'
		'want = {"cuda": "CUDAExecutionProvider", "rocm": "ROCMExecutionProvider", "openvino": "OpenVINOExecutionProvider", "directml": "DmlExecutionProvider"}.get("' + mode() + '", "CPUExecutionProvider")\n'
		's = ort.InferenceSession(m.SerializeToString(), providers=[want, "CPUExecutionProvider"])\n'
		's.run(None, {"x": np.array([1.0], dtype=np.float32)})\n'
		'used = s.get_providers()[0]\n'
		'print("GPU test    :", "OK - using " + used if used == want else "FAILED - wanted " + want + " but got " + used)\n'
		'raise SystemExit(0 if used == want else 1)\n'
	)
	sys.stdout.flush()
	result = subprocess.run([sys.executable, '-c', code], env=env)
	if mode() == 'cuda':
		try:
			info = subprocess.run(['nvidia-smi', '--query-gpu=name,driver_version,memory.total', '--format=csv,noheader'],
			                      capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=15).stdout.strip()
			print('GPU         :', info or 'nvidia-smi gave no answer')
		except (OSError, subprocess.SubprocessError):
			print('GPU         : nvidia-smi not found')
	if result.returncode != 0:
		if mode() == 'cuda':
			print('\nNVIDIA tip: update the graphics driver (on Windows: version 572 or newer, RTX 50xx cards need it),')
			print('reboot, and run the setup again. Still failing? Run setup with "directml" (Windows) or "cpu".')
		sys.exit('CHECK FAILED - see README_START_HERE.txt, section TROUBLESHOOTING.')
	print('CHECK PASSED')


def run_ui() -> None:
	env = tool_env()
	cmd = [sys.executable, 'facefusion.py', 'run', '--open-browser', '--execution-providers', provider()]
	subprocess.run(cmd, cwd=FACEFUSION, env=env)


def files_in(folder: Path, exts: set) -> list:
	if not folder.is_dir():
		return []
	return sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in exts)


def facefusion_cmd(faces: list, target: Path, output: Path, quality: str, selector: dict, threads: int = None) -> list:
	"""Build the FaceFusion command. selector: {'mode': one|many|reference, 'order': ..., 'position': int, 'frame': int}"""
	preset = PRESETS[quality]
	# FaceFusion runs inside its own folder, so every path must be absolute
	faces = [Path(f).resolve() for f in faces]
	target, output = Path(target).resolve(), Path(output).resolve()
	processors = ['face_swapper'] + (['face_enhancer'] if preset['enhancer'] else [])
	launcher = [sys.executable, 'facefusion.py']
	if selector.get('refs'):
		# several people get the face: ff_multi.py matches against all of them in one run
		refs_file = output.with_name(output.stem + '_refs.json')
		refs_file.write_text(json.dumps({'video': str(Path(selector['video']).resolve()), 'refs': selector['refs'],
		                                 'avoid': selector.get('avoid', [])}))
		launcher = [sys.executable, str(KIT / 'ff_multi.py'), '--refs', str(refs_file)]
	# private work folder per run: FaceFusion names its temp folder after the video file, so two runs on
	# the same clip (studio + batch, or two studios) would otherwise overwrite each other's frames
	temp_dir = Path(tempfile.gettempdir()) / 'faceswap_kit' / f'{os.getpid()}_{time.time_ns()}'
	temp_dir.mkdir(parents=True, exist_ok=True)
	cmd = [
		*launcher, 'headless-run', '--temp-path', str(temp_dir),
		'--source-paths', *[str(f) for f in faces],
		'--target-path', str(target),
		'--output-path', str(output),
		'--processors', *processors,
		'--face-swapper-model', 'hyperswap_1a_256',
		'--face-swapper-pixel-boost', preset['pixel_boost'],
		'--face-selector-mode', selector['mode'],
		'--face-selector-order', selector.get('order', 'large-small'),
		'--face-mask-types', 'box', 'occlusion',
		'--face-mask-blur', '0.3',
		'--output-video-quality', '95',
		'--output-image-quality', '95',
		'--execution-providers', provider(),
		'--log-level', 'info',
	]
	if selector['mode'] == 'reference':
		cmd += ['--reference-face-position', str(selector.get('position', 0)),
		        '--reference-frame-number', str(selector.get('frame', 0)),
		        '--reference-face-distance', str(selector.get('distance', 0.4))]
	if preset['enhancer']:
		cmd += ['--face-enhancer-model', preset['enhancer'][0], '--face-enhancer-blend', preset['enhancer'][1]]
	if threads:
		cmd += ['--execution-thread-count', str(threads)]
	return cmd


# ---- graphics memory handling -------------------------------------------------
# Measured on an RTX 5070, 1080p clip (peak MB above idle):
#   fast: 1 thread 4350, 4 -> 5127, 8 -> 7207 | balanced: 6439 / 8241 / 9320 | best: 6464 / 8215 / 8694
# A 50 s 720p clip at best with 5 threads peaked at ~10000 MB above idle (memory grows on long clips),
# so the per-thread cost is set from that run, not from the short test.
# Model: VRAM needed = BASE + PER_THREAD * threads (MB).
VRAM_COST = {
	'fast': (4400, 500),
	'balanced': (6500, 700),
	'best': (6500, 700),
}
VRAM_SAFETY_MB = 1000  # room for the desktop/browser growing while it runs
OOM_MARKERS = ('Failed to allocate memory', 'out of memory', 'CUDA_ERROR_OUT_OF_MEMORY', 'cudaErrorMemoryAllocation')


def gpu_free_mb():
	"""Free NVIDIA graphics memory in MB, or None if unknown."""
	if mode() != 'cuda':
		return None
	try:
		out = subprocess.run(['nvidia-smi', '--query-gpu=memory.free', '--format=csv,noheader,nounits'],
		                     capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=15).stdout
		return int(out.split()[0])
	except (OSError, ValueError, IndexError, subprocess.SubprocessError):
		return None


def pick_threads(quality: str) -> int:
	"""How many frames to process in parallel, so the graphics card does not run out of memory."""
	free = gpu_free_mb() if provider() == 'cuda' else None
	if free is None:
		return 8 if provider() == 'cpu' else 4
	base, per_thread = VRAM_COST[quality]
	return max(1, min(8, int((free - VRAM_SAFETY_MB - base) / per_thread)))


def run_facefusion(faces: list, target: Path, output: Path, quality: str, selector: dict, env: dict):
	"""
	Runs FaceFusion and yields its log lines. Returns True/False (generator return value).
	- picks the parallel frame count from free graphics memory
	- on 'out of memory' it stops at once and restarts with half the parallel frames
	  (otherwise some frames silently stay un-swapped)
	- retries once on any other failure (e.g. an interrupted first model download)
	"""
	threads = pick_threads(quality)
	retried = False
	while True:
		free = gpu_free_mb()
		yield f'=== Processing {threads} frame(s) in parallel' + (f' (free graphics memory: {free} MB)' if free is not None else '')
		output.unlink(missing_ok=True)
		proc = subprocess.Popen(facefusion_cmd(faces, target, output, quality, selector, threads), cwd=FACEFUSION, env=env,
		                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', bufsize=1, errors='replace')
		oom = False
		for line in proc.stdout:
			line = line.strip()
			if not line:
				continue
			if any(marker in line for marker in OOM_MARKERS):
				oom = True
				proc.terminate()
				break
			yield line
		try:
			proc.wait(timeout=60)
		except subprocess.TimeoutExpired:
			proc.kill()
			proc.wait()
		if not oom and proc.returncode == 0 and output.exists():
			return True
		if oom:
			if threads == 1:
				yield ('!!! The graphics card ran out of memory even with 1 frame at a time. Close other programs '
				       'that use the GPU (games, video editors, other browser tabs with video) or use a lower quality.')
				return False
			threads = max(1, threads // 2)
			yield f'=== Graphics memory full: restarting with {threads} frame(s) in parallel (slower, but every frame gets swapped)'
			continue
		if retried:
			return False
		retried = True
		yield '=== Retrying once (a model download may have been interrupted)'


# Temporal smoothing after the swap (the face enhancer re-sharpens every frame on its own -> jitter).
# Only pixels the swap changed are smoothed (other people / background untouched), it resets at scene
# cuts, and it is motion-adaptive: small frame-to-frame changes are averaged, big ones pass through.
#   value = (k, minimum blend): blend = clip(change / k, minimum, 1)
SMOOTH = {'off': None, 'normal': (50, 0.15), 'strong': (70, 0.1)}


def swap_region(s, o, kernel):
	"""Soft 0..1 mask of where the swap changed the picture. Measured: covers the swapped face, 0% of
	people who were not swapped. Grain/re-encoding differences are ignored (blur + threshold 4 + size)."""
	import cv2
	import numpy as np
	h, w = s.shape[:2]
	small = (w // 2, h // 2)  # half resolution: same result, 4x less work
	s2 = cv2.GaussianBlur(cv2.resize(s, small, interpolation=cv2.INTER_AREA), (0, 0), 1)
	o2 = cv2.GaussianBlur(cv2.resize(o, small, interpolation=cv2.INTER_AREA), (0, 0), 1)
	d = cv2.absdiff(s2, o2).max(axis=2)  # uint8 frames: fast
	m = cv2.dilate((d > 4).astype(np.uint8), kernel)
	n, labels, stats, _ = cv2.connectedComponentsWithStats(m)
	mask = np.zeros(m.shape, np.uint8)
	for j in range(1, n):
		if stats[j, cv2.CC_STAT_AREA] > 2500 / 4:  # real swapped faces only, not specks
			points = cv2.findNonZero((labels == j).astype(np.uint8))
			cv2.fillConvexPoly(mask, cv2.convexHull(points), 1)  # fill holes inside the face
	mask = cv2.GaussianBlur(mask.astype(np.float32), (15, 15), 0)
	return cv2.resize(mask, (w, h), interpolation=cv2.INTER_LINEAR)


def smooth_swap(swapped: Path, original: Path, out: Path, setting, env: dict) -> bool:
	"""Writes a smoothed copy of `swapped` (same size, with audio). Returns False if it cannot (sizes differ)."""
	import cv2
	import numpy as np
	k, minimum = setting
	cs, co = cv2.VideoCapture(str(swapped)), cv2.VideoCapture(str(original))
	w, h = int(cs.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cs.get(cv2.CAP_PROP_FRAME_HEIGHT))
	fps = cs.get(cv2.CAP_PROP_FPS) or 30
	same_size = (w, h) == (int(co.get(cv2.CAP_PROP_FRAME_WIDTH)), int(co.get(cv2.CAP_PROP_FRAME_HEIGHT)))
	cs.release()
	co.release()
	if not same_size:
		return False
	# decode with ffmpeg + accurate rounding (OpenCV's decoder darkens the picture by ~2 levels), so that
	# untouched areas come out exactly like a plain re-save of the swap
	def reader(path):
		return subprocess.Popen([find_ffmpeg(env), '-loglevel', 'error', '-i', str(path), '-sws_flags',
		                         'accurate_rnd+full_chroma_int', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-'],
		                        stdout=subprocess.PIPE, env=env)
	rs, ro = reader(swapped), reader(original)
	size = w * h * 3

	def frame(proc):
		data = proc.stdout.read(size)
		return np.frombuffer(data, np.uint8).reshape(h, w, 3) if len(data) == size else None
	enc = subprocess.Popen([find_ffmpeg(env), '-y', '-loglevel', 'error', '-sws_flags', 'accurate_rnd+full_chroma_int',
	                        '-f', 'rawvideo', '-pix_fmt', 'bgr24',
	                        '-s', f'{w}x{h}', '-r', f'{fps}', '-i', '-', '-i', str(swapped), '-map', '0:v', '-map', '1:a?',
	                        '-c:v', 'libx264', '-preset', 'fast', '-crf', '12', '-pix_fmt', 'yuv420p', '-c:a', 'copy', str(out)],
	                       stdin=subprocess.PIPE, env=env)
	kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (13, 13))  # used at half resolution
	state, prev_orig = None, None
	while True:
		s = frame(rs)
		o = frame(ro)
		if s is None:
			break
		if o is None:
			o = s
		small_o = cv2.resize(o, (w // 4, h // 4), interpolation=cv2.INTER_AREA).astype(np.int16)
		cut = prev_orig is None or float(np.abs(small_o - prev_orig).mean()) > 25  # scene cut: start fresh
		prev_orig = small_o
		if cut or state is None:
			state = s.astype(np.float32)
		else:
			mask = swap_region(s, o, kernel)
			ys, xs = np.nonzero(mask > 0.01)
			if len(ys) == 0:
				state = s.astype(np.float32)  # nothing swapped in this frame
			else:  # only do the smoothing maths inside the swapped area
				y1, y2, x1, x2 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
				prev, cur, m = state[y1:y2, x1:x2], s[y1:y2, x1:x2].astype(np.float32), mask[y1:y2, x1:x2, None]
				blend = np.clip(np.abs(cur - prev).max(axis=2) / k, minimum, 1.0)[..., None]  # small change = jitter -> average
				smoothed = prev + blend * (cur - prev)
				state = s.astype(np.float32)
				state[y1:y2, x1:x2] = m * smoothed + (1 - m) * cur
		enc.stdin.write(np.clip(state, 0, 255).astype(np.uint8).tobytes())
	enc.stdin.close()
	for proc in (rs, ro):
		proc.stdout.close()
		proc.wait()
	return enc.wait() == 0


def make_short(src: Path, dst: Path, shape: str, env: dict, crop_x: float = 50, smooth: str = 'normal',
               original: Path = None) -> None:
	"""shape: crop (fill 1080x1920, crop_x 0=left..100=right) | fit (whole frame, blurred bars) | original.
	original = the video before the swap (needed for smoothing only the swapped faces)."""
	x = max(0.0, min(100.0, crop_x)) / 100
	setting = SMOOTH.get(smooth)
	pre, temp = '', None
	if setting and original:
		temp = Path(dst).with_name(Path(dst).stem + '_smoothing.mp4')
		if smooth_swap(Path(src), Path(original), temp, setting, env):
			src = temp
		else:
			temp = None
	if setting and temp is None:  # fallback: light temporal filter on the whole picture
		pre = 'hqdn3d=0:0:6:6,'
	if shape == 'original':
		filt = ['-vf', pre + 'setsar=1']
	elif shape == 'fit':
		filt = ['-filter_complex', pre +
		        'split[a][b];[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20[bg];'
		        '[b]scale=1080:1920:force_original_aspect_ratio=decrease[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1']
	else:
		filt = ['-vf', pre + f'scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920:(iw-1080)*{x:.3f}:(ih-1920)/2,setsar=1']
	ff = [find_ffmpeg(env), '-y', '-loglevel', 'error', '-i', str(src), *filt,
	      '-c:v', 'libx264', '-preset', 'slow', '-crf', '17', '-pix_fmt', 'yuv420p',
	      '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', str(dst)]
	result = subprocess.run(ff, env=env).returncode
	if temp:
		temp.unlink(missing_ok=True)
	if result != 0:
		raise RuntimeError('ffmpeg failed on ' + Path(src).name)


def swap_one(clip: Path, faces: list, out_dir: Path, args, env: dict) -> Path:
	selector_mode, selector_order = FACE_CHOICE[args.face]
	tmp_dir = out_dir / '_work'
	tmp_dir.mkdir(parents=True, exist_ok=True)
	swapped = tmp_dir / (clip.stem + '_swapped.mp4')
	print('\n=== Swapping:', clip.name, f'({args.quality}, face={args.face})')
	runner = run_facefusion(faces, clip, swapped, args.quality, {'mode': selector_mode, 'order': selector_order}, env)
	ok = False
	try:
		while True:
			line = next(runner)
			if line.startswith(('processing:', 'analysing:', 'downloading:')):
				print('\r' + line[:150], end='', flush=True)  # progress bar on one line
			else:
				print(line, flush=True)
	except StopIteration as done:
		ok = done.value
	print()
	if not ok:
		raise RuntimeError('FaceFusion failed on ' + clip.name)

	if args.no_vertical:
		final = out_dir / (clip.stem + '_faceswap.mp4')
		make_short(swapped, final, 'original', env, smooth=args.smooth, original=clip)
		swapped.unlink(missing_ok=True)
		return final

	final = out_dir / (clip.stem + '_short.mp4')
	print('=== Making vertical 1080x1920 Short:', final.name)
	make_short(swapped, final, 'fit' if args.fit else 'crop', env, smooth=args.smooth, original=clip)
	swapped.unlink(missing_ok=True)
	return final


def main() -> None:
	p = argparse.ArgumentParser(description='Swap your face into every clip and make YouTube Shorts.')
	p.add_argument('--clips', default=str(KIT / 'clips'), help='folder with the videos (default: ./clips)')
	p.add_argument('--me', default=str(KIT / 'me'), help='folder with photos of the new face (default: ./me)')
	p.add_argument('--out', default=str(KIT / 'output'), help='output folder (default: ./output)')
	p.add_argument('--quality', choices=PRESETS, default='best', help='fast | balanced | best (default: best)')
	p.add_argument('--face', choices=FACE_CHOICE, default='largest', help='which face to replace (default: largest)')
	p.add_argument('--no-vertical', action='store_true', help='keep the original size instead of 1080x1920')
	p.add_argument('--smooth', choices=SMOOTH, default='normal', help='less face jitter: off | normal | strong (default: normal)')
	p.add_argument('--fit', action='store_true', help='vertical without cropping: whole frame + blurred background')
	p.add_argument('--redo', action='store_true', help='redo clips that already have an output')
	p.add_argument('--check', action='store_true', help='only test the installation')
	p.add_argument('--ui', action='store_true', help='open the FaceFusion web interface instead')
	args = p.parse_args()

	if args.check:
		return check()
	if args.ui:
		return run_ui()

	env = tool_env()
	clips = files_in(Path(args.clips), VIDEO_EXT)
	faces = files_in(Path(args.me), IMAGE_EXT)
	if not clips:
		sys.exit(f'No videos found in {args.clips}. Put .mp4/.mov/.mkv/.webm files there.')
	if not faces:
		sys.exit(f'No photos found in {args.me}. Put 10-20 clear .jpg/.png photos of the face there.')
	if len(faces) < 5:
		print(f'WARNING: only {len(faces)} photo(s) in {args.me}. 10-20 varied photos give a more accurate likeness.')

	out_dir = Path(args.out)
	out_dir.mkdir(parents=True, exist_ok=True)
	done, failed = [], []
	for clip in clips:
		suffix = '_faceswap.mp4' if args.no_vertical else '_short.mp4'
		if not args.redo and (out_dir / (clip.stem + suffix)).exists():
			print('Skipping (already done):', clip.name)
			continue
		start = time.time()
		try:
			done.append(swap_one(clip, faces, out_dir, args, env))
			print(f'=== Done in {time.time() - start:.0f}s ->', done[-1])
		except Exception as error:
			print('!!!', error)
			failed.append(clip.name)

	print('\nFinished.', len(done), 'made,', len(failed), 'failed.')
	for f in failed:
		print('  failed:', f)
	print('Outputs are in', out_dir)
	print('Reminder: tick "Altered or synthetic content" when uploading to YouTube.')
	sys.exit(1 if failed else 0)


if __name__ == '__main__':
	main()
