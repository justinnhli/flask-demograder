import sys
from itertools import product, chain
from os import chmod, walk
from os.path import join as join_path
from pathlib import Path
from shutil import copyfile
from subprocess import run as run_process, PIPE
from tempfile import TemporaryDirectory

from sqlalchemy import select

# pylint: disable = import-outside-toplevel

sys.path.append(str(Path(__file__).parent))


def evaluate_submission(submission_id):
    result_ids = []
    for dependent_ids in expand_submission(submission_id):
        result_ids.append(create_empty_result(submission_id, dependent_ids))
    for result_id in result_ids:
        evaluate_result(result_id)


def expand_submission(submission_id):
    from demograder import create_app
    from demograder.models import db, User, Student, Instructor, Submission
    with create_app(with_queue=False).app_context():
        submission = db.session.scalar(select(Submission).where(Submission.id == submission_id))
        permute_args = []
        course_id = submission.course.id
        for dependency in submission.question.upstream_dependencies:
            if dependency.submitters == 'everyone':
                submitters = [
                    *(
                        student.id for student in
                        submission.question.assignment.course.students
                    ),
                    *(
                        instructor.id for instructor in 
                        submission.question.assignment.course.instructors
                    ),
                ]
            elif dependency.submitters == 'students':
                submitters = [
                    student.id for student in
                    submission.question.assignment.course.students
                ]
            elif dependency.submitters == 'instructors':
                submitters = [
                    instructor.id for instructor in 
                    submission.question.assignment.course.instructors
                ]
            else:
                assert False
            permute_args.append(
                db.session.scalars(
                    select(Submission)
                    .where(Submission.question_id == dependency.producer_id)
                    .where(Submission.disabled == False)
                    .where(Submission.user_id.in_(submitters))
                )
            )
        if permute_args:
            return [
                [submission.id for submission in family]
                for family in product(*permute_args)
            ]
        else:
            return []


def create_empty_result(submission_id, dependent_ids):
    from demograder import create_app
    from demograder.models import db, Result, ResultDependency
    with create_app(with_queue=False).app_context():
        result = Result(submission_id=submission_id)
        db.session.add(result)
        db.session.commit()
        for dependent_id in dependent_ids:
            db.session.add(ResultDependency(result_id=result.id, submission_id=dependent_id))
        db.session.commit()
        return result.id


def recursive_chmod(path):
    # FIXME Path.walk() will be available in Python 3.12
    '''
    path.chmod(0o777)
    for root, dirs, files in path.walk():
        for d in dirs:
            root.joinpath(d).chmod(0o777)
        for f in files:
            root.joinpath(f).chmod(0o777)
    '''
    chmod(path, 0o777)
    for root, dirs, files in walk(path):
        for d in dirs:
            chmod(join_path(root, d), 0o777)
        for f in files:
            chmod(join_path(root, f), 0o777)


def evaluate_result(result_id):
    from demograder import create_app
    from demograder.models import db, Result
    with create_app(with_queue=False).app_context():
        result = db.session.scalar(select(Result).where(Result.id == result_id))
        # create a temporary directory for evaluation
        with TemporaryDirectory() as temp_dir:
            temp_dir = Path(temp_dir)
            # write the evaluation script
            with temp_dir.joinpath('.script').open('w', encoding='utf-8') as fd:
                for line in result.question.script.splitlines():
                    fd.write(line.rstrip())
                    fd.write('\n')
                fd.write('\n')
            for submission in chain(result.upstream_submissions, [result.submission]):
                for submission_file in submission.files:
                    copyfile(submission_file.filepath, temp_dir.joinpath(submission_file.question_file.filename))
            recursive_chmod(temp_dir)
            completed_process = run_process(
                [
                    'sudo',
                    '-u', 'nobody',
                    'timeout',
                    '-s', 'KILL',
                    str(result.question.timeout_seconds), str(temp_dir.joinpath('.script')),
                ],
                cwd=temp_dir,
                stderr=PIPE,
                stdout=PIPE,
                check=False,
            )
            stdout = completed_process.stdout.decode('utf-8')[:2**16]
            stderr = completed_process.stderr.decode('utf-8')[:2**16]
            return_code = completed_process.returncode
            if return_code == -9: # from timeout
                stderr += '\n\n'
                stderr += f'The program failed to complete within {result.question.timeout_seconds} seconds and was terminated.'
                stderr = stderr.strip()
            # Some programs (eg. Python) writes to directory (eg. __pycache__),
            # but with the permissions of the executing user (in this case,
            # nobody). This subprocess cleans all of that up.
            completed_process = run_process(
                ['sudo', '-u', 'nobody', 'rm', '-rf', *temp_dir.iterdir()],
                cwd=temp_dir,
                check=False,
            )
        result = db.session.scalar(select(Result).where(Result.id == result_id))
        result.stdout = stdout.strip()
        result.stderr = stderr.strip()
        result.return_code = return_code
        db.session.add(result)
        db.session.commit()
