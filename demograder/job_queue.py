"""A job queue that dispatches jobs to separate processes."""

import logging
from typing import Any, Callable, Dict, Mapping, Optional, Tuple
from collections import namedtuple
from itertools import count as sequence
from multiprocessing import Queue as ProcessQueue, Process
from os import cpu_count
from queue import Queue as ThreadQueue
from threading import Lock, Condition, Thread

__all__ = ['JobQueue']


class JobData:
    """Container for information about a job."""

    COUNTER = sequence()

    def __init__(
        self,
        function, # type: Callable[[Any], Any]
        args=None, # type: Optional[Sequence[Any]]
        kwargs=None, # type: Optional[Mapping[Any, Any]]
        callback=None, # type: Optional[Callable[[Any], Any]]
        error_callback=None, # type: Optional[Callable[[Any], Any]]
    ):
        # type: (...) -> None
        """Initialize a JobData.

        Parameters:
            function (Callable): The function to run.
            args (Tuple): The positional arguments to the function.
            kwargs (Mapping): The keyword arguments to the function.
            callback (Callable[[Any], Any]): The function to call when the
                function succeeds. Defaults to None.
            error_callback (Callable[[Any], Any]): The function to call when
                the function succeeds. Defaults to None.
        """
        self.process_id = next(JobData.COUNTER)
        self.function = function
        self.args = args
        self.kwargs = kwargs
        self.callback = callback
        self.error_callback = error_callback


ProcessInput = namedtuple('ProcessInput', 'process_id, function, args, kwargs')
ProcessOutput = namedtuple('ProcessOutput', 'process_id, error, result')


class JobQueue:
    """A job queue that dispatches jobs to separate processes.

    This class uses a thread-level queue (the wait-queue) and two process-level
    queues (the run-queue and the result-queue). These queues are used to
    communicate between three threads (the main-thread, the in-thread, and the
    out-thread) and the spawned processes. The threads are coordinated with a
    has-idle-process Condition, which ensures that only a fixed number of
    process are created at maximum.

    The workflow for a submitted job is:

    1. The main-thread creates a JobData about the job with a unique ID.
    That ID is added to the wait-queue.

    2. The run-thread gets an ID from the wait-queue and gets the job function
    and arguments from the main-thread cache. If the maximum number of
    processes has been reached, it waits for the has-idle-process condition.
    Once the condition is met, the thread adds the job and its ID to the
    run-queue. It then spawns a process with the run-queue and the result-queue
    as the arguments.

    3. The new process gets the job function and the arguments from the
    run-queue, then runs it. The ID of the job and its result are put in the
    result-queue. The process completes and terminates.

    4. The result-thread gets the result from the result-queue, and runs the
    callback functions. The has-idle-process condition is then notified so a
    new process can spawn if necessary.
    """

    def __init__(self, max_processes: int = None):
        """Initialize the JobQueue.

        Parameters:
            max_processes (int): The maximum number of processes running.
                Defaults to the number of CPUs, or if indeterminable, to 4.
        """
        # parameters
        if max_processes is None:
            max_processes = cpu_count()
        if max_processes is None:
            max_processes = 4
        self._max_processes: int = max_processes # TODO use multiprocessing.Pool instead?
        # variables
        self._num_processes = 0
        self.job_data: Dict[int, JobData] = {}
        self.mutex = Lock()
        self.has_idle_process = Condition(self.mutex)
        # queues
        self.wait_queue: ThreadQueue = ThreadQueue()
        self.run_queue: ProcessQueue = ProcessQueue()
        self.result_queue: ProcessQueue = ProcessQueue()
        # threads
        # TODO handle signals to exit cleanly
        self.in_thread = Thread(
            name='in-thread',
            target=run_thread_main,
            args=(self,),
        )
        self.out_thread = Thread(
            name='out-thread',
            target=result_thread_main,
            args=(self,),
        )
        self.in_thread.start()
        self.out_thread.start()

    def __len__(self):
        """Return the approximate number of items in the wait-queue."""
        return self.wait_queue.qsize()

    @property
    def idle_processes(self) -> int:
        """Return the number of "idle" processes.

        Returns:
            int: the number of "idle" processes.
        """
        return self.max_processes - self.num_processes

    @property
    def max_processes(self) -> int:
        """Return the number of maximum concurrent processes.

        Returns:
            int: the number of maximum concurrent processes.
        """
        return self._max_processes

    @property
    def num_processes(self) -> int:
        """Return the number of running processes.

        Returns:
            int: the number of running processes.
        """
        return self._num_processes

    def spawned_process(self) -> None:
        """Increment the number of running processes."""
        self._num_processes += 1

    def terminated_process(self) -> None:
        """Decrement the number of running processes."""
        self._num_processes -= 1

    def put(
        self,
        function: Callable,
        args: Tuple = None,
        kwargs: Mapping = None,
        callback: Optional[Callable[[Any], Any]] = None,
        error_callback: Optional[Callable[[Any], Any]] = None,
    ) -> None:
        """Add a job to be run.

        Parameters:
            function (Callable): The function to run.
            args (Tuple): The positional arguments to the function.
            kwargs (Mapping): The keyword arguments to the function.
            callback (Callable[Any, None]): The function to call when the
                function succeeds.
            error_callback (Callable[Any, None]): The function to call when the
                function succeeds.
        """
        if args is None:
            args = ()
        if kwargs is None:
            kwargs = {}
        job_data = JobData(function, args, kwargs, callback, error_callback)
        self.job_data[job_data.process_id] = job_data
        self.wait_queue.put(job_data.process_id)


