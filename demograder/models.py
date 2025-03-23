from datetime import datetime as DateTime
from enum import IntEnum
from itertools import product
from textwrap import dedent

from flask import current_app
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from sqlalchemy import select, case, func, or_
from sqlalchemy.orm import aliased, validates

db = SQLAlchemy()


class SiteRole(IntEnum):
    """A class representing the site role of the viewer.

    This exists to allow dynamically checking what the page looks like for different people.
    """
    STUDENT = 0
    FACULTY = 1
    ADMIN = 2


class CourseRole(IntEnum):
    """A class representing the course role of the viewer.

    This exists to allow dynamically checking what the page looks like for different people.
    """
    STUDENT = 0
    INSTRUCTOR = 1


class User(db.Model, UserMixin):
    __tablename__ = 'users'
    __table_args__ = (
        db.Index('ix_users_family_name_preferred_name', 'family_name', 'preferred_name'),
    )
    id = db.Column(db.Integer, primary_key=True)
    preferred_name = db.Column(db.String, nullable=False, default='')
    family_name = db.Column(db.String, nullable=False, default='')
    email = db.Column(db.String, nullable=False, unique=True, index=True)
    admin = db.Column(db.Boolean, nullable=False, default=False)
    faculty = db.Column(db.Boolean, nullable=False, default=False)
    logged_in = db.Column(db.Boolean, nullable=False, default=False)

    def __lt__(self, other):
        return (
            (self.family_name, self.preferred_name, self.email)
            < (other.family_name, other.preferred_name, other.email)
        )

    def __str__(self):
        return f'{self.full_name} <{self.email}>'

    @property
    def has_full_name(self):
        return self.preferred_name and self.family_name

    @property
    def full_name(self):
        return f'{self.preferred_name} {self.family_name}'

    def is_teaching(self, course_id):
        return any(course.id == course_id for course in self.courses_teaching)

    def is_taking(self, course_id):
        return any(course.id == course_id for course in self.courses_taking)

    def get_id(self):
        # this method is required by flask-login
        return self.email

    def courses(self):
        return db.session.scalars(
            select(Course)
            .where(or_(
                (
                    select(Instructor).
                    where(Instructor.user_id == self.id, Instructor.course_id == Course.id)
                    .exists()
                ),
                (
                    select(Student).
                    where(Student.user_id == self.id, Student.course_id == Course.id)
                    .exists()
                ),
            ))
            .order_by(
                Course.year.desc(),
                SEASONS_ORDER_BY.desc(),
                Course.department_code.asc(),
                Course.number.asc(),
                Course.section.asc(),
            )
        )

    def courses_with_student(self, student_id):
        # return courses that the user teaches and the student is enrolled
        return db.session.scalars(
            select(Course)
            .join(Instructor)
            .where(Instructor.user_id == self.id)
            .join(Student)
            .where(Student.user_id == student_id)
        )

    def courses_with_coinstructor(self, user_id):
        # return courses that the user teaches and the other user is also an instructor
        # FIXME change to SQLAlchemy 2 syntax
        # problem is this uses Instructor twice; will likely need an alias here
        return Course.query.join(
            Instructor.query.filter_by(user_id=self.id).subquery()
        ).join(
            Instructor.query.filter_by(user_id=user_id).subquery()
        )

    def submissions_from_students(self, include_hidden=False, include_disabled=False, limit=None):
        statement = (
            select(Submission)
            .where(Submission.disabled == include_disabled)
            .join(Question)
            .where(Question.visible == (not include_hidden))
            .join(Assignment)
            .join(Course)
            .join(Instructor)
            .where(Instructor.user_id == self.id)
            .order_by(Submission.timestamp.desc())
        )
        if limit is None:
            return db.session.scalars(statement)
        else:
            return db.session.scalars(statement.limit(limit))

    def submissions(self, include_hidden=False, include_disabled=False, before=None, limit=None):
        statement = select(Submission).where(Submission.user_id == self.id)
        if before:
            statement = statement.where(Submission.timestamp <= before)
        if not include_disabled:
            statement = statement.where(Submission.disabled == False)
        if not include_hidden:
            statement = (
                statement
                .join(Question)
                .where(Question.visible == True)
            )
        statement = statement.order_by(Submission.timestamp.desc())
        if limit is None:
            return db.session.scalars(statement)
        else:
            return db.session.scalars(statement.limit(limit))

    def may_submit(self, question_id):
        """Determine if a user is allowed to submit to a project.

        The motivation behind stopping student submissions is to prevent
        overloading the system, and (in theory) to instill a more thorough
        manual debugging process. There are three trivial cases when a user can
        submit:

        * they are a superuser
        * they are the instructor for the course
        * they have not submitted to this project before

        If they are not the instructor and have previous submissions, then all
        of the following must be true for the student to submit:

        * the project is not locked
        * all their previous submissions for this project have finished running
        * the cooldown has not passed since their last submission to a question
        """
        question = db.session.get(Question, question_id)
        if self.admin or self.is_teaching(question.course.id):
            return True
        if question.locked:
            return False
        latest_submission = question.submissions(user_id=self.id, limit=1).first()
        if not latest_submission:
            return True
        if latest_submission.num_tbd > 0:
            return False
        current_time = DateTime.now()
        submit_time = latest_submission.timestamp
        return (current_time - submit_time).seconds > question.cooldown_seconds

    def may_view_file(self, submission_file_id):
        """Determine if a user is allowed to view a file.

        Beyond the trivial case where the user is the instructor for the course,
        a user can see a submission file only if both of the following are true:

        * the file is from a submission used in a result for the student
        * the question dependency allows viewing that upstream submission
        """
        submission_file = db.session.get(SubmissionFile, submission_file_id)
        if self.is_teaching(submission_file.course.id):
            return True
        if self == submission_file.submitter:
            return True
        producer_alias = aliased(Question)
        consumer_alias = aliased(Question)
        consumer_submissions_alias = aliased(Submission)
        return bool(db.session.scalar(
            select(QuestionDependency)
            .distinct()
            .where(QuestionDependency.viewable == True)
            .join(producer_alias, QuestionDependency.producer)
            .join(producer_alias.all_submissions)
            .join(SubmissionFile)
            .where(SubmissionFile.id == submission_file_id)
            .join(consumer_alias, QuestionDependency.consumer)
            .join(consumer_submissions_alias, consumer_alias.all_submissions)
            .where(consumer_submissions_alias.user_id == self.id)
        ))

    @staticmethod
    def get_by_email(email):
        return db.session.scalar(select(User).where(User.email == email))


