from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from sqlalchemy.orm import validates

db = SQLAlchemy()


class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    preferred_name = db.Column(db.String, nullable=False)
    family_name = db.Column(db.String, nullable=False)
    email = db.Column(db.String, nullable=False, unique=True, index=True)
    admin = db.Column(db.Boolean, nullable=False, default=False)
    faculty = db.Column(db.Boolean, nullable=False, default=False)
    logged_in = db.Column(db.Boolean, nullable=False, default=False) 
    submissions = db.relationship('Submission', backref='user')

    def __str__(self):
        return f'{self.full_name} <{self.email}>'

    @property
    def full_name(self):
        return f'{self.preferred_name} {self.family_name}'

    def latest_submission(self, question=None):
        pass # TODO

    def may_submit(self, question):
        pass # TODO

    def get_id(self):
        # this method is required by flask-login
        return self.email


class Instructor(db.Model):
    __tablename__ = 'instructors'
    __table_args__ = (
        db.UniqueConstraint('user_id', 'course_id'),
    )
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)


class Student(db.Model):
    __tablename__ = 'students'
    __table_args__ = (
        db.UniqueConstraint('user_id', 'course_id'),
    )
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)


class Course(db.Model):
    __tablename__ = 'courses'
    __table_args__ = (
        db.UniqueConstraint('season', 'year', 'department_code', 'number', 'section'),
    )
    id = db.Column(db.Integer, primary_key=True)
    season = db.Column(db.Enum('Fall', 'Winter', 'Spring', 'Summer'), nullable=False)
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


class Assignment(db.Model):
    __tablename__ = 'assignments'
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    name = db.Column(db.String, nullable=False)
    due_date = db.Column(db.DateTime, nullable=True)
    questions = db.relationship('Question', backref='assignment')


class QuestionDependency(db.Model):
    __tablename__ = 'question_dependencies'
    __table_args__ = (
        db.UniqueConstraint('producer_id', 'consumer_id'),
    )
    id = db.Column(db.Integer, primary_key=True)
    producer_id = db.Column(db.Integer, db.ForeignKey('questions.id'), nullable=False)
    consumer_id = db.Column(db.Integer, db.ForeignKey('questions.id'), nullable=False)
    input_type = db.Column(db.Enum('all', 'latest'), nullable=False) # TODO default value
    submitters = db.Column(db.Enum('instructors', 'everyone'), nullable=False) # TODO default value
    viewable = db.Column(db.Boolean, default=True)


class Question(db.Model):
    __tablename__ = 'questions'
    id = db.Column(db.Integer, primary_key=True)
    assignment_id = db.Column(db.Integer, db.ForeignKey('assignments.id'), nullable=False)
    cooldown_seconds = db.Column(db.Integer, default=10)
    timeout_seconds = db.Column(db.Integer, default=10)
    hide_output = db.Column(db.Boolean, default=False)
    visible = db.Column(db.Boolean, default=False)
    locked = db.Column(db.Boolean, default=False)
    files = db.relationship('QuestionFile', backref='question')
    submission = db.relationship('Submission', backref='question')
    consumes = db.relationship(
        'User',
        secondary='question_dependencies',
        primaryjoin=(id == QuestionDependency.consumer_id),
        secondaryjoin=(id == QuestionDependency.producer_id),
        backref='consumed_by',
    )


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
    timestamp = db.Column(db.DateTime, nullable=False)
    uploads = db.relationship('Upload', backref='submission')
    results = db.relationship('Result', backref='submission')
    dependent_results = db.relationship(
        'Result',
        secondary='result_dependencies',
        backref='depends_on',
    )

    @property
    def submitter(self):
        return self.user


class Upload(db.Model):
    __tablename__ = 'uploads'
    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(db.Integer, db.ForeignKey('submissions.id'), nullable=False)
    filepath = db.Column(db.String, nullable=False)

    @property
    def submitter(self):
        return self.submission.user


class Result(db.Model):
    __tablename__ = 'results'
    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(db.Integer, db.ForeignKey('submissions.id'), nullable=False)

    @property
    def submitter(self):
        return self.submission.user


class ResultDependency(db.Model):
    __tablename__ = 'result_dependencies'
    __table_args__ = (
        db.UniqueConstraint('result_id', 'submission_id'),
    )
    id = db.Column(db.Integer, primary_key=True)
    result_id = db.Column(db.Integer, db.ForeignKey('results.id'), nullable=False)
    submission_id = db.Column(db.Integer, db.ForeignKey('submissions.id'), nullable=False)
