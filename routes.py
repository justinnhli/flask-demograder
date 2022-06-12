import re
from datetime import datetime as DateTime

from flask import Blueprint, render_template, url_for, redirect, abort
from werkzeug.utils import secure_filename

from .context import get_context, Role
from .forms import UserForm, CourseForm, AssignmentForm, QuestionForm
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
    form = UserForm.for_user(user_id, context)
    if not form.is_submitted():
        form.process()
        return render_template('forms/user.html', form=form, **context)
    elif form.validate():
        if form.id.data:
            # if there is an ID, this is editing an existing User
            # make sure that the submitted ID is the same as the user ID
            if not (context['user'].admin or int(form.id.data) == user_id):
                abort(403)
            user = User.query.get(form.id.data)
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


def find_emails(text):
    return [
        re_match.group(0) for re_match in
        re.finditer(r'[0-9a-z._]+@[0-9a-z]+(\.[0-9a-z]+)+', text, flags=re.IGNORECASE)
    ]


@blueprint.route('/forms/course/', defaults={'course_id': None}, methods=('GET', 'POST'))
@blueprint.route('/forms/course/<int:course_id>', methods=('GET', 'POST'))
def course_form(course_id):
    context = get_context(course_id=course_id, min_role=Role.INSTRUCTOR.name)
    form = CourseForm.for_course(course_id, context)
    if not form.is_submitted():
        form.process()
        return render_template('forms/course.html', form=form, **context)
    elif form.validate():
        if form.id.data:
            # if there is an ID, this is editing an existing Course
            # make sure that the submitted ID is the same as the course ID
            if not (context['user'].admin or int(form.id.data) == user_id):
                abort(403)
            course = Course.query.get(form.id.data)
            course.season = form.season.data.strip() # FIXME
            course.year = int(form.year.data)
            course.department_code = form.department_code.data.strip()
            course.number = int(form.number.data)
            course.section = int(form.section.data)
            course.title = form.title.data.strip()
        else:
            # otherwise, this is creating a new Course
            course = Course(
                season=form.season.data, # FIXME
                year=int(form.year.data),
                department_code = form.department_code.data.strip(),
                number=int(form.number.data),
                section=int(form.section.data),
                title=form.title.data.strip(),
            )
        for instructor_str in form.instructors.data:
            course.instructors.append(User.query.filter_by(email=find_emails(instructor_str)[0]).first())
        for student_str in form.enrolled_students.choices:
            if student_str not in form.enrolled_students.data:
                course.students.remove(User.query.filter_by(email=find_emails(student_str)[0]).first())
        for email in find_emails(form.new_students.data.strip()):
            user = User.query.filter_by(email=email).first()
            if not user:
                user = User(email=email)
                db.session.add(user)
            course.students.append(user)
        db.session.add(course)
        db.session.commit()
        return redirect(url_for('demograder.home')) # FIXME redirect to course


@blueprint.route('/forms/assignment/<int:course_id>/', defaults={'assignment_id': None}, methods=('GET', 'POST'))
@blueprint.route('/forms/assignment/<int:course_id>/<int:assignment_id>/', methods=('GET', 'POST'))
def assignment_form(course_id, assignment_id):
    context = get_context(course_id=course_id, assignment_id=assignment_id, min_role=Role.INSTRUCTOR.name)
    form = AssignmentForm.for_assignment(assignment_id, context)
    if not form.is_submitted():
        form.process()
        return render_template('forms/assignment.html', form=form, **context)
    elif form.validate():
        if form.id.data:
            assignment = Assignment.query.get(form.id.data)
            assignment.name = form.name.data.strip()
        else:
            assignment = Assignment(
                course_id=course_id,
                name=form.name.data.strip(),
            )
        db.session.add(assignment)
        db.session.commit()
        return redirect(url_for('demograder.home')) # FIXME redirect to assignment


@blueprint.route('/forms/question/<int:assignment_id>/', defaults={'question_id': None}, methods=('GET', 'POST'))
@blueprint.route('/forms/question/<int:assignment_id>/<int:question_id>/', methods=('GET', 'POST'))
def question_form(assignment_id, question_id):
    context = get_context(assignment_id=assignment_id, question_id=question_id, min_role=Role.INSTRUCTOR.name)
    form = QuestionForm.for_question(question_id, context)
    if not form.is_submitted():
        form.process()
        return render_template('forms/question.html', form=form, **context)
    elif form.validate():
        due_date = form.due_date.data
        if due_date:
            due_date = DateTime(
                due_date.year, due_date.month, due_date.day,
                int(form.due_hour.data), int(form.due_minute.data),
            )
        else:
            due_date = None
        if form.id.data:
            question = Question.query.get(form.id.data)
        else:
            question = Question(assignment_id=assignment_id)
        question.name = form.name.data.strip()
        question.due_date = due_date
        question.cooldown = form.cooldown.data
        question.timeout = form.timeout.data
        question.visible = form.visible.data
        question.locked = form.locked.data
        question.hide_output = form.hide_output.data
        db.session.add(question)
        db.session.commit()
        return redirect(url_for('demograder.home')) # FIXME redirect to assignment


# REDIRECTS


@blueprint.errorhandler(401)
def unauthorized_error(error):
    return redirect(url_for('demograder.root'))
