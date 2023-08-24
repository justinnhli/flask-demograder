from datetime import datetime as DateTime

from sqlalchemy import select
from flask_wtf import FlaskForm
from flask_wtf.file import FileField
from wtforms import Form
from wtforms import HiddenField, SubmitField, BooleanField,  DecimalField, StringField, TextAreaField
from wtforms import SelectField, SelectMultipleField, DateField, FieldList, FormField
from wtforms.widgets import ListWidget, CheckboxInput
from wtforms.validators import ValidationError, InputRequired, Regexp, Optional

from .models import db, SEASONS, User, Course, Assignment, Question, QuestionDependency


class MultiCheckboxField(SelectMultipleField):
    widget = ListWidget(prefix_label=False)
    option_widget = CheckboxInput()


def unique(cls, fields):

    if len(fields) == 1:
        message = f'A {cls.__name__} already exists with this {fields[0]}'
    else:
        fields_string = f'{", ".join(fields[:-1])}  and {fields[-1]}'
        message = f'A {cls.__name__} already exists with this {fields_string}'

    def uniqueness_check(form, form_field):
        filters = {
            field: getattr(form, field).data
            for field in fields
        }
        instance = cls.query.filter_by(**filters).first() # FIXME convert to SQLAlchemy 2 syntax
        if instance and instance.id != int(form.id.data):
            getattr(form, form_field.id).errors.append(message)
            return False
        return True

    return uniqueness_check


class UserForm(FlaskForm):
    id = HiddenField('id')
    preferred_name = StringField('Preferred Name')
    family_name = StringField('Family Name')
    email = StringField(
        'Email',
        validators=[
            InputRequired(),
            Regexp(
                r'^[\w.+-]+@[\w-]+(\.[\w-]+)+$',
                message='Please enter a valid email address',
            ),
            unique(User, ['email']),
        ],
        render_kw={},
    )
    admin = BooleanField('Admin')
    faculty = BooleanField('Faculty')
    submit = SubmitField('Submit')

    def update_for(self, user_id, context):
        user = db.session.scalar(select(User).where(User.id == user_id))
        self.id.data = user.id
        self.preferred_name.data = user.preferred_name
        self.family_name.data = user.family_name
        self.email.data = user.email
        self.admin.data = user.admin
        self.faculty.data = user.faculty
        # disable the email field for non-admins
        if context['role'] < context['Role'].ADMIN:
            self.email.render_kw['readonly'] = ''

    @staticmethod
    def build(context):
        return UserForm()


class CourseForm(FlaskForm):
    id = HiddenField('id')
    season = SelectField('Season', choices=SEASONS)
    year = DecimalField('Year', places=0, default=DateTime.now().year)
    department_code = StringField('Department Code', default='COMP', validators=[InputRequired()])
    number = DecimalField('Course Number', places=0, validators=[InputRequired()])
    section = DecimalField('Section', places=0, default=0) # FIXME uniqueness check
    title = StringField('Title', validators=[InputRequired()])
    instructors = TextAreaField(
        'Instructors',
        description='Instructors and teaching assistants for the course. Everything accept their emails will be ignored.',
    )
    students = TextAreaField(
        'Students',
        description='Students enrolled in the course. Everything accept their emails will be ignored.',
    )
    submit = SubmitField('Submit')

    def update_for(self, course_id, context):
        course = db.session.scalar(select(Course).where(Course.id == course_id))
        self.id.data = course.id
        self.season.data = course.season
        self.year.data = int(course.year)
        self.department_code.data = course.department_code
        self.number.data = int(course.number)
        self.section.data = int(course.section)
        self.title.data = course.title
        self.instructors.data = '\n'.join(str(user) for user in sorted(course.instructors))
        self.students.data = '\n'.join(str(user) for user in sorted(course.students))

    @staticmethod
    def build(context):
        return CourseForm()


class AssignmentForm(FlaskForm):
    id = HiddenField('id')
    course_id = HiddenField('course_id')
    course = StringField('Course', render_kw={'readonly':''})
    name = StringField('Name',  validators=[InputRequired()])
    submit = SubmitField('Submit')

    def update_for(self, assignment_id, context):
        assignment = db.session.scalar(select(Assignment).where(Assignment.id == assignment_id))
        self.id.data = assignment_id
        self.name.data = assignment.name

    @staticmethod
    def build(context):
        form = AssignmentForm()
        form.course_id.data = context['course'].id
        form.course.data = str(context['course'])
        return form


class QuestionDependencyForm(Form):
    question_id = HiddenField('question_id')
    question = StringField('question')
    is_dependency = BooleanField(default=False)
    submissions_used = SelectField('Submissions Used', choices=['all', 'latest'])
    submitters_used = SelectField('Submitters Used', choices=['instructors', 'students', 'everyone'])
    viewable = BooleanField('source file viewable')


