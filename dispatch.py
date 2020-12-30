
from .job_queue import JobQueue
from .models import Question, Submission, Result

JOB_QUEUE = JobQueue(max_processes=3)


def prepare_files():
    pass


def enqueue_grade_project():
    pass


def evaluate_project():
    pass


def enqueue_grade_submission():
    pass


def evaluate_submission():
    pass


def enqueue_grade_result():
    JOB_QUEUE.put(
        func,
        args=(filepath, 10),
        callback=callback,
        error_callback=error_callback,
    )


def evaluate_result():
    # TODO delete existing results
    pass
