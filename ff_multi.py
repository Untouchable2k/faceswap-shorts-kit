"""
Runs FaceFusion with SEVERAL reference people at once, so every chosen person gets the new face
(the same person in two looks, or "3 of me" on different people). FaceFusion itself only supports
one reference person; this launcher swaps in a selector that matches against all of them.
FaceFusion's files are not modified.

Usage: python ff_multi.py --refs <refs.json> <normal facefusion.py arguments>
refs.json: {"video": "<path of the clip the references come from>",
            "refs": [{"frame": 825, "box": [x1, y1, x2, y2]}, ...],      people who GET the face
            "avoid": [{"frame": 1095, "box": [...]}, ...]}               people who must NOT (optional)
A face is swapped only if it is within the distance of a chosen person AND closer to a chosen
person than to every person in "avoid" (closest person wins). Without this, an unchosen person
whose face is borderline-similar (e.g. a blurry side profile) can get swapped by mistake.
"""
import json
import os
import sys
import threading
from pathlib import Path

FF = Path(__file__).resolve().parent / 'facefusion'
sys.path.insert(0, str(FF))
os.chdir(FF)
os.environ['OMP_NUM_THREADS'] = '1'


def overlap(a, b) -> float:
	ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
	iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
	union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - ix * iy
	return ix * iy / union if union > 0 else 0.0


def install(refs_file: str) -> None:
	from facefusion import state_manager
	from facefusion import face_selector
	from facefusion.common_helper import get_middle
	from facefusion.face_creator import get_static_faces
	from facefusion.face_tracker import track_faces
	from facefusion.vision import read_static_video_frame

	spec = json.loads(Path(refs_file).read_text())
	original_select = face_selector.select_faces
	cache = {}
	lock = threading.Lock()

	def load(items):
		faces = []
		for ref in items:
			frame = read_static_video_frame(spec['video'], int(ref['frame']))
			candidates = get_static_faces([ frame ]) if frame is not None else []
			if candidates:
				best = max(candidates, key = lambda face: overlap([ float(v) for v in face.bounding_box ], ref['box']))
				if overlap([ float(v) for v in best.bounding_box ], ref['box']) > 0.3:
					faces.append(best)
		return faces

	def reference_faces():
		with lock:
			if 'faces' not in cache:
				cache['faces'] = load(spec['refs'])
				cache['avoid'] = load(spec.get('avoid', []))
				print(f'[FF_MULTI] {len(cache["faces"])} chosen people, {len(cache["avoid"])} protected people', flush = True)
			return cache['faces'], cache['avoid']

	def select_faces(reference_vision_frame, source_vision_frames, target_vision_frames):
		if state_manager.get_item('face_selector_mode') != 'reference':
			return original_select(reference_vision_frame, source_vision_frames, target_vision_frames)
		if state_manager.get_item('face_tracker_score') > 0:
			target_faces = track_faces(target_vision_frames, state_manager.get_item('face_tracker_score'))
		else:
			target_faces = get_static_faces([ get_middle(target_vision_frames) ])
		chosen, avoid = reference_faces()
		limit = state_manager.get_item('reference_face_distance')
		selected = []
		for face in target_faces:
			d_chosen = min((face_selector.calculate_face_distance(face, ref) for ref in chosen), default = 9.0)
			d_avoid = min((face_selector.calculate_face_distance(face, ref) for ref in avoid), default = 9.0)
			# same scale as FaceFusion's compare_faces: interp(distance, [0, 2], [0, 1]) < limit
			if d_chosen / 2 < limit and d_chosen < d_avoid:  # close enough AND closest to a chosen person
				selected.append(face)
		return selected

	face_selector.select_faces = select_faces
	import importlib
	for name in ('face_swapper', 'face_enhancer'):
		module = importlib.import_module(f'facefusion.processors.modules.{name}.core')
		module.select_faces = select_faces


if __name__ == '__main__':
	args = sys.argv[1:]
	if len(args) >= 2 and args[0] == '--refs':
		refs_file = args[1]
		from facefusion import conda, core
		conda.setup()  # may restart this script with the same arguments, so run it before changing sys.argv
		sys.argv = [ str(FF / 'facefusion.py') ] + args[2:]
		install(refs_file)
		core.cli()
	else:
		sys.exit(__doc__)
