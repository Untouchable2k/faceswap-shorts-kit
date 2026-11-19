#!/usr/bin/env python3
"""
Face-Swap Studio: a simple step-by-step app in your browser.
  1. Get a video (paste a link or upload)   2. Cut the part you want
  3. Add + check your face photos           4. Click the person to replace
  5. Test on one frame, then make the Short

Start it with studio_linux.sh / studio_windows.bat.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

KIT = Path(__file__).resolve().parent
sys.path.insert(0, str(KIT))
os.environ.setdefault('GRADIO_ANALYTICS_ENABLED', 'False')

import cv2  # noqa: E402
import gradio as gr  # noqa: E402

import swap as kit  # noqa: E402

ENV = kit.tool_env()
os.environ['PATH'] = ENV['PATH']  # so yt-dlp finds ffmpeg + deno from tools/env
CLIPS = KIT / 'clips'
ME = KIT / 'me'
OUT = KIT / 'output'
WORK = OUT / '_studio'
for d in (CLIPS, ME, OUT, WORK):
	d.mkdir(parents=True, exist_ok=True)

SHORTS_MAX = 180
QUALITY = {'Fast (quick check)': 'fast', 'Balanced': 'balanced', 'Best (most accurate, slower)': 'best'}
SHAPES = {'Vertical: fill the screen (crops the sides)': 'crop',
          'Vertical: whole picture (blurred bars)': 'fit',
          'Keep original shape': 'original'}
EVERYONE = 'Everyone (replace all faces)'
SMOOTHNESS = {'Off': 'off', 'Normal (recommended)': 'normal', 'Strong': 'strong'}


# ---------------------------------------------------------------- helpers ---

def video_info(path) -> dict:
	cap = cv2.VideoCapture(str(path))
	fps = cap.get(cv2.CAP_PROP_FPS) or 30
	frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
	info = {'fps': fps, 'frames': frames, 'duration': frames / fps if fps else 0,
	        'w': int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), 'h': int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}
	cap.release()
	return info


def frame_at(path, seconds: float = None, index: int = None):
	"""Returns an RGB frame. Uses frame index, like FaceFusion does."""
	cap = cv2.VideoCapture(str(path))
	if index is None:
		fps = cap.get(cv2.CAP_PROP_FPS) or 30
		index = int(round((seconds or 0) * fps))
	total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
	cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, min(index, total - 1)))
	ok, frame = cap.read()
	cap.release()
	return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB) if ok else None


def fmt(seconds: float) -> str:
	m, s = divmod(max(0.0, seconds), 60)
	return f'{int(m)}:{s:04.1f}'


def detect_faces(images: list, embed: bool = False) -> dict:
	"""Runs FaceFusion's own face detector (same numbering as the swap)."""
	images = [str(Path(i).resolve()) for i in images]
	cmd = [sys.executable, str(KIT / 'faces_helper.py'), kit.provider(), *(['--embed'] if embed else []), *images]
	res = subprocess.run(cmd, env=ENV, capture_output=True, text=True, encoding='utf-8', errors='replace')
	for line in res.stdout.splitlines():
		if line.startswith('FACES_JSON '):
			return json.loads(line[len('FACES_JSON '):])
	raise gr.Error('Face detection failed:\n' + (res.stderr or res.stdout)[-1500:])


def safe_name(text: str) -> str:
	return re.sub(r'[^A-Za-z0-9_-]+', '_', text).strip('_')[:60] or 'clip'


def clip_choices():
	return [p.name for p in kit.files_in(CLIPS, kit.VIDEO_EXT)]


def my_photos():
	return [p for p in kit.files_in(ME, kit.IMAGE_EXT)]


def go(tab: str):
	return gr.Tabs(selected=tab)


# --------------------------------------------------- step 1: get a video ---

def load_clip(path: Path):
	info = video_info(path)
	if not info['frames']:
		raise gr.Error('Could not read that video. Try another file or link.')
	d = round(info['duration'], 1)
	end = min(d, SHORTS_MAX)
	msg = (f'✅ **Loaded:** {path.name} ({info["w"]}x{info["h"]}, {fmt(d)} long)\n\n'
	       '👉 **Next:** Step 2. Choose the part you want.')
	return (str(path), msg,
	        gr.update(value=str(path)),
	        gr.update(maximum=d, value=0), gr.update(maximum=d, value=end),
	        frame_at(path, 0), frame_at(path, max(0, end - 0.1)), range_text(0, end),
	        gr.update(choices=clip_choices()), go('s2'))


def download_link(url, browser, rights):
	url = (url or '').strip()
	if not url:
		raise gr.Error('Paste a video link first.')
	if not rights:
		raise gr.Error('Please confirm you have the right to use this video (tick the box).')
	import yt_dlp
	opts = {
		'outtmpl': str(CLIPS / '%(extractor)s_%(id)s.%(ext)s'),
		'format': 'bv*[height<=1920][ext=mp4]+ba[ext=m4a]/bv*[height<=1920]+ba/b[ext=mp4]/b',
		'merge_output_format': 'mp4',
		'noplaylist': True,
		'quiet': True,
		'no_warnings': True,
		'ffmpeg_location': str(Path(kit.find_ffmpeg(ENV)).parent),
	}
	if browser and browser != 'No':
		opts['cookiesfrombrowser'] = (browser.lower(),)
	try:
		with yt_dlp.YoutubeDL(opts) as ydl:
			info = ydl.extract_info(url, download=True)
			if 'entries' in info:
				info = info['entries'][0]
			path = Path(info['requested_downloads'][0]['filepath'])
	except Exception as error:
		hint = ''
		if 'login' in str(error).lower() or 'cookie' in str(error).lower() or 'instagram' in url:
			hint = '\n\nTip: this site wants you logged in. Log in to it in your browser, then choose that browser under "Use my browser login" and try again.'
			if 'instagram' in url:
				hint += ' Or download it with Snapgram (link on the right) and upload the file.'
		raise gr.Error('Download failed: ' + str(error)[:400] + hint)
	return load_clip(path)


