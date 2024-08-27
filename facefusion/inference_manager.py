from functools import lru_cache
from time import sleep
from typing import List

import onnx
from onnxruntime import InferenceSession

from facefusion import process_manager, state_manager
from facefusion.app_context import detect_app_context
from facefusion.execution import create_execution_providers, has_execution_provider
from facefusion.thread_helper import thread_lock
from facefusion.typing import DownloadSet, ExecutionProviderKey, InferencePool, InferencePoolSet, ModelInitializer

INFERENCE_POOLS : InferencePoolSet =\
{
	'cli': {},  # type:ignore[typeddict-item]
	'ui': {}  # type:ignore[typeddict-item]
}


def get_inference_pool(model_context : str, model_sources : DownloadSet) -> InferencePool:
	global INFERENCE_POOLS

	with thread_lock():
		while process_manager.is_checking():
			sleep(0.5)
		app_context = detect_app_context()

		if app_context == 'cli' and INFERENCE_POOLS.get('ui').get(model_context):
			INFERENCE_POOLS['cli'][model_context] = INFERENCE_POOLS.get('ui').get(model_context)
		if app_context == 'ui' and INFERENCE_POOLS.get('cli').get(model_context):
			INFERENCE_POOLS['ui'][model_context] = INFERENCE_POOLS.get('cli').get(model_context)
		if INFERENCE_POOLS.get(app_context).get(model_context) is None:
			INFERENCE_POOLS[app_context][model_context] = create_inference_pool(model_sources, state_manager.get_item('execution_device_id'), find_execution_providers(model_context))

		return INFERENCE_POOLS.get(app_context).get(model_context)


def create_inference_pool(model_sources : DownloadSet, execution_device_id : str, execution_provider_keys : List[ExecutionProviderKey]) -> InferencePool:
	inference_pool : InferencePool = {}

	for model_name in model_sources.keys():
		inference_pool[model_name] = create_inference_session(model_sources.get(model_name).get('path'), execution_device_id, execution_provider_keys)
	return inference_pool


def clear_inference_pool(model_context : str) -> None:
	global INFERENCE_POOLS

	app_context = detect_app_context()
	INFERENCE_POOLS[app_context][model_context] = None


def create_inference_session(model_path : str, execution_device_id : str, execution_provider_keys : List[ExecutionProviderKey]) -> InferenceSession:
	providers = create_execution_providers(execution_device_id, execution_provider_keys)
	return InferenceSession(model_path, providers = providers)


@lru_cache(maxsize = None)
def get_static_model_initializer(model_path : str) -> ModelInitializer:
	model = onnx.load(model_path)
	return onnx.numpy_helper.to_array(model.graph.initializer[-1])


def find_execution_providers(model_context : str) -> List[ExecutionProviderKey]:
	if has_execution_provider('coreml') and model_context in [ 'facefusion.processors.modules.age_modifier', 'facefusion.processors.modules.frame_colorizer' ]:
		return [ 'cpu' ]
	return state_manager.get_item('execution_providers')