class Instructor(db.Model):
    __tablename__ = 'instructors'
    __table_args__ = (
        db.UniqueConstraint('user_id', 'course_id'),
    )
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False, index=True)


class Student(db.Model):
    __tablename__ = 'students'
    __table_args__ = (
        db.UniqueConstraint('user_id', 'course_id'),
    )
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False, index=True)


SEASONS = ['Fall', 'Winter', 'Spring', 'Summer']
SEASONS_ORDER_MAP = {season: index for index, season in enumerate(SEASONS)}


class Course(db.Model):
    __tablename__ = 'courses'
    __table_args__ = (
        db.UniqueConstraint('season', 'year', 'department_code', 'number', 'section'),
    )
    id = db.Column(db.Integer, primary_key=True)
    season = db.Column(db.Enum(*SEASONS), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    department_code = db.Column(db.String, nullable=False)
    number = db.Column(db.String, nullable=False)
    section = db.Column(db.Integer, nullable=False, default=0)
    title = db.Column(db.String, nullable=False)
    instructors = db.relationship(
        'User',
        secondary='instructors',
        backref='courses_teaching',
    )
    students = db.relationship(
        'User',
        secondary='students',
        backref='courses_taking',
    )

    @validates('department_code')
    def upper(self, key, value):
        return value.upper()

    def __str__(self):
        return ' '.join(str(part) for part in [
            self.season.title(),
            self.year,
            self.department_code.upper(),
            self.number,
            self.section,
        ])

    @property
    def anchorable_id(self):
        return str(self).replace(' ', '_')

    @property
    def semester(self):
        return f'{self.season} {self.year}'

    @property
    def course_number(self):
        if self.section == 0:
            return f'{self.department_code} {self.number}'
        else:
            return f'{self.department_code} {self.number} {self.section}'

    def assignments(self, include_hidden=False):
        assignments = db.session.scalars(
            select(Assignment)
            .where(Assignment.course_id == self.id)
        )
        return sorted(
            (assignment for assignment in assignments if include_hidden or assignment.visible),
            key=(lambda assignment: assignment.due_date),
            reverse=True,
        )

    def submissions(self, user_id=None, include_hidden=False, include_disabled=False, before=None, limit=None):
        statement = select(Submission)
        if user_id:
            statement = statement.where(Submission.user_id == user_id)
        if before:
            statement = statement.where(Submission.timestamp <= before)
        if not include_disabled:
            statement = statement.where(Submission.disabled == False)
        statement = statement.join(Question)
        if not include_hidden:
            statement = statement.where(Question.visible == True)
        statement = (
            statement
            .join(Assignment)
            .join(Course)
            .where(Course.id == self.id)
            .order_by(Submission.timestamp.desc())
        )
        if limit is None:
            return db.session.scalars(statement)
        else:
            return db.session.scalars(statement.limit(limit))


SEASONS_ORDER_BY = case(SEASONS_ORDER_MAP, value=Course.season)


class Assignment(db.Model):
    __tablename__ = 'assignments'
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False, index=True)
    name = db.Column(db.String, nullable=False, default='')
    course = db.relationship('Course')

    def __str__(self):
        return self.name

    @property
    def visible(self):
        return any(question.visible for question in self.questions(include_hidden=True))

    @property
    def due_date(self):
        return max(
            (question.due_date for question in self.questions() if question.visible),
            default=DateTime.now(),
        )

    def questions(self, include_hidden=False):
        statement = select(Question).where(Question.assignment_id == self.id)
        if not include_hidden:
            statement = statement.where(Question.visible == True)
        statement = statement.order_by(
            Question.visible.desc(),
            Question.due_date.desc(),
            Question.name.asc(),
        )
        return db.session.scalars(statement)

    def submissions(self, user_id=None, include_hidden=False, include_disabled=False, before=None, limit=None):
        statement = select(Submission)
        if user_id:
            statement = statement.where(Submission.user_id == user_id)
        if before:
            statement = statement.where(Submission.timestamp <= before)
        if not include_disabled:
            statement = statement.where(Submission.disabled == False)
        statement = statement.join(Question)
        if not include_hidden:
            statement = statement.where(Question.visible == True)
        statement = (
            statement
            .join(Assignment)
            .where(Assignment.id == self.id)
            .order_by(Submission.timestamp.desc())
        )
        if limit is None:
            return db.session.scalars(statement)
        else:
            return db.session.scalars(statement.limit(limit))