def upload_file(file, rights):
	if not file:
		raise gr.Error('Choose a video file first.')
	if not rights:
		raise gr.Error('Tick the box "I own this video or have permission" at the top, then press "Use this file".')
	src = Path(file)
	dst = CLIPS / (safe_name(src.stem) + src.suffix.lower())
	shutil.copy(src, dst)
	return load_clip(dst)


def pick_existing(name, rights):
	if not name:
		raise gr.Error('Choose a clip from the list.')
	if not rights:
		raise gr.Error('Please confirm you have the right to use this video (tick the box).')
	return load_clip(CLIPS / name)


# ---------------------------------------------------------- step 2: cut ---

def range_text(start, end):
	length = max(0, end - start)
	warn = f'  ⚠️ Shorts can be at most {SHORTS_MAX // 60} minutes.' if length > SHORTS_MAX else ''
	if length <= 0:
		warn = '  ⚠️ End must be after start.'
	return f'**Selected:** {fmt(start)} → {fmt(end)}  ·  **length {length:.1f} s**{warn}'


def show_start(clip, start, end):
	return (frame_at(clip, start) if clip else None), range_text(start, end)


def show_end(clip, start, end):
	return (frame_at(clip, max(0, end - 0.05)) if clip else None), range_text(start, end)


def set_from_player(clip, which, seconds, start, end):
	"""'Set start/end here' buttons: gets the current play position from the browser."""
	try:
		seconds = round(float(seconds), 1)
	except (TypeError, ValueError):
		raise gr.Error('Play or pause the video at the moment you want, then press the button.')
	if which == 'start':
		start = seconds
	else:
		end = seconds
	return start, end, frame_at(clip, start), frame_at(clip, max(0, end - 0.05)), range_text(start, end)


def cut_clip(clip, start, end):
	if not clip:
		raise gr.Error('Do Step 1 first.')
	if end - start < 0.5:
		raise gr.Error('The part is too short. Move the End slider after the Start slider.')
	if end - start > SHORTS_MAX:
		gr.Warning('This is longer than 3 minutes, too long for a Short. Continuing anyway.')
	out = WORK / f'{Path(clip).stem}_{start:.1f}-{end:.1f}.mp4'.replace(':', '')
	cmd = [kit.find_ffmpeg(ENV), '-y', '-loglevel', 'error', '-ss', f'{start:.3f}', '-i', clip,
	       '-t', f'{end - start:.3f}', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '14',
	       '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', str(out)]
	if subprocess.run(cmd, env=ENV).returncode != 0:
		raise gr.Error('Cutting failed.')
	d = round(video_info(out)['duration'], 1)
	msg = (f'✅ **Cut done:** {d} s. Check it in the player.\n\n'
	       '👉 **Next:** Step 3. Add photos of your face.')
	return str(out), gr.update(value=str(out)), msg, gr.update(maximum=d, value=round(d / 2, 1)), go('s3')


# ------------------------------------------------------ step 3: my face ---

def add_photos(files):
	for f in files or []:
		src = Path(f)
		if src.suffix.lower() in kit.IMAGE_EXT:
			shutil.copy(src, ME / (safe_name(src.stem) + src.suffix.lower()))
	return gallery_and_hint()


def clear_photos():
	old = ME / '_old' / time.strftime('%Y%m%d-%H%M%S')
	old.mkdir(parents=True, exist_ok=True)
	for p in my_photos():
		shutil.move(str(p), old / p.name)
	return gallery_and_hint() + ([],)


def gallery_and_hint():
	photos = my_photos()
	n = len(photos)
	if n == 0:
		hint = '📷 No photos yet. Add 10-20 photos of your face.'
	elif n < 10:
		hint = f'📷 {n} photo(s). **Add a few more (10-20 is best)**, then press **Check my photos**.'
	else:
		hint = f'📷 {n} photos. Now press **Check my photos**.'
	return [str(p) for p in photos], hint


def check_photos():
	photos = my_photos()
	if not photos:
		raise gr.Error('Add some photos of your face first.')
	found = detect_faces(photos)
	rows, good = [], []
	for p in photos:
		faces = found.get(str(Path(p).resolve()), [])
		img = cv2.imread(str(p))
		problem = ''
		if len(faces) == 0:
			problem = 'No face found'
		elif len(faces) > 1:
			problem = f'{len(faces)} faces. Crop it so only you are in it'
		else:
			x1, y1, x2, y2 = [int(v) for v in faces[0]['box']]
			w = x2 - x1
			crop = img[max(0, y1):y2, max(0, x1):x2] if img is not None else None
			# sharpness measured at a fixed face size, so big and small photos are judged the same way
			sharp = cv2.Laplacian(cv2.resize(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY), (256, 256), interpolation=cv2.INTER_AREA), cv2.CV_64F).var() if crop is not None and crop.size else 0
			if w < 120:
				problem = f'Face too small ({w}px). Use a closer or bigger photo'
			elif sharp < 40:  # calibrated: blurred (sigma 2.5+) faces score < 30, sharp photos 60-300
				problem = 'Blurry'
			elif faces[0]['score'] < 0.6:  # good front photos score ~0.75-0.85, slight turns ~0.67+
				problem = 'Face not clear (angle/light/covered)'
		if problem:
			rows.append([p.name, '⚠️ ' + problem])
		else:
			rows.append([p.name, '✅ Good'])
			good.append(str(p))
	if not good:
		msg = '❌ **None of the photos are usable.** Add clear, close photos with only your face.'
		return rows, good, msg
	msg = f'✅ **{len(good)} good photo(s)** will be used. Photos marked ⚠️ are skipped.'
	if len(good) < 5:
		msg += '\n\n⚠️ Fewer than 5 good photos: the likeness will be weaker. Add more if you can.'
	msg += '\n\n👉 **Next:** Step 4. Choose who to replace.'
	return rows, good, msg


