"""
Builds example face sets for testing: 15 photos per person, made from one
AI-generated face (thispersondoesnotexist.com, StyleGAN, not a real person)
with FaceFusion's face editor (head turns + expressions), the face enhancer
(keeps them sharp), and small
framing/lighting changes.

Usage (from the kit folder):
  tools/env/bin/python example_faces/make_examples.py example_faces/_base/base2.jpg person_A
"""
import random
import zlib
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

KIT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KIT))
import swap as kit  # noqa: E402

VARIANTS = [
	('01_front', {}),
	('02_turn_right', {'head-yaw': 0.3}),
	('03_turn_left', {'head-yaw': -0.3}),
	('04_turn_right_more', {'head-yaw': 0.5}),
	('05_turn_left_more', {'head-yaw': -0.5}),
	('06_look_up', {'head-pitch': 0.25}),
	('07_look_down', {'head-pitch': -0.25}),
	('08_neutral', {'mouth-smile': -0.6}),
	('09_big_smile', {'mouth-smile': 0.6}),
	('10_talking', {'lip-open-ratio': 0.6}),
	('11_right_neutral', {'head-yaw': 0.3, 'mouth-smile': -0.5}),
	('12_left_talking', {'head-yaw': -0.3, 'lip-open-ratio': 0.5}),
	('13_surprised', {'eyebrow-direction': 0.6, 'eye-open-ratio': 0.4, 'lip-open-ratio': 0.3}),
	('14_head_tilt', {'head-roll': 0.2, 'mouth-smile': 0.3}),
	('15_down_left_neutral', {'head-pitch': -0.15, 'head-yaw': -0.2, 'mouth-smile': -0.5}),
]


def vary_photo(path: Path, seed: int) -> None:
	"""Small zoom/shift/brightness change so each looks like a separate photo."""
	rnd = random.Random(seed)
	img = cv2.imread(str(path))
	h, w = img.shape[:2]
	zoom = rnd.uniform(0.82, 0.97)
	cw, ch = int(w * zoom), int(h * zoom)
	x = rnd.randint(0, w - cw)
	y = rnd.randint(0, h - ch)
	img = cv2.resize(img[y:y + ch, x:x + cw], (800, 800), interpolation=cv2.INTER_AREA)
	alpha = rnd.uniform(0.9, 1.1)
	beta = rnd.uniform(-12, 12)
	img = np.clip(img.astype(np.float32) * alpha + beta, 0, 255).astype(np.uint8)
	path.unlink()
	cv2.imwrite(str(path.with_name(path.name.replace('_raw', '')).with_suffix('.jpg')), img, [cv2.IMWRITE_JPEG_QUALITY, 92])


def main() -> None:
	base = Path(sys.argv[1]).resolve()
	out = Path(__file__).resolve().parent / sys.argv[2]
	out.mkdir(parents=True, exist_ok=True)
	env = kit.tool_env()
	for i, (name, edits) in enumerate(VARIANTS):
		target = out / (name + '_raw' + base.suffix)
		if (out / (name + '.jpg')).exists():
			continue
		if not edits:
			cv2.imwrite(str(target), cv2.imread(str(base)))
		else:
			cmd = [sys.executable, 'facefusion.py', 'headless-run', '--target-path', str(base),
			       '--output-path', str(target), '--processors', 'face_editor', 'face_enhancer',
			       '--face-enhancer-model', 'gpen_bfr_512', '--face-enhancer-blend', '85',
			       '--execution-providers', kit.provider(), '--log-level', 'error', '--output-image-quality', '100']
			for key, value in edits.items():
				cmd += ['--face-editor-' + key, str(value)]
			res = subprocess.run(cmd, cwd=kit.FACEFUSION, env=env)
			if res.returncode != 0 or not target.exists():
				sys.exit('failed: ' + name)
		vary_photo(target, seed=zlib.crc32((sys.argv[2] + name).encode()))
		print('made', out.name, name)


if __name__ == '__main__':
	main()