class QuestionDependency(db.Model):
    __tablename__ = 'question_dependencies'
    __table_args__ = (
        db.UniqueConstraint('producer_id', 'consumer_id'),
    )
    id = db.Column(db.Integer, primary_key=True)
    producer_id = db.Column(db.Integer, db.ForeignKey('questions.id'), nullable=False, index=True)
    consumer_id = db.Column(db.Integer, db.ForeignKey('questions.id'), nullable=False, index=True)
    input_type = db.Column(db.Enum('latest', 'all'), nullable=False, default='latest')
    submitters = db.Column(db.Enum('instructors', 'students', 'everyone'), nullable=False, default='instructor')
    viewable = db.Column(db.Boolean, default=True)


class Question(db.Model):
    __tablename__ = 'questions'
    __table_args__ = (
        db.Index('ix_questions_assignment_id_due_date_visible', 'assignment_id', 'visible', 'due_date'),
    )
    id = db.Column(db.Integer, primary_key=True)
    assignment_id = db.Column(db.Integer, db.ForeignKey('assignments.id'), nullable=False, index=True)
    name = db.Column(db.String, nullable=False, default='')
    due_date = db.Column(db.DateTime, nullable=True)
    cooldown_seconds = db.Column(db.Integer, default=300)
    timeout_seconds = db.Column(db.Integer, default=10)
    visible = db.Column(db.Boolean, default=False)
    locked = db.Column(db.Boolean, default=False)
    allow_disable = db.Column(db.Boolean, default=False)
    hide_output = db.Column(db.Boolean, default=False)
    script = db.Column(db.String, nullable=False, default=dedent('''
        #!/bin/bash

        exit 1 # FIXME
    ''').strip())
    assignment = db.relationship('Assignment')
    filenames = db.relationship('QuestionFile', backref='question')
    upstream_dependencies = db.relationship(
        'QuestionDependency',
        foreign_keys=QuestionDependency.consumer_id,
        backref='consumer',
    )
    downstream_dependencies = db.relationship(
        'QuestionDependency',
        foreign_keys=QuestionDependency.producer_id,
        backref='producer',
    )
    # The lack of direct "consumes"/"consumed_by" relationships is deliberate.
    # SQLAlchemy calls relationships like QuestionDependency "association
    # objects", as they contain additional information beyond the IDs of what is
    # being linked. Having `relationship()`s with both the _association_ objects
    # and the _associated_ objects can lead to race conditions, and the intended
    # solution is too much of a pain to implement. For details, see
    # https://docs.sqlalchemy.org/en/14/orm/basic_relationships.html#association-object

    def __str__(self):
        if self.due_date:
            return f'{self.name} ({self.due_date})'
        else:
            return self.name

    @property
    def iso_format(self):
        return self.due_date.strftime('%Y-%m-%d %H:%M')

    @property
    def course(self):
        return self.assignment.course

    @property
    def upstream_submission_id_sets(self):
        permute_args = []
        for dependency in self.upstream_dependencies:
            statement = (
                select(Submission)
                .where(Submission.question_id == dependency.producer_id)
                .where(Submission.disabled == False)
                .join(User)
            )
            if dependency.submitters == 'everyone':
                statement = (
                    statement
                    .where(or_(
                        (
                            select(Instructor).
                            where(
                                Instructor.user_id == User.id,
                                Instructor.course_id == self.course.id,
                            )
                            .exists()
                        ),
                        (
                            select(Student).
                            where(
                                Student.user_id == User.id,
                                Student.course_id == self.course.id,
                            )
                            .exists()
                        ),
                    ))
                )
            elif dependency.submitters == 'students':
                statement = (
                    statement
                    .join(Student)
                    .where(Student.course_id == self.course.id)
                )
            elif dependency.submitters == 'instructors':
                statement = (
                    statement
                    .join(Instructor)
                    .where(Instructor.course_id == self.course.id)
                )
            else:
                assert False
            if dependency.input_type == 'all':
                pass # no need to filter if all submissions are used
            elif dependency.input_type == 'latest':
                statement = (
                    statement
                    .group_by(User.id)
                    .order_by(func.max(Submission.timestamp).desc())
                )
            else:
                assert False
            submissions = db.session.scalars(statement)
            permute_args.append(list(submission.id for submission in submissions))
        if permute_args:
            return list(product(*permute_args))
        else:
            return []

    def most_recent_submission(self, user_id):
        return db.session.scalar(
            select(Submission)
            .where(
                Submission.question_id == self.id,
                Submission.user_id == user_id,
            )
            .order_by(Submission.timestamp.desc())
        )

    def submissions(self, user_id=None, include_hidden=False, include_disabled=False, before=None, limit=None):
        statement = select(Submission).where(Submission.question_id == self.id)
        if user_id:
            statement = statement.where(Submission.user_id == user_id)
        if before:
            statement = statement.where(Submission.timestamp <= before)
        if not include_disabled:
            statement = statement.where(Submission.disabled == False)
        if not include_hidden:
            statement = (
                statement
                .join(Question)
                .where(Question.visible == True)
            )
        statement = statement.order_by(Submission.timestamp.desc())
        if limit is None:
            return db.session.scalars(statement)
        else:
            return db.session.scalars(statement.limit(limit))