def to_step4(good):
	if not good:
		raise gr.Error('Press "Check my photos" first. You need at least one ✅ photo.')
	return go('s4')


# ------------------------------------------------- step 4: pick person ---

COLORS = [(255, 60, 60), (60, 200, 255), (255, 200, 0), (120, 255, 120), (255, 120, 255), (255, 255, 255)]


def find_people(cut, seconds):
	if not cut:
		raise gr.Error('Do Step 2 first (cut the clip).')
	info = video_info(cut)
	index = int(round(seconds * info['fps']))
	frame = frame_at(cut, index=index)
	if frame is None:
		raise gr.Error('Could not read that frame.')
	png = WORK / f'reference_frame_{time.time_ns()}.png'  # unique: several studios / clicks never overwrite each other
	cv2.imwrite(str(png), cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
	faces = detect_faces([png]).get(str(png.resolve()), [])
	shown = frame.copy()
	t = max(2, frame.shape[1] // 300)
	for i, f in enumerate(faces):
		x1, y1, x2, y2 = [int(v) for v in f['box']]
		c = COLORS[i % len(COLORS)]
		cv2.rectangle(shown, (x1, y1), (x2, y2), c, t)
		cv2.putText(shown, str(i + 1), (x1, max(30, y1 - 10)), cv2.FONT_HERSHEY_SIMPLEX, t * 0.6, c, t + 1)
	if not faces:
		return shown, gr.update(choices=[], value=None), index, str(png), [], \
			'❌ **No face found in this frame.** Move the slider to a moment where the face is clear, then press **Find faces**.'
	choices = [person_label(i, f) for i, f in enumerate(faces)] + ([EVERYONE] if len(faces) > 1 else [])
	# pre-select the clearest + biggest face, not simply the left-most one
	best = max(range(len(faces)), key=lambda i: faces[i]['score'] * face_width(faces[i]))
	if len(faces) > 1:
		msg = (f'Found **{len(faces)}** face(s). I selected **Person {best + 1}** (the clearest). '
		       '**Check the numbers on the picture** and click a different person if needed.')
	else:
		msg = 'Found **1** face. It is selected.'
	msg += small_face_warning(faces[best])
	return shown, gr.update(choices=choices, value=choices[best]), index, str(png), faces, msg + '\n\n👉 Then go to **Step 5**.'


def face_width(face) -> float:
	return face['box'][2] - face['box'][0]


def person_label(i, face) -> str:
	label = f'Person {i + 1}'
	if face['score'] < 0.6:
		label += ' (unclear, maybe not a face)'
	return label


def person_index(person) -> int:
	return int(re.match(r'Person (\d+)', person).group(1)) - 1


def small_face_warning(face) -> str:
	w = int(face_width(face))
	if w < 80:
		return (f'\n\n⚠️ **This face is very small ({w} px wide).** The swap will be hard to see and less accurate. '
		        'Best: pick a clip where the face is bigger (at least 150 px), or a later moment where they are closer.')
	if w < 150:
		return f'\n\nℹ️ The face is fairly small ({w} px). It will work, but bigger faces give sharper, more convincing swaps.'
	return ''


def on_person_change(faces, person):
	if not faces or not person or person == EVERYONE:
		return gr.update()
	return (small_face_warning(faces[min(person_index(person), len(faces) - 1)]).strip() or '✅ Good face size.') + '\n\n👉 Then go to **Step 5**.'


def auto_crop_x(ref_png, faces, person):
	"""Crop position that puts the chosen person in the middle of the vertical frame."""
	if not faces or not ref_png or not Path(ref_png).exists():
		return 50
	h, w = cv2.imread(ref_png).shape[:2]
	cw = h * 9 / 16
	if cw >= w:
		return 50
	if person == EVERYONE or not person:
		xs = [(f['box'][0] + f['box'][2]) / 2 for f in faces]
		cx = (min(xs) + max(xs)) / 2
	else:
		box = faces[min(person_index(person), len(faces) - 1)]['box']
		cx = (box[0] + box[2]) / 2
	return int(round(max(0, min(100, (cx - cw / 2) / (w - cw) * 100))))


PERSON_NAMES = 'ABCDEFGH'


def find_video_people(cut):
	"""
	Scans the cut (2 frames/s), groups the faces by identity, and returns one picture per person.
	Each person's reference is their BIGGEST face, because matching works much better from a close-up.
	"""
	import numpy as np
	if not cut:
		raise gr.Error('Do Step 2 first (cut the clip).')
	info = video_info(cut)
	scan = WORK / 'scan'
	shutil.rmtree(scan, ignore_errors=True)
	scan.mkdir(parents=True)
	step = max(1, int(info['fps'] / 2))
	cap = cv2.VideoCapture(str(cut))
	frames = []
	for index in range(0, info['frames'], step):
		cap.set(cv2.CAP_PROP_POS_FRAMES, index)
		ok, frame = cap.read()
		if not ok:
			break
		path = scan / f'{index:06d}.jpg'
		cv2.imwrite(str(path), frame, [cv2.IMWRITE_JPEG_QUALITY, 92])
		frames.append((index, path))
	cap.release()
	found = detect_faces([p for _, p in frames], embed=True)

	# all reasonably sized faces, biggest first (big faces give reliable identity vectors)
	faces = []
	for index, path in frames:
		for face in found.get(str(path.resolve()), []):
			if 'embedding' in face and face_width(face) >= 50:
				faces.append((face_width(face) * face['score'], index, path, face, np.array(face['embedding'])))
	faces.sort(key=lambda f: -f[0])
	people = []  # each: {'ref': (index, path, face), 'vectors': [...], 'count': n}
	for _, index, path, face, vec in faces:
		best, best_d = None, 1.0
		for person in people:
			d = 1 - float(np.dot(vec, person['center']) / (np.linalg.norm(vec) * np.linalg.norm(person['center'])))
			if d < best_d:
				best, best_d = person, d
		if best is not None and best_d < 0.65:
			best['count'] += 1
			if len(best['vectors']) < 10:
				best['vectors'].append(vec)
				best['center'] = np.mean(best['vectors'], axis=0)
		elif face_width(face) >= 90 and len(people) < len(PERSON_NAMES):
			people.append({'ref': (index, path, face), 'vectors': [vec], 'center': vec, 'count': 1})
	# merge groups that are the same person seen from a different angle (e.g. looking down)
	def distance(a, b):
		return 1 - float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
	merged = []
	for person in people:  # people are in order of their biggest face
		target = next((m for m in merged if distance(m['center'], person['center']) < 0.75), None)
		if target:
			target['count'] += person['count']
		else:
			merged.append(person)
	# hide 'people' seen for under 3 s: transitions, distorted frames, passers-by (not worth swapping)
	min_count = max(2, int(3 * info['fps'] / step))
	people = [p for p in merged if p['count'] >= min_count] or merged
	if not people:
		return [], [], '❌ No clear faces found in this clip. Try a different clip.', gr.update(choices=[], value=[])
	people.sort(key=lambda p: -p['count'])
	gallery, refs = [], []
	for n, person in enumerate(people):
		index, path, face = person['ref']
		img = cv2.imread(str(path))
		x1, y1, x2, y2 = [int(v) for v in face['box']]
		pad = int((x2 - x1) * 0.5)
		crop = img[max(0, y1 - pad):y2 + pad, max(0, x1 - pad):x2 + pad]
		thumb = path.with_name(f'person_{n}.jpg')
		cv2.imwrite(str(thumb), cv2.resize(crop, (240, int(240 * crop.shape[0] / max(1, crop.shape[1])))))
		seconds = person['count'] * step / info['fps']
		gallery.append((str(thumb), f'Person {PERSON_NAMES[n]} · on screen ~{seconds:.0f} s'))
		refs.append({'time': round(index / info['fps'], 1), 'box': face['box'], 'frame': index, 'label': gallery[-1][1]})
	labels = [caption for _, caption in gallery]
	return gallery, refs, (f'Found **{len(people)} {"person" if len(people) == 1 else "people"}** (people on screen for under 3 s are hidden). '
	                       '**Tick everyone who should get your face** (click a picture or a tick box). '
	                       'Each ticked person uses their own best close-up automatically.'), gr.update(choices=labels, value=labels[:1])


def toggle_person(chosen, evt: gr.SelectData):
	"""Clicking a picture ticks / unticks that person."""
	label = evt.value['caption'] if isinstance(evt.value, dict) else None
	chosen = list(chosen or [])
	if label:
		chosen = [c for c in chosen if c != label] if label in chosen else chosen + [label]
	return chosen


def people_chosen(chosen, refs):
	"""Ticked people -> references for the swap; the first one is used for the preview + crop."""
	by_label = {r['label']: r for r in refs or []}
	picked = [by_label[label] for label in (chosen or []) if label in by_label]
	if not picked:
		return gr.update(), None, []
	# everyone NOT ticked is protected: a face only gets swapped if it is closest to a ticked person
	avoid = [{'frame': r['frame'], 'box': r['box']} for r in refs if r['label'] not in (chosen or [])]
	return picked[0]['time'], picked[0]['box'], {'refs': [{'frame': r['frame'], 'box': r['box']} for r in picked], 'avoid': avoid}


def people_summary(chosen, msg):
	if not chosen:
		return gr.update()  # nothing ticked (e.g. a moment was picked by hand): keep the current message
	names = ', '.join(label.split(' ·')[0] for label in chosen)
	if len(chosen) == 1:
		return f'✅ **{names}** gets your face. Tick more people to give them your face too.\n\n👉 Then go to **Step 5**.'
	return (f'✅ **{len(chosen)} people get your face: {names}.** Everyone else is left alone. '
	        '(The preview below shows the first one.)\n\n👉 Then go to **Step 5**.')


def select_box(faces, box, person):
	"""After find_people: select the face that matches the person clicked in the gallery."""
	if not faces or not box:
		return gr.update()
	def overlap(a, b):
		ix = max(0, min(a[2], b[2]) - max(a[0], b[0]))
		iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
		union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - ix * iy
		return ix * iy / union if union else 0
	i = max(range(len(faces)), key=lambda k: overlap(faces[k]['box'], box))
	return person_label(i, faces[i])


def to_step5(person):
	if not person:
		raise gr.Error('Press "Find faces" and choose a person first.')
	return go('s5')


def selector_for(person, frame_index, distance, multi=None, video=None):
	if multi:
		refs, avoid = (multi['refs'], multi.get('avoid', [])) if isinstance(multi, dict) else (multi, [])
		return {'mode': 'reference', 'order': 'left-right', 'position': 0, 'frame': frame_index, 'distance': distance,
		        'refs': refs, 'avoid': avoid, 'video': video}
	if person == EVERYONE:
		return {'mode': 'many', 'order': 'left-right'}
	position = person_index(person)
	return {'mode': 'reference', 'order': 'left-right', 'position': position, 'frame': frame_index, 'distance': distance}


# ------------------------------------------------------ step 5: make it ---

def crop_preview(ref_png, shape, crop_x):
	if not ref_png or not Path(ref_png).exists():
		return None
	img = cv2.cvtColor(cv2.imread(ref_png), cv2.COLOR_BGR2RGB)
	h, w = img.shape[:2]
	if SHAPES[shape] != 'crop':
		return img
	cw = int(h * 9 / 16)
	if cw >= w:
		return img
	x = int((w - cw) * crop_x / 100)
	dim = (img * 0.35).astype(img.dtype)
	dim[:, x:x + cw] = img[:, x:x + cw]
	cv2.rectangle(dim, (x, 0), (x + cw - 1, h - 1), (255, 255, 0), max(2, w // 400))
	return dim


def test_frame(good, ref_png, person, frame_index, quality, distance, faces, multi=None, cut=None):
	if not good or not ref_png or not person:
		raise gr.Error('Finish steps 3 and 4 first.')
	out = WORK / f'test_{int(time.time())}.png'
	sel = selector_for(person, 0, distance, multi, cut)  # single image: frame 0 (multi: refs come from the cut)
	cmd = kit.facefusion_cmd([Path(g) for g in good], Path(ref_png), out, QUALITY[quality], sel)
	res = subprocess.run(cmd, cwd=kit.FACEFUSION, env=ENV, capture_output=True, text=True, encoding='utf-8', errors='replace')
	if res.returncode != 0 or not out.exists():
		raise gr.Error('Test failed:\n' + (res.stdout + res.stderr)[-1200:])
	before = cv2.cvtColor(cv2.imread(ref_png), cv2.COLOR_BGR2RGB)
	after = cv2.cvtColor(cv2.imread(str(out)), cv2.COLOR_BGR2RGB)
	if person == EVERYONE:
		boxes = [f['box'] for f in faces]
	else:
		boxes = [faces[min(person_index(person), len(faces) - 1)]['box']] if faces else []
	changed = float(abs(after.astype(int) - before.astype(int)).mean())
	if not boxes:
		return after, '⚠️ No face to compare.'
	tiles = []
	for box in boxes[:3]:
		x1, y1, x2, y2 = [int(v) for v in box]
		pad = int((x2 - x1) * 0.6)
		x1, y1 = max(0, x1 - pad), max(0, y1 - pad)
		x2, y2 = min(before.shape[1], x2 + pad), min(before.shape[0], y2 + pad)
		for img, name in ((before, 'BEFORE'), (after, 'AFTER')):
			tile = cv2.resize(img[y1:y2, x1:x2], (360, int(360 * (y2 - y1) / max(1, x2 - x1))), interpolation=cv2.INTER_CUBIC)
			tile = cv2.copyMakeBorder(tile, 36, 0, 4, 4, cv2.BORDER_CONSTANT, value=(20, 20, 20))
			cv2.putText(tile, name, (10, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
			tiles.append(tile)
	h = max(t.shape[0] for t in tiles)
	tiles = [cv2.copyMakeBorder(t, 0, h - t.shape[0], 0, 0, cv2.BORDER_CONSTANT, value=(20, 20, 20)) for t in tiles]
	zoom = cv2.hconcat(tiles)
	msg = ('✅ **Zoomed in on the face: BEFORE vs AFTER.** Look closely. Happy? Press **Make my Short**.\n\n'
	       'Not right? Try Best quality, better photos (Step 3), another person or moment (Step 4).')
	if changed < 0.01:
		msg = '⚠️ **Nothing changed.** The face was not swapped. Go back to Step 4 and choose another person or moment.'
	return zoom, msg


def make_short(cut, good, person, frame_index, quality, distance, shape, crop_x, rights, multi=None, smooth='Normal (recommended)'):
	if not (cut and good and person):
		raise gr.Error('Finish steps 1-4 first.')
	if not rights:
		raise gr.Error('Go back to Step 1 and confirm you have the right to use this video.')
	swapped = WORK / (Path(cut).stem + '_swapped.mp4')
	final = OUT / (Path(cut).stem + f'_short_{time.strftime("%H%M%S")}.mp4')
	log = []
	started = time.time()
	runner = kit.run_facefusion([Path(g) for g in good], Path(cut), swapped, QUALITY[quality],
	                            selector_for(person, int(frame_index), distance, multi, cut), ENV)
	ok, last = False, 0
	try:
		while True:
			line = next(runner)
			if log and '%' in line and log[-1].split(':')[0] == line.split(':')[0]:
				log[-1] = line  # progress bar update
			else:
				log.append(line)
			status = f'⏳ Working... {int(time.time() - started)} s'
			if line.startswith('=== Graphics memory full'):
				status = '⏳ Graphics memory was full. Restarting with lower memory use (slower, but every frame gets swapped)...'
			if time.time() - last > 0.5 or line.startswith('==='):
				last = time.time()
				yield None, status, '\n'.join(log[-12:])
	except StopIteration as done:
		ok = done.value
	if not ok or not swapped.exists():
		yield None, '❌ **The face swap failed.** See the log below.', '\n'.join(log[-40:])
		return
	yield None, '⏳ Checking where the face was swapped...', '\n'.join(log[-12:])
	report = swap_report(cut, swapped)
	yield None, '⏳ Making the final video...', '\n'.join(log[-12:])
	kit.make_short(swapped, final, SHAPES[shape], ENV, crop_x, SMOOTHNESS[smooth], original=cut)
	swapped.unlink(missing_ok=True)
	yield str(final), (f'🎉 **Done in {int(time.time() - started)} s!** Saved to:\n\n`{final}`\n\n' + report +
	                   'Watch it all the way through before posting.\n\n'
	                   '📌 **When uploading to YouTube:** set **"Altered or synthetic content" = Yes**.'), '\n'.join(log[-12:])


def swap_report(original, swapped) -> str:
	"""Compares before/after (3 samples per second) and lists the parts where nothing was swapped."""
	a, b = cv2.VideoCapture(str(original)), cv2.VideoCapture(str(swapped))
	fps = a.get(cv2.CAP_PROP_FPS) or 30
	n = int(a.get(cv2.CAP_PROP_FRAME_COUNT))
	step = max(1, int(fps / 3))
	marks = []
	for index in range(0, n, step):
		a.set(cv2.CAP_PROP_POS_FRAMES, index)
		b.set(cv2.CAP_PROP_POS_FRAMES, index)
		ok1, f1 = a.read()
		ok2, f2 = b.read()
		if not (ok1 and ok2):
			break
		diff = cv2.GaussianBlur(cv2.absdiff(f1, f2).max(axis=2), (9, 9), 0)
		marks.append((index / fps, int((diff > 25).sum()) > 400))
	a.release()
	b.release()
	if not marks:
		return ''
	percent = 100 * sum(m for _, m in marks) // len(marks)
	gaps, start = [], None
	for t, swapped_here in marks + [(marks[-1][0] + 1, True)]:
		if not swapped_here and start is None:
			start = t
		if swapped_here and start is not None:
			if t - start >= 1.0:
				gaps.append(f'{fmt(start)}–{fmt(t)}')
			start = None
	text = f'**Face swapped in about {percent}% of the video.**'
	if gaps:
		text += (' Not swapped: ' + ', '.join(gaps[:8]) + ('…' if len(gaps) > 8 else '') + '. '
		         'That is normal where your person is not on screen. If they ARE visible there: pick a bigger close-up in '
		         'Step 4, raise "Face matching" a little (Step 5 > Advanced), or cut those parts out.')
	return text + '\n\n'


# ------------------------------------------------------------------ UI ---

def build():
	with gr.Blocks(title='Face-Swap Studio', theme=gr.themes.Soft(), css='.hidden-pos{display:none !important}') as app:
		clip = gr.State('')
		cut = gr.State('')
		good = gr.State([])
		frame_index = gr.State(0)
		ref_png = gr.State('')
		faces_state = gr.State([])

		gr.Markdown('# 🎬 Face-Swap Studio\nDo the steps in order. Each step tells you what to do next.')
		with gr.Tabs() as tabs:
			# 1
			with gr.Tab('1 · Get video', id='s1'):
				gr.Markdown('### Step 1: Get a video\nPaste a link (YouTube, TikTok, Instagram, X/Twitter, Reddit, '
				            'Imgur, Vimeo, Twitch, Facebook, Streamable and 1000+ more), **or** upload a file.\n\n'
				            'Best results: the face is **big, facing the camera, well lit**, not moving too fast.')
				rights = gr.Checkbox(label='I own this video or have permission to use it (needed for YouTube, avoids copyright strikes)')
				with gr.Row():
					with gr.Column():
						url = gr.Textbox(label='Video link', placeholder='https://...')
						browser = gr.Dropdown(['No', 'Firefox', 'Chrome', 'Edge', 'Brave', 'Safari'], value='No',
						                      label='Use my browser login (only needed for Instagram/private videos)')
						dl_btn = gr.Button('⬇️ Download', variant='primary')
					with gr.Column():
						gr.Markdown('**Instagram link not working?** Open [Snapgram](https://www.snapgram.io/) '
						            '(opens in a new tab), paste the Instagram link there, download the video, '
						            'then drop the file below.')
						up = gr.File(label='…or upload a video file', file_types=['video'], type='filepath')
						up_btn = gr.Button('📤 Use this file')
						existing = gr.Dropdown(clip_choices(), label='…or pick a video already in the clips folder')
						ex_btn = gr.Button('📂 Use this clip')
				s1_msg = gr.Markdown()
			# 2
			with gr.Tab('2 · Cut', id='s2'):
				gr.Markdown('### Step 2: Choose the part you want\nPlay the video. Use **Set START here** and **Set END here** '
				            'at the right moments, or drag the sliders. The pictures show your exact first and last frame.')
				player = gr.Video(label='Your video', interactive=False, elem_id='player', height=420)
				with gr.Row():
					set_start = gr.Button('⏮ Set START here')
					set_end = gr.Button('Set END here ⏭')
				with gr.Row():
					start = gr.Slider(0, 1, value=0, step=0.1, label='Start (seconds)')
					end = gr.Slider(0, 1, value=1, step=0.1, label='End (seconds)')
				range_md = gr.Markdown()
				with gr.Row():
					start_img = gr.Image(label='First frame', interactive=False, height=220)
					end_img = gr.Image(label='Last frame', interactive=False, height=220)
				cut_btn = gr.Button('✂️ Cut this part', variant='primary')
				cut_player = gr.Video(label='Your cut', interactive=False, height=360)
				s2_msg = gr.Markdown()
				pos = gr.Number(value=None, elem_id='pos', elem_classes='hidden-pos', container=False)
			# 3
			with gr.Tab('3 · Your face', id='s3'):
				gr.Markdown('### Step 3: Add photos of YOUR face\n'
				            '**10-20 photos** · sharp and well lit · only you in the photo · mostly facing the camera '
				            '+ a few slight side turns · no sunglasses/hands/hair over the face · a few expressions.\n\n'
				            'Photos are saved in the `me` folder, so next time they are already here.')
				photos_in = gr.File(label='Add photos', file_count='multiple', file_types=['image'], type='filepath')
				g0, h0 = gallery_and_hint()
				gallery = gr.Gallery(value=g0, label='Your photos', columns=8, height=220)
				photo_hint = gr.Markdown(h0)
				with gr.Row():
					check_btn = gr.Button('🔍 Check my photos', variant='primary')
					clear_btn = gr.Button('🗑 Remove all photos (moves them to me/_old)', size='sm')
				report = gr.Dataframe(headers=['Photo', 'Result'], interactive=False, wrap=True)
				s3_msg = gr.Markdown()
				s3_next = gr.Button('Next ➜ Step 4')
			# 4
			with gr.Tab('4 · Who to replace', id='s4'):
				gr.Markdown('### Step 4: Choose the person to replace\n'
				            '1) Press **Find people**.  2) **Tick everyone who should get your face** (click their picture). '
				            'Same person in two looks, or "3 of me" on different people: tick them all.\n\n'
				            'Only the people you tick get your face; everyone else is left alone.')
				people_btn = gr.Button('🔎 Find people in this video', variant='primary')
				people_gallery = gr.Gallery(label='People in this video. Click to tick / untick', columns=6, height=240, allow_preview=False)
				people_pick = gr.CheckboxGroup([], label='Who gets your face? (tick one or more)')
				people_refs = gr.State([])
				picked_box = gr.State(None)
				multi_refs = gr.State([])
				with gr.Accordion('Or pick a moment yourself', open=False):
					gr.Markdown('Move the slider to a moment where the person is **big and facing the camera**, then press Find faces.')
					ref_time = gr.Slider(0, 1, value=0, step=0.1, label='Moment in your cut (seconds)')
					find_btn = gr.Button('👤 Find faces at this moment')
				faces_img = gr.Image(label='Faces found (numbered)', interactive=False, height=420)
				person = gr.Radio([], label='Who gets your face?')
				s4_msg = gr.Markdown()
				s4_next = gr.Button('Next ➜ Step 5')
			# 5
			with gr.Tab('5 · Make it', id='s5'):
				gr.Markdown('### Step 5: Test, then make your Short\n'
				            '1) Press **Test on one frame** and look closely.  2) If it looks right, press **Make my Short**.')
				with gr.Row():
					quality = gr.Radio(list(QUALITY), value='Best (most accurate, slower)', label='Quality')
					shape = gr.Radio(list(SHAPES), value=list(SHAPES)[0], label='Shape')
				smooth = gr.Radio(list(SMOOTHNESS), value='Normal (recommended)', label='Smoothness: removes face jitter / flicker between frames. Strong = smoothest, may leave faint trails on very fast movement')
				crop_x = gr.Slider(0, 100, value=50, step=1, label='Crop position: set automatically to the chosen person. Move it if needed (0 = left, 100 = right)')
				with gr.Accordion('Advanced', open=False):
					distance = gr.Slider(0.1, 0.8, value=0.4, step=0.05,
					                     label='Face matching. Raise it if your face is MISSING in some shots, lower it if OTHER people get your face')
				with gr.Row():
					crop_img = gr.Image(label='Frame + crop area', interactive=False, height=320)
					test_img = gr.Image(label='Test result (zoomed on the face)', interactive=False, height=320)
				test_btn = gr.Button('🔍 Test on one frame')
				s5_test_msg = gr.Markdown()
				go_btn = gr.Button('🚀 Make my Short', variant='primary', size='lg')
				result = gr.Video(label='Your Short', interactive=False, height=560)
				s5_msg = gr.Markdown()
				log = gr.Textbox(label='Progress', lines=8, max_lines=12)

		s1_outputs = [clip, s1_msg, player, start, end, start_img, end_img, range_md, existing, tabs]
		dl_btn.click(download_link, [url, browser, rights], s1_outputs)
		up_btn.click(upload_file, [up, rights], s1_outputs)
		up.upload(upload_file, [up, rights], s1_outputs)  # loads right after the upload finishes
		ex_btn.click(pick_existing, [existing, rights], s1_outputs)

		start.release(show_start, [clip, start, end], [start_img, range_md])
		end.release(show_end, [clip, start, end], [end_img, range_md])
		get_time = '(c, p, s, e) => { const v = document.querySelector("#player video"); return [c, v ? v.currentTime : null, s, e]; }'
		set_start.click(lambda c, p, s, e: set_from_player(c, 'start', p, s, e), [clip, pos, start, end],
		                [start, end, start_img, end_img, range_md], js=get_time)
		set_end.click(lambda c, p, s, e: set_from_player(c, 'end', p, s, e), [clip, pos, start, end],
		              [start, end, start_img, end_img, range_md], js=get_time)
		cut_btn.click(cut_clip, [clip, start, end], [cut, cut_player, s2_msg, ref_time, tabs])

		photos_in.upload(add_photos, [photos_in], [gallery, photo_hint])
		clear_btn.click(clear_photos, None, [gallery, photo_hint, good])
		check_btn.click(check_photos, None, [report, good, s3_msg])
		s3_next.click(to_step4, [good], tabs)

		people_btn.click(find_video_people, [cut], [people_gallery, people_refs, s4_msg, people_pick])
		people_gallery.select(toggle_person, [people_pick], people_pick)
		people_pick.change(people_chosen, [people_pick, people_refs], [ref_time, picked_box, multi_refs]).then(
			lambda chosen, cut_path, t: find_people(cut_path, t) if chosen else (gr.update(),) * 6,
			[people_pick, cut, ref_time], [faces_img, person, frame_index, ref_png, faces_state, s4_msg]).then(
			select_box, [faces_state, picked_box, person], person).then(
			auto_crop_x, [ref_png, faces_state, person], crop_x).then(
			people_summary, [people_pick, s4_msg], s4_msg)
		find_btn.click(lambda: ([], []), None, [people_pick, multi_refs]).then(find_people, [cut, ref_time], [faces_img, person, frame_index, ref_png, faces_state, s4_msg]).then(
			auto_crop_x, [ref_png, faces_state, person], crop_x).then(
			crop_preview, [ref_png, shape, crop_x], crop_img)
		s4_next.click(to_step5, [person], tabs).then(crop_preview, [ref_png, shape, crop_x], crop_img)

		person.input(on_person_change, [faces_state, person], s4_msg)
		person.change(auto_crop_x, [ref_png, faces_state, person], crop_x).then(crop_preview, [ref_png, shape, crop_x], crop_img)
		shape.change(crop_preview, [ref_png, shape, crop_x], crop_img)
		crop_x.release(crop_preview, [ref_png, shape, crop_x], crop_img)
		test_btn.click(test_frame, [good, ref_png, person, frame_index, quality, distance, faces_state, multi_refs, cut], [test_img, s5_test_msg])
		go_btn.click(make_short, [cut, good, person, frame_index, quality, distance, shape, crop_x, rights, multi_refs, smooth], [result, s5_msg, log])
	return app


PID_FILE = KIT / 'tools' / 'studio.pid'


def _linux_processes():
	"""(pid, parent pid, cwd, argv list) for every process we can see."""
	for entry in os.listdir('/proc'):
		if not entry.isdigit():
			continue
		try:
			with open(f'/proc/{entry}/cmdline', 'rb') as f:
				argv = [a.decode(errors='replace') for a in f.read().split(b'\0') if a]
			with open(f'/proc/{entry}/stat') as f:
				ppid = int(f.read().rsplit(')', 1)[1].split()[1])
			cwd = os.readlink(f'/proc/{entry}/cwd')
		except OSError:
			continue
		yield int(entry), ppid, cwd, argv


def _is_kit_studio(cwd: str, argv: list) -> bool:
	"""True only for '<python> [.../]studio.py ...' started from THIS kit (not shells, editors, grep...)."""
	if len(argv) < 2 or not os.path.basename(argv[0]).startswith('python'):
		return False
	script = argv[1]
	path = Path(script if os.path.isabs(script) else os.path.join(cwd, script))
	try:
		return path.resolve() == (KIT / 'studio.py').resolve()
	except OSError:
		return False


def stop_old_studios() -> int:
	"""Closes studios already running from this kit folder (and the swaps they started)."""
	me = os.getpid()
	stopped = 0
	if sys.platform.startswith('linux'):
		procs = list(_linux_processes())
		parent = {pid: ppid for pid, ppid, _, _ in procs}
		mine = {me}  # never stop myself or whatever started me
		p = me
		while p in parent and p > 1:
			p = parent[p]
			mine.add(p)
		old = [pid for pid, _, cwd, argv in procs if pid not in mine and _is_kit_studio(cwd, argv)]
		children = [pid for pid, ppid, _, _ in procs if ppid in old and pid not in mine]  # running swaps / face checks
		targets = children + old
		for pid in targets:
			try:
				os.kill(pid, 15)  # ask nicely
				stopped += pid in old
			except OSError:
				pass
		end = time.time() + 3
		while time.time() < end and any(os.path.exists(f'/proc/{pid}') for pid in targets):
			time.sleep(0.2)
		for pid in targets:  # old studios wait forever for open browser tabs, so force them
			try:
				os.kill(pid, 9)
			except OSError:
				pass
	elif os.name == 'nt' and PID_FILE.exists():
		try:
			pid = int(PID_FILE.read_text().strip())
			if pid != me:
				res = subprocess.run(['taskkill', '/PID', str(pid), '/T', '/F'], capture_output=True)
				stopped += res.returncode == 0
		except (OSError, ValueError):
			pass
	try:
		PID_FILE.write_text(str(me))
	except OSError:
		pass
	return stopped


def wait_for_port(port: int, seconds: float = 10) -> bool:
	import socket
	end = time.time() + seconds
	while time.time() < end:
		with socket.socket() as sock:
			try:
				sock.bind(('127.0.0.1', port))
				return True
			except OSError:
				time.sleep(0.5)
	return False


if __name__ == '__main__':
	port = int(os.environ.get('GRADIO_SERVER_PORT', 7860))
	if os.environ.get('STUDIO_KEEP_OTHERS') != '1':  # set to 1 to run a second studio on purpose
		n = stop_old_studios()
		if n:
			print(f'Closed {n} studio window(s) that were already running.', flush=True)
	if not wait_for_port(port):
		print(f'Port {port} is busy. Using the next free one (see the address below).')
		port = None
	for old in list(WORK.glob('reference_frame_*.png')) + list(WORK.glob('test_*.png')):  # tidy previews older than a day
		try:
			if time.time() - old.stat().st_mtime > 86400:
				old.unlink()
		except OSError:
			pass
	app = build()
	print('Face-Swap Studio: open http://127.0.0.1:' + str(port or 'see below') + ' if the browser does not open.', flush=True)
	app.queue().launch(server_name='127.0.0.1', server_port=port, inbrowser='--no-browser' not in sys.argv,
	                   allowed_paths=[str(KIT)], show_api=False)
