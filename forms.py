from flask_wtf import FlaskForm
from wtforms.widgets import ListWidget, CheckboxInput
from wtforms import BooleanField, HiddenField, StringField, SubmitField, SelectMultipleField, TextAreaField, SelectField, DecimalField, DateField
from wtforms.validators import InputRequired, Regexp, Optional

from .models import SEASONS, User, Course, Assignment, Question


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

    @staticmethod
    def for_user(user_id, context):
        form = UserForm()
        if user_id is not None:
            user = User.query.get(user_id)
            form.id.data = user.id
            form.preferred_name.data = user.preferred_name
            form.family_name.data = user.family_name
            form.email.data = user.email
            form.admin.data = user.admin
            form.faculty.data = user.faculty
            # disable the email field for non-admins
            if context['role'] < context['Role'].ADMIN:
                form.email.render_kw['disabled'] = ''
        return form


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

    @staticmethod
    def for_course(course_id, context):
        form = CourseForm()
        form.instructors.choices = [
            str(user) for user in 
            User.query.filter_by(faculty=True).all()
        ]
        if course_id is None:
            # FIXME set form.season.data
            # FIXME set form.year.data
            form.instructors.data = [str(context['viewer']),]
            form.enrolled_students.choices = []
        else:
            course = Course.query.get(course_id)
            form.id.data = course.id
            form.season.data = course.season
            form.year.data = int(course.year)
            form.department_code.data = course.department_code
            form.number.data = int(course.number)
            form.section.data = int(course.section)
            form.title.data = course.title
            form.instructors.data = [str(user) for user in course.instructors]
            students = [str(user) for user in sorted(course.students)]
            form.enrolled_students.choices = students
            form.enrolled_students.data = students
        return form


class AssignmentForm(FlaskForm):
    id = HiddenField('id')
    course_id = HiddenField('course_id')
    course = StringField('Course', render_kw={})
    name = StringField( 'Name',  validators=[InputRequired()])
    submit = SubmitField('Submit')

    @staticmethod
    def for_assignment(assignment_id, context):
        assignment = Assignment.query.get(assignment_id)
        form = AssignmentForm()
        form.id.data = assignment_id
        form.course_id.data = context['course'].id
        form.course.data = str(context['course'])
        form.course.render_kw['disabled'] = ''
        if assignment_id is not None:
            form.name.data = assignment.name
            if assignment.due_date:
                form.due_date.data = assignment.due_date.date
                form.due_hour.data = f'{assignment.due_date.hour:02d}'
                form.due_minute.data = f'{assignment.due_date.minute:02d}'
        return form


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
    # FIXME files
    # FIXME dependencies
    submit = SubmitField('Submit')

    @staticmethod
    def for_question(question_id, context):
        question = Question.query.get(question_id)
        form = QuestionForm()
        form.id.data = question_id
        form.assignment_id.data = context['assignment'].id
        form.course.data = str(context['course'])
        form.course.render_kw['disabled'] = ''
        form.assignment.data = str(context['assignment'])
        form.assignment.render_kw['disabled'] = ''
        if question_id is not None:
            form.name.data = question.name
            if question.due_date:
                form.due_date.data = question.due_date.date
                form.due_hour.data = f'{question.due_date.hour:02d}'
                form.due_minute.data = f'{question.due_date.minute:02d}'
            form.cooldown.data = question.cooldown_seconds
            form.timeout.data = question.timeout_seconds
            form.visible.data = question.visible
            form.locked.data = question.locked
            form.hide_output.data = question.hide_output
        return form
