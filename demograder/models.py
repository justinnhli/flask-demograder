from datetime import datetime as DateTime
from textwrap import dedent

from flask import current_app
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from sqlalchemy import case as case_
from sqlalchemy.orm import validates

db = SQLAlchemy()


class User(db.Model, UserMixin):
    __tablename__ = 'users'
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
    def full_name(self):
        return f'{self.preferred_name} {self.family_name}'

    def is_teaching(self, course_id):
        return bool(Instructor.query.filter_by(user_id=self.id, course_id=course_id).first())

    def is_taking(self, course_id):
        return bool(Student.query.filter_by(user_id=self.id, course_id=course_id).first())

    def may_submit(self, question_id):
        """Determines if a user is allowed to submit to a project.

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
        question = Question.query.get(question_id)
        if self.admin or self.is_teaching(question.course.id):
            return True
        if question.locked:
            return False
        last_submission = self.question_submissions(question_id, limit=1).first()
        if not last_submission:
            return True
        if last_submission.num_tbd > 0:
            return False
        current_time = UTC.normalize(datetime.now(last_submission.timestamp.tzinfo)) # FIXME
        submit_time = UTC.normalize(last_submission.timestamp) # FIXME
        return (current_time - submit_time).seconds > question.cooldown_seconds

    def get_id(self):
        # this method is required by flask-login
        return self.email

    def courses(self):
        return Course.query.join(
            Student.query.filter_by(user_id=self.id).union(
                Instructor.query.filter_by(user_id=self.id)
            ).subquery()
        ).order_by(
            Course.year.desc(),
            SEASONS_ORDER_BY.desc(),
            Course.department_code.asc(),
            Course.number.asc(),
            Course.section.asc(),
        )

    def courses_taking(self):
        return Course.query.join(
            Student.query.filter_by(user_id=self.id).subquery()
        )

    def courses_teaching(self):
        return Course.query.join(
            Instructor.query.filter_by(user_id=self.id).subquery()
        )

    def courses_with_student(self, user):
        # return courses that the user teaches and the student is enrolled
        return Course.query.join(
            Instructor.query.filter_by(user_id=self.id).subquery()
        ).join(
            Student.query.filter_by(user_id=user.id).subquery()
        )

    def courses_with_coinstructor(self, user):
        # return courses that the user teaches and the other user is also an instructor
        return Course.query.join(
            Instructor.query.filter_by(user_id=self.id).subquery()
        ).join(
            Instructor.query.filter_by(user_id=user.id).subquery()
        )

    def latest_submission(self, question_id):
        return self.question_submissions(question_id, limit=1).first()

    def question_submissions(self, question_id=None, limit=None):
        query = Submission.query.filter_by(user_id=self.id, question_id=question_id).order_by(Submission.timestamp.desc())
        if limit is None:
            return query
        else:
            return query.limit(limit)

    def course_submissions(self, course_id, limit=None):
        query = Submission.query.filter_by(user_id=self.id).join(Question).join(Assignment).join(
            Course.query.filter_by(id=course_id)
        ).order_by(Submission.timestamp.desc())
        if limit is None:
            return query
        else:
            return query.limit(limit)


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
    assignments = db.relationship(
        'Assignment',
        backref='course',
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

    @property
    def visible_assignments(self):
        return tuple(assignment for assignment in self.assignments if assignment.visible)

    def submissions(self, include_hidden=False, limit=None):
        if include_hidden:
            question_subquery = Question
        else:
            question_subquery = Question.query.filter_by(visible=True)
        query = Submission.query.filter_by(disabled=False).join(question_subquery).join(Assignment).join(
            Course.query.filter_by(id=self.id)
        ).order_by(Submission.timestamp.desc())
        if limit is None:
            return query
        else:
            return query.limit(limit)


SEASONS_ORDER_BY = case_(value=Course.season, whens=SEASONS_ORDER_MAP)


class Assignment(db.Model):
    __tablename__ = 'assignments'
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    name = db.Column(db.String, nullable=False, default='')
    questions = db.relationship('Question', backref='assignment')

    def __str__(self):
        return self.name

    @property
    def visible(self):
        return any(question.visible for question in self.questions)

    @property
    def visible_questions(self):
        return tuple(question for question in self.questions if question.visible)


class QuestionDependency(db.Model):
    __tablename__ = 'question_dependencies'
    __table_args__ = (
        db.UniqueConstraint('producer_id', 'consumer_id'),
    )
    id = db.Column(db.Integer, primary_key=True)
    producer_id = db.Column(db.Integer, db.ForeignKey('questions.id'), nullable=False)
    consumer_id = db.Column(db.Integer, db.ForeignKey('questions.id'), nullable=False)
    input_type = db.Column(db.Enum('latest', 'all'), nullable=False, default='latest')
    submitters = db.Column(db.Enum('everyone', 'instructors'), nullable=False, default='everyone')
    viewable = db.Column(db.Boolean, default=True)


class Question(db.Model):
    __tablename__ = 'questions'
    id = db.Column(db.Integer, primary_key=True)
    assignment_id = db.Column(db.Integer, db.ForeignKey('assignments.id'), nullable=False)
    name = db.Column(db.String, nullable=False, default='')
    due_date = db.Column(db.DateTime, nullable=True)
    cooldown_seconds = db.Column(db.Integer, default=10)
    timeout_seconds = db.Column(db.Integer, default=10)
    visible = db.Column(db.Boolean, default=False)
    locked = db.Column(db.Boolean, default=False)
    hide_output = db.Column(db.Boolean, default=False)
    script = db.Column(db.String, nullable=False, default=dedent('''
        #!/bin/bash

        exit 1 # FIXME
    ''').strip())
    filenames = db.relationship('QuestionFile', backref='question')
    submission = db.relationship('Submission', backref='question')
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
        return self.due_date.strftime('%Y-%m-%d %H:%M:%S')

    @property
    def course(self):
        return self.assignment.course


class QuestionFile(db.Model):
    __tablename__ = 'question_files'
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id'), nullable=False)
    filename = db.Column(db.String, nullable=True)


class Submission(db.Model):
    __tablename__ = 'submissions'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id'), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=DateTime.utcnow)
    disabled = db.Column(db.Boolean, nullable=False, default=False)
    files = db.relationship('SubmissionFile', backref='submission')
    results = db.relationship('Result', backref='submission')
    user = db.relationship('User')

    @property
    def num_results(self):
        return Result.query.filter_by(submission_id=self.id).count()

    @property
    def num_passed(self):
        return Result.query.filter_by(submission_id=self.id, return_code=0).count()

    @property
    def num_failed(self):
        return Result.query.filter_by(submission_id=self.id, return_code=1).count()

    @property
    def num_tbd(self):
        return Result.query.filter_by(submission_id=self.id, return_code=None).count()

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
    submission_id = db.Column(db.Integer, db.ForeignKey('submissions.id'), nullable=False)
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
    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(db.Integer, db.ForeignKey('submissions.id'), nullable=False)
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
        return QuestionDependency.query.filter_by(producer_id=question_id, consumer_id=self.question.id).first()

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
    result_id = db.Column(db.Integer, db.ForeignKey('results.id'), nullable=False)
    submission_id = db.Column(db.Integer, db.ForeignKey('submissions.id'), nullable=False)
