from flask import current_app

from .job_queue import JobQueue
from .workers import evaluate_submission, reevaluate_submission, evaluate_result, reevaluate_result


def create_job_queue(app):
    return JobQueue(max_processes=app.config['MAX_WORKERS'])


def enqueue_evaluate_submission(submission_id):
    current_app.job_queue.put(
        evaluate_submission,
        args=(submission_id,),
    )


def enqueue_reevaluate_submission(submission_id):
    current_app.job_queue.put(
        reevaluate_submission,
        args=(submission_id,),
    )


def enqueue_evaluate_result(result_id):
    current_app.job_queue.put(
        evaluate_result,
        args=(result_id,),
    )


def enqueue_reevaluate_result(result_id):
    current_app.job_queue.put(
        reevaluate_result,
        args=(result_id,),
    )