def worker_main(run_queue: ProcessQueue, result_queue: ProcessQueue) -> None:
    """Run a job.

    Parameters:
        run_queue (ProcessQueue): The queue to get job parameters.
        result_queue (ProcessQueue): The queue to put job results.
    """
    process_input = run_queue.get()
    process_id = process_input.process_id
    try:
        result = process_input.function(
            *process_input.args,
            **process_input.kwargs,
        )
        error = False
    except Exception as exception: # pylint: disable = broad-except
        result = exception
        error = True
    result_queue.put(ProcessOutput(process_id, error, result))


def run_thread_main(job_queue: JobQueue) -> None:
    """Spawn processes to run jobs.

    Parameters:
        job_queue (JobQueue): The managing JobQueue.
    """
    logging.info('run thread started')
    while True:
        process_id = job_queue.wait_queue.get()
        with job_queue.has_idle_process:
            if job_queue.idle_processes == 0:
                job_queue.has_idle_process.wait()
            job_queue.spawned_process()
            job_data = job_queue.job_data[process_id]
        job_queue.run_queue.put(ProcessInput(
            job_data.process_id,
            job_data.function,
            job_data.args,
            job_data.kwargs,
        ))
        process = Process(
            target=worker_main,
            args=(job_queue.run_queue, job_queue.result_queue),
            daemon=True,
        )
        process.start()


def result_thread_main(job_queue: JobQueue) -> None:
    """Deal with results from completed jobs.

    Parameters:
        job_queue (JobQueue): The managing JobQueue.
    """
    logging.info('result thread started')
    while True:
        process_output = job_queue.result_queue.get()
        process_id = process_output.process_id
        job_data = job_queue.job_data[process_id]
        if process_output.error:
            if job_data.error_callback is not None:
                job_data.error_callback(process_output.result)
        else:
            if job_data.callback is not None:
                job_data.callback(*process_output.result)
        with job_queue.has_idle_process:
            job_queue.terminated_process()
            del job_queue.job_data[process_id]
            job_queue.has_idle_process.notify()


def demo_work_main(seconds):
    """Track the start and end times of a job.

    Parameters:
        seconds (int): The number of seconds this job should take.

    Returns:
        int: The same value as the seconds parameter.
        str: The starting local time of this job.
        str: The ending local time of this job.
        float: The total time elapsed for this job, in seconds.
    """
    from datetime import datetime
    from time import sleep, monotonic
    start_time = datetime.now().time().isoformat('seconds')
    start = monotonic()
    count = 0
    for _ in range(seconds):
        count += 1
        sleep(1)
    end = monotonic()
    end_time = datetime.now().time().isoformat('seconds')
    return (count, start_time, end_time, end - start)


def demo():
    """Demonstrate that the job queue works."""
    from time import sleep

    def callback(result, start_time, end_time, elapsed):
        print(f'{result:2d} ({start_time} to {end_time}; {elapsed:.3f}s total)')

    queue = JobQueue(max_processes=4)
    for seconds in [10, 5, 2, 1, 1, 1, 5]:
        queue.put(demo_work_main, args=(seconds,), callback=callback)
    sleep(20)
    for seconds in [10, 5, 2, 1, 1, 1, 5]:
        queue.put(demo_work_main, args=(seconds,), callback=callback)


if __name__ == '__main__':
    demo()
