from typing import Optional, List
import json
import os
import shutil

from facefusion.common_helper import get_current_datetime
from facefusion.filesystem import is_file, is_directory
from facefusion.typing import JobStep, Job, Args, JobStatus, JobStepStatus, JobStepAction

JOBS_PATH : Optional[str] = None
JOB_STATUSES : List[JobStatus] = [ 'queued', 'completed', 'failed' ]


def init_jobs(jobs_path : str) -> bool:
	global JOBS_PATH

	JOBS_PATH = jobs_path
	job_status_paths = [ os.path.join(JOBS_PATH, job_status) for job_status in JOB_STATUSES ]

	for job_status_path in job_status_paths:
		os.makedirs(job_status_path, exist_ok = True)
	return all(is_directory(status_path) for status_path in job_status_paths)


def clear_jobs(jobs_path : str) -> None:
	if is_directory(jobs_path):
		shutil.rmtree(jobs_path)


def create_job(job_id : str) -> bool:
	job : Job =\
	{
		'version': '1',
		'date_created': get_current_datetime(),
		'date_updated': None,
		'steps': []
	}

	return create_job_file(job_id, job)


def delete_job(job_id : str) -> bool:
	return delete_job_file(job_id)


def get_job_status(job_id : str) -> Optional[JobStatus]:
	for job_status in JOB_STATUSES:
		if job_id in find_job_ids(job_status):
			return job_status
	return None


def find_job_ids(job_status : JobStatus) -> List[str]:
	job_ids = []
	job_file_names = os.listdir(os.path.join(JOBS_PATH, job_status))

	for job_file_name in job_file_names:
		if is_file(os.path.join(JOBS_PATH, job_status, job_file_name)):
			job_ids.append(os.path.splitext(job_file_name)[0])
	return job_ids


def add_step(job_id : str, step_args : Args) -> bool:
	job = read_job_file(job_id)

	if job:
		step = create_step(step_args)
		job.get('steps').append(step)
		return update_job_file(job_id, job)
	return False


def remix_step(job_id : str, step_index : int, step_args : Args) -> bool:
	steps = get_steps(job_id)
	output_path = steps[step_index].get('args').get('output_path')

	if not is_directory(output_path):
		step_args['target_path'] = output_path
		return add_step(job_id, step_args) and set_step_action(job_id, step_index + 1, 'remix')
	return False


def insert_step(job_id : str, step_index : int, step_args : Args) -> bool:
	job = read_job_file(job_id)

	if job:
		step = create_step(step_args)
		job.get('steps').insert(step_index, step)
		return update_job_file(job_id, job)
	return False


def remove_step(job_id : str, step_index : int) -> bool:
	job = read_job_file(job_id)

	if job:
		job.get('steps').pop(step_index)
		return update_job_file(job_id, job)
	return False


def get_step(job_id : str, step_index : int) -> Optional[JobStep]:
	steps = get_steps(job_id)

	for index, step in enumerate(steps):
		if index == step_index:
			return step
	return None


def get_steps(job_id : str) -> Optional[List[JobStep]]:
	job = read_job_file(job_id)

	if job:
		return job.get('steps')
	return None


def create_step(args : Args) -> JobStep:
	step : JobStep =\
	{
		'action': 'process',
		'args': args,
		'status': 'queued'
	}

	return step


def set_step_status(job_id : str, step_index : int, step_status : JobStepStatus) -> bool:
	job = read_job_file(job_id)
	steps = job.get('steps')

	for index, step in enumerate(steps):
		if index == step_index:
			job.get('steps')[index]['status'] = step_status
			return update_job_file(job_id, job)
	return False


def set_step_action(job_id : str, step_index : int, step_action : JobStepAction) -> bool:
	job = read_job_file(job_id)
	steps = job.get('steps')

	for index, step in enumerate(steps):
		if index == step_index:
			job.get('steps')[index]['action'] = step_action
			return update_job_file(job_id, job)
	return False


def read_job_file(job_id : str) -> Optional[Job]:
	job_path = resolve_job_path(job_id)

	if is_file(job_path):
		with open(job_path, 'r') as job_file:
			return json.load(job_file)
	return None


def create_job_file(job_id : str, job : Job) -> bool:
	job_path = suggest_job_path(job_id)

	if is_file(job_path):
		with open(job_path, 'w') as job_file:
			json.dump(job, job_file, indent = 4)
		return is_file(job_path)
	return False


def update_job_file(job_id : str, job : Job) -> bool:
	job_path = resolve_job_path(job_id)

	if is_file(job_path):
		with open(job_path, 'w') as job_file:
			job['date_updated'] = get_current_datetime()
			json.dump(job, job_file, indent = 4)
		return is_file(job_path)
	return False


def move_job_file(job_id : str, job_status : JobStatus) -> bool:
	job_path = resolve_job_path(job_id)

	if is_file(job_path):
		job_file_path_moved = shutil.move(job_path, os.path.join(JOBS_PATH, job_status))
		return is_file(job_file_path_moved)
	return False


def delete_job_file(job_id : str) -> bool:
	job_path = resolve_job_path(job_id)

	if is_file(job_path):
		os.remove(job_path)
		return not is_file(job_path)
	return False


def suggest_job_path(job_id : str) -> Optional[str]:
	job_file_name = job_id + '.json'
	job_path = os.path.join(JOBS_PATH, 'queued', job_file_name)

	if not is_file(job_path):
		return job_path
	return None


def resolve_job_path(job_id : str) -> Optional[str]:
	job_file_name = job_id + '.json'

	for job_status in JOB_STATUSES:
		if job_file_name in os.listdir(os.path.join(JOBS_PATH, job_status)):
			return os.path.join(JOBS_PATH, job_status, job_file_name)
	return None
