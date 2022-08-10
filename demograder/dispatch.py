from flask import current_app

from .job_queue import JobQueue
from .workers import evaluate_submission, evaluate_result


# INITIALIZE JOB QUEUE


def create_job_queue(app):
    return JobQueue(max_processes=app.config['MAX_WORKERS'])


def enqueue_evaluate_submission(submission_id):
    current_app.job_queue.put(
        evaluate_submission,
        args=(submission_id,),
    )


def enqueue_evaluate_result(result_id):
    current_app.job_queue.put(
        evaluate_result,
        args=(result_id,),
    )
