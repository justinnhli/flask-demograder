from flask_wtf import FlaskForm
from wtforms.widgets import ListWidget, CheckboxInput
from wtforms import BooleanField, HiddenField, StringField, SubmitField, SelectMultipleField, TextAreaField, SelectField, DecimalField
from wtforms.validators import InputRequired, Regexp

from .models import SEASONS, User, Course


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
            form.id.default = user.id
            form.preferred_name.default = user.preferred_name
            form.family_name.default = user.family_name
            form.email.default = user.email
            form.admin.default = user.admin
            form.faculty.default = user.faculty
            # disable the email field for non-admins
            if context['role'] < context['Role'].ADMIN:
                form.email.render_kw['disabled'] = ''
        return form


class CourseForm(FlaskForm):
    id = HiddenField('id')
    season = SelectField('Season', choices=SEASONS)
    year = DecimalField('Year', places=0)
    department_code = StringField(
        'Department Code',
        default='COMP',
        validators=[InputRequired()],
    )
    number = DecimalField(
        'Course Number',
        places=0,
        validators=[InputRequired()],
    )
    section = DecimalField('Section', places=0, default=0) # FIXME uniqueness check
    title = StringField(
        'Title',
        validators=[InputRequired()],
    )
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
            # FIXME set form.season.default
            # FIXME set form.year.default
            form.instructors.default = [str(context['viewer']),]
            form.enrolled_students.choices = []
        else:
            course = Course.query.get(course_id)
            form.id.default = course.id
            form.season.default = course.season
            form.year.default = int(course.year)
            form.department_code.default = course.department_code
            form.number.default = int(course.number)
            form.section.default = int(course.section)
            form.title.default = course.title
            form.instructors.default = [str(user) for user in course.instructors]
            students = [
                str(user) for user in 
                sorted(
                    course.students,
                    key=(lambda student: (student.family_name, student.preferred_name, student.email)),
                )
            ]
            form.enrolled_students.choices = students
            form.enrolled_students.default = students
        return form