class QuestionFile(db.Model):
    __tablename__ = 'question_files'
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id'), nullable=False, index=True)
    filename = db.Column(db.String, nullable=True)


class Submission(db.Model):
    __tablename__ = 'submissions'
    __table_args__ = (
        # for site-level submissions page
        db.Index('ix_submissions_timestamp', 'timestamp'),
        # for user page, group by the user_id
        db.Index('ix_submissions_user_id_question_id_timestamp', 'user_id', 'question_id', 'timestamp'),
        # for user submissions page, group by the user_id
        db.Index('ix_submissions_user_id_timestamp', 'user_id', 'timestamp'),
        # for course/assignment/question-level submissions page (which will ignore the user_id)
        # and for evaluation (which uses the user_id)
        db.Index('ix_submissions_question_id_disabled_user_id_timestamp', 'question_id', 'disabled', 'user_id', 'timestamp'),
    )
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id'), nullable=False, index=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=(lambda: DateTime.now()))
    disabled = db.Column(db.Boolean, nullable=False, default=False)
    files = db.relationship('SubmissionFile', backref='submission')
    results = db.relationship('Result', backref='submission')
    user = db.relationship('User')
    question = db.relationship('Question', backref='all_submissions')

    @property
    def num_results(self):
        return db.session.scalar(
            select(func.count(Result.id))
            .where(Result.submission_id == self.id)
        )

    @property
    def num_passed(self):
        return db.session.scalar(
            select(func.count(Result.id))
            .where(Result.submission_id == self.id, Result.return_code == 0)
        )

    @property
    def num_failed(self):
        return db.session.scalar(
            select(func.count(Result.id))
            .where(Result.submission_id == self.id, Result.return_code != 0)
        )

    @property
    def num_tbd(self):
        return db.session.scalar(
            select(func.count(Result.id))
            .where(Result.submission_id == self.id, Result.return_code.is_(None))
        )

    @property
    def files_str(self):
        return ', '.join(file.filename for file in self.files)

    @property
    def submitter(self):
        return self.user

    @property
    def iso_format(self):
        return self.timestamp.strftime('%Y-%m-%d %H:%M:%S')

    @property
    def assignment(self):
        return self.question.assignment

    @property
    def course(self):
        return self.question.course


