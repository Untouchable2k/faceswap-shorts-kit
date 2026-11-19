"""
Detects faces with FaceFusion's own models so the studio shows exactly the faces
(and the same numbering) that FaceFusion will use.

Usage: python faces_helper.py <execution_provider> [--embed] <image> [<image> ...]
(--embed adds each face's identity vector, used to group faces by person)
Prints one line:  FACES_JSON {"<image>": [{"box": [x1,y1,x2,y2], "score": 0.9}, ...], ...}
Faces are sorted left-to-right (matches --face-selector-order left-right).
"""
import io
import json
import os
import sys
from contextlib import redirect_stdout
from pathlib import Path

FF = Path(__file__).resolve().parent / 'facefusion'
sys.path.insert(0, str(FF))
os.chdir(FF)


def main() -> None:
	provider = sys.argv[1]
	embed = '--embed' in sys.argv
	images = [a for a in sys.argv[2:] if a != '--embed']
	noise = io.StringIO()
	with redirect_stdout(noise):
		from facefusion import state_manager, face_detector, face_landmarker, face_recognizer, face_classifier
		from facefusion.args import apply_args
		from facefusion.program import create_program
		from facefusion.face_creator import get_many_faces
		from facefusion.face_selector import sort_faces_by_order
		from facefusion.vision import read_static_image

		program = create_program()
		args = vars(program.parse_args([ 'headless-run', '--execution-providers', provider, '--log-level', 'error' ]))
		apply_args(args, state_manager.init_item)
		for module in (face_detector, face_landmarker, face_recognizer, face_classifier):
			if not module.pre_check():
				raise SystemExit('model download failed for ' + module.__name__)

		result = {}
		for image in images:
			frame = read_static_image(image)
			faces = sort_faces_by_order(get_many_faces([ frame ]), 'left-right') if frame is not None else []
			result[image] = []
			for face in faces:
				item = { 'box': [ float(v) for v in face.bounding_box ], 'score': float(face.score_set.get('detector', 0)) }
				if embed and face.embedding_norm is not None:
					item['embedding'] = [ round(float(v), 4) for v in face.embedding_norm ]
				result[image].append(item)
	print('FACES_JSON ' + json.dumps(result))


if __name__ == '__main__':
	main()
