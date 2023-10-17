from typing import Any, Dict
import threading
from functools import lru_cache

import cv2
import numpy
import onnxruntime
from tqdm import tqdm

import facefusion.globals
from facefusion import wording
from facefusion.typing import Frame, ModelValue
from facefusion.vision import get_video_frame, count_video_frame_total, read_image, detect_fps
from facefusion.utilities import resolve_relative_path, conditional_download

PREDICTOR = None
THREAD_LOCK : threading.Lock = threading.Lock()
NAME = 'FACEFUSION.PREDICTOR'
MODELS : Dict[str, ModelValue] =\
{
	'open_nsfw':
	{
		'url': 'https://github.com/facefusion/facefusion-assets/releases/download/models/open_nsfw.onnx',
		'path': resolve_relative_path('../.assets/models/open_nsfw.onnx')
	}
}
MAX_PROBABILITY = 0.80
MAX_RATE = 5
STREAM_COUNTER = 0


def get_predictor() -> Any:
	global PREDICTOR

	with THREAD_LOCK:
		if PREDICTOR is None:
			model_path = MODELS.get('open_nsfw').get('path')
			PREDICTOR = onnxruntime.InferenceSession(model_path, providers = facefusion.globals.execution_providers)
	return PREDICTOR


def clear_predictor() -> None:
	global PREDICTOR

	PREDICTOR = None


def pre_check() -> bool:
	if not facefusion.globals.skip_download:
		download_directory_path = resolve_relative_path('../.assets/models')
		model_url = MODELS.get('open_nsfw').get('url')
		conditional_download(download_directory_path, [ model_url ])
	return True


def predict_stream(frame : Frame, fps : float) -> bool:
	global STREAM_COUNTER

	STREAM_COUNTER = STREAM_COUNTER + 1
	if STREAM_COUNTER % int(fps) == 0:
		return predict_frame(frame)
	return False


def prepare_frame(frame : Frame) -> Frame:
	frame = cv2.resize(frame, (224, 224)).astype(numpy.float32)
	frame -= numpy.array([ 104, 117, 123 ]).astype(numpy.float32)
	frame = numpy.expand_dims(frame, axis = 0)
	return frame


def predict_frame(frame : Frame) -> bool:
	predictor = get_predictor()
	frame = prepare_frame(frame)
	probability = predictor.run(None,
	{
		'input:0': frame
	})[0][0][1]
	return probability > MAX_PROBABILITY


@lru_cache(maxsize = None)
def predict_image(image_path : str) -> bool:
	frame = read_image(image_path)
	return predict_frame(frame)


@lru_cache(maxsize = None)
def predict_video(video_path : str, start_frame : int, end_frame : int) -> bool:
	video_frame_total = count_video_frame_total(video_path)
	fps = detect_fps(video_path)
	frame_range = range(start_frame or 0, end_frame or video_frame_total)
	rate = 0
	counter = 0
	with tqdm(total = len(frame_range), desc = wording.get('analysing'), unit = 'frame') as progress:
		for frame_number in frame_range:
			if frame_number % int(fps) == 0:
				frame = get_video_frame(video_path, frame_number)
				if predict_frame(frame):
					counter += 1
			rate = counter * int(fps) / len(frame_range) * 100
			progress.update()
			progress.set_postfix(rate = rate)
	return rate > MAX_RATE