class SubmissionFile(db.Model):
    __tablename__ = 'submission_files'
    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(db.Integer, db.ForeignKey('submissions.id'), nullable=False, index=True)
    question_file_id = db.Column(db.Integer, db.ForeignKey('question_files.id'), nullable=False)
    question_file = db.relationship('QuestionFile')
    filename = db.Column(db.String, nullable=False)

    @property
    def submitter(self):
        return self.submission.submitter

    @property
    def question(self):
        return self.submission.question

    @property
    def assignment(self):
        return self.submission.assignment

    @property
    def course(self):
        return self.submission.course

    @property
    def filepath(self):
        suffix = f'{self.course.id}/{self.assignment.id}/{self.submission.id}/{self.filename}'
        return current_app.config['SUBMISSION_PATH'].joinpath(suffix)

    @property
    def contents(self):
        with self.filepath.open() as fd:
            return fd.read()


class Result(db.Model):
    __tablename__ = 'results'
    __table_args__ = (
        db.Index('ix_results_submission_id_return_code', 'submission_id', 'return_code'),
    )
    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(db.Integer, db.ForeignKey('submissions.id'), nullable=False, index=True)
    stdout = db.Column(db.String, nullable=True)
    stderr = db.Column(db.String, nullable=True)
    return_code = db.Column(db.Integer, nullable=True)
    upstream_submissions = db.relationship(
        'Submission',
        secondary='result_dependencies',
        backref='result',
    )

    @property
    def submitter(self):
        return self.submission.user

    @property
    def dependent_files(self):
        result = []
        for submission in self.upstream_submissions:
            result.extend(submission.files)
        return result

    def question_dependency(self, question_id):
        return db.session.scalar(
            select(QuestionDependency)
            .where(
                QuestionDependency.producer_id == question_id,
                QuestionDependency.consumer_id == self.question.id,
            )
        )

    @property
    def question(self):
        return self.submission.question

    @property
    def assignment(self):
        return self.submission.assignment

    @property
    def course(self):
        return self.submission.course

    @property
    def is_tbd(self):
        return self.return_code is None

    @property
    def passed(self):
        return self.return_code == 0

    @property
    def failed(self):
        return not self.is_tbd and not self.passed


class ResultDependency(db.Model):
    __tablename__ = 'result_dependencies'
    __table_args__ = (
        db.UniqueConstraint('result_id', 'submission_id'),
    )
    id = db.Column(db.Integer, primary_key=True)
    result_id = db.Column(db.Integer, db.ForeignKey('results.id'), nullable=False, index=True)
    submission_id = db.Column(db.Integer, db.ForeignKey('submissions.id'), nullable=False)
