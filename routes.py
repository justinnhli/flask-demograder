from flask import Blueprint, render_template, url_for, redirect, abort
from werkzeug.utils import secure_filename

from .context import get_context, Role
from .forms import UserForm, CourseForm
from .models import db, User, Course, Assignment, Question, QuestionFile
from .dispatch import evaluate_submission

blueprint = Blueprint(name='demograder', import_name='demograder')


@blueprint.route('/')
def root():
    context = get_context(login_required=False)
    if context['user']:
        return redirect(url_for('demograder.home'))
    return render_template('root.html')


@blueprint.route('/home')
def home():
    context = get_context()
    if context['role'] >= Role.ADMIN:
        context['users'] = User.query.all()
        context['courses'] = Course.query.all()
        context['assignments'] = Assignment.query.all()
        context['questions'] = Question.query.all()
        context['question_files'] = QuestionFile.query.all()
        return render_template('home-admin.html', **context)
    else:
        return render_template('home.html', **context)


@blueprint.route('/user/<int:user_id>')
def user_view(user_id):
    return f'{user_id=}' # TODO


@blueprint.route('/course/<int:course_id>')
def course_view(course_id):
    return f'{course_id=}' # TODO


@blueprint.route('/question/<int:question_id>')
def question_view(question_id):
    return f'{question_id=}' # TODO


@blueprint.route('/submission/<int:submission_id>')
def submission_view(submission_id):
    return f'{submission_id=}' # TODO


@blueprint.route('/download_submission/<int:submission_id>')
def download_submission(submission_id):
    return f'{submission_id=}' # TODO


@blueprint.route('/result/<int:result_id>')
def result_view(result_id):
    return f'{result_id=}' # TODO


@blueprint.route('/download_result/<int:result_id>')
def download_result(result_id):
    return f'{result_id=}' # TODO


@blueprint.route('/file/<int:file>')
def file_view(file_id):
    return f'{file_id=}' # TODO


@blueprint.route('/download_file/<int:file>')
def download_file(file_id):
    return f'{file_id=}' # TODO


# FORMS


@blueprint.route('/forms/user/', defaults={'user_id': None}, methods=('GET', 'POST'))
@blueprint.route('/forms/user/<int:user_id>', methods=('GET', 'POST'))
def user_form(user_id):
    context = get_context(user=user_id)
    form = UserForm()
    # if the form is being submitted, process it for data
    if form.validate_on_submit():
        if form.id.data:
            # if there is an ID, this is editing an existing User
            # make sure that the submitted ID is the same as the user ID
            if not (context['user'].admin or int(form.id.data) == user_id):
                abort(403)
            user = User.query.get(form.id.data).first()
            user.preferred_name = form.preferred_name.data.strip()
            user.family_name = form.family_name.data.strip()
            # only an admin can change the email or the admin/faculty statuses
            if context['user'].admin:
                user.email = form.email.data.strip()
                user.admin = form.admin.data
                user.faculty = form.faculty.data
        else:
            # otherwise, this is creating a new User
            user = User(
                preferred_name=form.preferred_name.data.strip(),
                family_name=form.family_name.data.strip(),
                email=form.email.data.strip(),
                admin=form.admin.data,
                faculty=form.faculty.data,
            )
        db.session.add(user)
        db.session.commit()
        return redirect(url_for('demograder.home')) # FIXME
    # the form is not being submitted
    if user_id is not None:
        # a user ID is provided; set the defaults to the user being edited
        user = User.query.get(user_id).first()
        form.id.default = user.id
        form.preferred_name.default = user.preferred_name
        form.family_name.default = user.family_name
        form.email.default = user.email
        form.admin.default = user.admin
        form.faculty.default = user.faculty
        # disable the email field for non-admins
        if context['role'] < Role.ADMIN:
            form.email.render_kw['disabled'] = ''
        form.process()
    return render_template('forms/user.html', form=form, **context)


@blueprint.route('/forms/course/', defaults={'course_id': None}, methods=('GET', 'POST'))
@blueprint.route('/forms/course/<int:course_id>', methods=('GET', 'POST'))
def course_form(course_id):
    context = get_context(course=course_id)
    form = CourseForm()

    # add logic for the 'add me as instructor' option from form
    # ask about how this should work

    if form.validate_on_submit():
        parsed_students = parse_students(form.students.data.strip())
        if form.course_id:
            # is there anything that should be restrictured to just admin?
            course = Course.query.filter_by(id=form.id.data).first()
            course.season = form.season.data.strip()
            course.year = form.year.data.strip()
            course.department_code = form.department_code.data.strip()
            course.number = form.number.data.strip()
            course.section = form.section.data.strip()
            course.title = form.title.data.strip()

            # TODO:
            # - for the instructors & the students:
            #   - isolate the email addresses (parse function)
            #   - check with the username if there is already a User for them
            #     - if already user, grab that user and do course.instructors.append(user) / course.students.append(user)
            #     - else: creaate a new user for them, with just email (name, etc. = '') and then append
            
            course.instructors = form.instructors.data.strip()
            course.students = parsed_students

        else:
            course = Course(
                season = form.season.data.strip(),
                year = form.year.data.strip(),
                department_code = form.department_code.data.strip(),
                number = form.number.data.strip(),
                section = form.section.data.strip(),
                title = form.title.data.strip(),
                instructors = form.instructors.data.strip(),
                students = parsed_students,
            )
        db.session.add(course)
        db.session.commit()

        # TODO need to add student adding based on email addresses

        return redirect(url_for('demograder.home'))

    elif course_id:
        course = Course.query.filter_by(id=course_id).first()
        form.id.default = course.id
        form.season.default = course.season
        form.year.default = course.year
        form.department_code.default = course.department_code
        form.number.default = course.number
        form.section.default = course.section
        form.title.default = course.title
        form.instructors.default = course.instructors
        form.students.default = course.students
        form.process()
    return render_template('course_form.html', form=form, **context)


def parse_students(students):
    '''
    in: text/str list of all the students being enrolled
    out: a list of just the email addresses
    desc: grabs the email addresses from the 'students' field
    '''
    students_list = [item.strip(',/-.') for item in students.split(' ') if '@' in item]
    return students_list


@blueprint.errorhandler(401)
def unauthorized_error(error):
    return redirect(url_for('demograder.root'))
