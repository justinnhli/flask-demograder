from werkzeug.datastructures import MultiDict
from flask_wtf import FlaskForm
from flask_wtf.file import FileField
from wtforms import BooleanField, DateField, DecimalField, FieldList, FormField, HiddenField, SelectField, SelectMultipleField, StringField, SubmitField, TextAreaField, Form
from wtforms.widgets import ListWidget, CheckboxInput
from wtforms.validators import ValidationError, InputRequired, Regexp, Optional

from .models import SEASONS, User, Course, Assignment, Question
from .models import QuestionDependency


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
        instance = cls.query.filter_by(**filters).first()
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
        user = User.query.get(user_id)
        self.id.data = user.id
        self.preferred_name.data = user.preferred_name
        self.family_name.data = user.family_name
        self.email.data = user.email
        self.admin.data = user.admin
        self.faculty.data = user.faculty
        # disable the email field for non-admins
        if context['role'] < context['Role'].ADMIN:
            self.email.render_kw['disabled'] = ''

    @staticmethod
    def build(context):
        return UserForm()


class CourseForm(FlaskForm):
    id = HiddenField('id')
    season = SelectField('Season', choices=SEASONS)
    year = DecimalField('Year', places=0)
    department_code = StringField( 'Department Code', default='COMP', validators=[InputRequired()])
    number = DecimalField('Course Number', places=0, validators=[InputRequired()])
    section = DecimalField('Section', places=0, default=0) # FIXME uniqueness check
    title = StringField('Title', validators=[InputRequired()])
    instructors = MultiCheckboxField('Instructors')
    enrolled_students = MultiCheckboxField('Enrolled Students')
    new_students = TextAreaField('New Students')
    submit = SubmitField('Submit')

    def update_for(self, course_id, context):
        course = Course.query.get(course_id)
        self.id.data = course.id
        self.season.data = course.season
        self.year.data = int(course.year)
        self.department_code.data = course.department_code
        self.number.data = int(course.number)
        self.section.data = int(course.section)
        self.title.data = course.title
        self.instructors.data = [str(user) for user in course.instructors]
        students = [str(user) for user in sorted(course.students)]
        self.enrolled_students.choices = students
        self.enrolled_students.data = students

    @staticmethod
    def build(context):
        form = CourseForm()
        form.instructors.choices = [
            str(user) for user in 
            User.query.filter_by(faculty=True).all()
        ]
        # FIXME set form.season.data by estimating semester
        # FIXME set form.year.data by estimating semester
        form.instructors.data = [str(context['viewer']),]
        form.enrolled_students.choices = []
        return form


class AssignmentForm(FlaskForm):
    id = HiddenField('id')
    course_id = HiddenField('course_id')
    course = StringField('Course', render_kw={})
    name = StringField( 'Name',  validators=[InputRequired()])
    submit = SubmitField('Submit')

    def update_for(self, assignment_id, context):
        assignment = Assignment.query.get(assignment_id)
        form.id.data = assignment_id
        self.name.data = assignment.name
        if assignment.due_date:
            self.due_date.data = assignment.due_date.date
            self.due_hour.data = f'{assignment.due_date.hour:02d}'
            self.due_minute.data = f'{assignment.due_date.minute:02d}'

    @staticmethod
    def build(context):
        form = AssignmentForm()
        form.course_id.data = context['course'].id
        form.course.data = str(context['course'])
        form.course.render_kw['disabled'] = ''
        return form


class QuestionDependencyForm(Form):
    question_id = HiddenField('question_id')
    question = StringField('question')
    is_dependency = BooleanField(default=False)
    submissions_used = SelectField('Submissions Used', choices=['all', 'latest'])
    viewable = BooleanField('source file viewable')


class QuestionForm(FlaskForm):
    id = HiddenField('id')
    assignment_id = HiddenField('assignment_id')
    course = StringField('Course', render_kw={})
    assignment = StringField('Assignment', render_kw={})
    name = StringField( 'Name',  validators=[InputRequired()])
    due_date = DateField( 'Due Date', validators=[Optional()])
    due_hour = SelectField(choices=[f'{hour:02d}' for hour in range(24)])
    due_minute = SelectField(choices=[f'{minute:02d}' for minute in range(60)])
    cooldown = DecimalField('Cooldown (sec)', places=0, default=10)
    timeout = DecimalField('Timeout (sec)', places=0, default=10)
    visible = BooleanField('Visible')
    locked = BooleanField('Locked')
    hide_output = BooleanField('Hide Output')
    dependencies = FieldList(FormField(QuestionDependencyForm))
    # cannot be "filenames" due to namespace collision in WTForm
    file_names = StringField(
        'Filenames',
        description='The filenames to be submitted, separated by commas.',
    ) 
    script = TextAreaField('Script')
    submit = SubmitField('Submit')

    def update_for(self, question_id, context):
        question = Question.query.get(question_id)
        self.id.data = question_id
        self.name.data = question.name
        if question.due_date:
            self.due_date.data = question.due_date.date
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
            question_dependency = QuestionDependency.query.filter_by(
                producer_id=other_question.id,
                consumer_id=question.id,
            ).first()
            if question_dependency:
                self.dependencies.append_entry({
                    'question_id': other_question.id,
                    'question': other_question.name,
                    'is_dependency': True,
                    'submissions_used': question_dependency.input_type,
                    'viewable': question_dependency.viewable,
                })
            else:
                self.dependencies.append_entry({
                    'question_id': other_question.id,
                    'question': other_question.name,
                    'submissions_used': 'latest',
                    'viewable': True,
                })
        self.file_names.data = ','.join(question_file.filename for question_file in question.filenames)
        self.script.data = question.script

    @staticmethod
    def build(context):
        form = QuestionForm()
        form.assignment_id.data = context['assignment'].id
        form.course.data = str(context['course'])
        form.course.render_kw['disabled'] = ''
        form.assignment.data = str(context['assignment'])
        form.assignment.render_kw['disabled'] = ''
        return form

    def validate_filenames(form, field):
        question_id = form.id.data
        if question_id is None:
            return
        question = Question.query.get(question_id)
        filenames = [filename.strip() for filename in form.file_names.data.split(',')]
        if not filenames:
            return
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
        question = Question.query.get(question_id)
        self.question_id.data = question_id
        for question_file in question.filenames:
            self.submission_files.append_entry({
                'question_file_id': question_file.id,
                'filename': question_file.filename,
            })

    @staticmethod
    def build(context):
        return SubmissionForm()
