from flask_wtf import FlaskForm
from wtforms import BooleanField, HiddenField, StringField, SubmitField, \
                    SelectField, DateField
from wtforms.validators import InputRequired, Regexp

from .models import User


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
    preferred_name = StringField('Preferred name')
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


class CourseForm(FlaskForm):
    id = HiddenField('id')
    season = SelectField(u'Season', choices=['Fall', 'Spring', 'Summer', 'Winter'])

    # is there a way to do a year dropdown field?
    year = StringField('Year')
    department_code = StringField('Department Code')
    number = StringField('Course Number')
    section = StringField('Section Number')
    title = StringField('Course Title')
    add_instructor = BooleanField('Add Me As Instructor')
    instructors = StringField('Instructors')
    students = StringField('Students')
    submit = SubmitField('Submit')

    # Are we representing this in the form or will these get added later?
    # assignments = 


class AssignmentForm(FlaskForm):
    id = HiddenField('id')
    course_id = HiddenField('course_id')
    name = StringField('Assignment Name')

    # should we use a different date format?
    # default for DateField is: format='%Y-%m-%d'
    due_date = DateField('Due Date')
    submit = SubmitField('Submit')


class QuestionForm(FlaskForm):
    id = HiddenField('id')
    assignment_id = StringField('Assignment ID')
    cooldown_seconds = StringField('Cooldown seconds')
    timeout_seconds = StringField('Timeout seconds')
    hide_output = BooleanField('Hide Output')
    visible = BooleanField('Visible')
    locked = BooleanField('Locked')
    submit = SubmitField('Submit')