class QuestionForm(FlaskForm):
    id = HiddenField('id')
    assignment_id = HiddenField('assignment_id')
    course = StringField('Course', render_kw={'readonly':''})
    assignment = StringField('Assignment', render_kw={'readonly':''})
    name = StringField('Name',  validators=[InputRequired()])
    due_date = DateField('Due Date', validators=[Optional()])
    due_hour = SelectField(choices=[f'{hour:02d}' for hour in range(24)])
    due_minute = SelectField(choices=[f'{minute:02d}' for minute in range(60)])
    cooldown = DecimalField(
        'Cooldown (sec)', places=0, default=300,
        description='How long students have to wait before they can resubmit to a question.',
    )
    timeout = DecimalField(
        'Timeout (sec)', places=0, default=10,
        description='How long student code is allowed to run before it is killed.',
    )
    visible = BooleanField(
        'Visible',
        description='If visible, students will not be able to see or access this question.',
    )
    locked = BooleanField(
        'Locked',
        description='If locked, students will not be able to submit to this question.',
    )
    hide_output = BooleanField(
        'Hide Output',
        description='If the output is hidden, students will only see whether a testcase passed/failed, but not any printed output or errors.',
    )
    dependencies = FieldList(
        FormField(QuestionDependencyForm),
        description='Other questions whose submissions are needed for the evaluation of this question.',
    )
    # cannot be "filenames" due to namespace collision in WTForm
    file_names = StringField(
        'Filenames',
        description='The filenames to be submitted, separated by commas.',
    )
    script = TextAreaField(
        'Script',
        default='#!/bin/sh\n\nexit 1 # FIXME',
        description='The script to run to evaluate submissions to this question.',
    )
    submit = SubmitField('Submit')

    def update_for(self, question_id, context):
        question = db.session.scalar(select(Question).where(Question.id == question_id))
        self.id.data = question_id
        self.name.data = question.name
        if question.due_date:
            self.due_date.data = question.due_date
            self.due_hour.data = f'{question.due_date.hour:02d}'
            self.due_minute.data = f'{question.due_date.minute:02d}'
        self.cooldown.data = question.cooldown_seconds
        self.timeout.data = question.timeout_seconds
        self.visible.data = question.visible
        self.locked.data = question.locked
        self.hide_output.data = question.hide_output
        other_questions = []
        for assignment in question.assignment.course.assignments:
            other_questions.extend(assignment.questions)
        other_questions = [
            other_question for other_question in other_questions
            if other_question.id != question.id
        ]
        for other_question in other_questions:
            question_dependency = db.session.scalar(
                select(QuestionDependency)
                .where(
                    QuestionDependency.producer_id == other_question.id,
                    QuestionDependency.consumer_id == question.id,
                )
            )
            if question_dependency:
                self.dependencies.append_entry({
                    'question_id': other_question.id,
                    'question': other_question.name,
                    'is_dependency': True,
                    'submissions_used': question_dependency.input_type,
                    'submitters_used': question_dependency.submitters,
                    'viewable': question_dependency.viewable,
                })
            else:
                self.dependencies.append_entry({
                    'question_id': other_question.id,
                    'question': other_question.name,
                    'submissions_used': 'all',
                    'submitters_used': 'instructor',
                    'viewable': True,
                })
        self.file_names.data = ','.join(question_file.filename for question_file in question.filenames)
        self.script.data = question.script

    @staticmethod
    def build(context):
        form = QuestionForm()
        form.assignment_id.data = context['assignment'].id
        form.course.data = str(context['course'])
        form.assignment.data = str(context['assignment'])
        return form

    def validate_file_names(self, field):
        filenames = [filename.strip() for filename in field.data.split(',')]
        if len(filenames) != len(set(filenames)):
            raise ValidationError('filenames must be unique')


class FileSubmissionForm(Form):
    question_file_id = HiddenField('question_file_id')
    filename = HiddenField('filename')
    file = FileField('file')


class SubmissionForm(FlaskForm):
    question_id = HiddenField('question_id')
    submission_files = FieldList(FormField(FileSubmissionForm))
    submit = SubmitField('Submit')

    def update_for(self, question_id, context):
        question = db.session.scalar(select(Question).where(Question.id == question_id))
        self.question_id.data = question_id
        for question_file in question.filenames:
            self.submission_files.append_entry({
                'question_file_id': question_file.id,
                'filename': question_file.filename,
            })

    @staticmethod
    def build(context):
        return SubmissionForm()
