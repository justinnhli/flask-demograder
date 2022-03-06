from enum import IntEnum

from flask import Blueprint, render_template, url_for, request, session, redirect, abort
from werkzeug.utils import secure_filename

from .forms import UserForm
from .models import db, User, Course, Assignment, Question, QuestionFile
from .dispatch import evaluate_submission

blueprint = Blueprint(name='demograder', import_name='demograder')


class Role(IntEnum):
    '''A class representing the role of the viewer.

    This exists to allow dynamically checking what the page looks like for different people.
    '''
    STUDENT = 0
    INSTRUCTOR = 1
    FACULTY = 2
    ADMIN = 3


def get_context(**kwargs):
    user = User.query.filter_by(email=session.get('user_email')).first()
    context = {}
    context['user'] = user
    # check if login is required
    if not kwargs.get('login_required', True):
        return context
    elif not user:
        abort(401)
    # check if the user is an instructor of the course
    if 'course' in context:
        context['instructor'] = True # FIXME
    else:
        context['instructor'] = False
    # get URL parameters
    args = request.args.to_dict()
    # Set admin rendering parameters, viewer and role.
    # These two parameters overlap in semantics slightly. The viewer parameter
    # is used to render a page as though they are the user. This is helpful for
    # checking that a page renders correctly. However, an appropriate viewer
    # is not always available; for example, if an admin is the sole instructor
    # of a course, and wants to see the page as a non-admin faculty, there is
    # no viewer that could provide that. Hence the role parameter, which can 
    # restrict the privileges of the user. In sum:
    # * the user is for checking actual permissions
    # * the viewer is for acting as a specific person
    # * the role is for checking renders
    if user.admin:
        # set viewer
        if 'viewer' in args:
            context['viewer'] = User.query.filter_by(email=args['viewer']).first()
        if not context.get('viewer', None):
            context['viewer'] = user
        # set role
        if 'role' in args and args['role'].upper() not in Role.__members__.keys():
            del args['role']
        context['Role'] = Role # this allows templates to branch on role
        context['role'] = Role.ADMIN
        if context['viewer'].admin:
            context['role'] = Role[args.get('role', 'admin').upper()]
        elif context['viewer'].faculty:
            context['role'] = min(
                Role[args.get('role', 'faculty').upper()],
                context['role'],
            )
        elif context['instructor']:
            context['role'] = min(
                Role[args.get('role', 'instructor').upper()],
                context['role'],
            )
        else:
            context['role'] = Role.STUDENT

    # FIXME temporary DB dump
    context['users'] = User.query.all()
    context['courses'] = Course.query.all()
    context['assignments'] = Assignment.query.all()
    context['questions'] = Question.query.all()
    context['question_files'] = QuestionFile.query.all()

    return context


@blueprint.route('/')
def root():
    context = get_context(login_required=False)
    if context['user']:
        return redirect(url_for('demograder.home'))
    return render_template('root.html')


@blueprint.route('/home')
def home():
    context = get_context()
    if context['user'].admin:
        return render_template('home-admin.html', **context)
    else:
        return render_template('home.html', **context)


@blueprint.route('/user/<user_id>')
def user_view(user_id):
    return f'{user_id=}' # TODO


@blueprint.route('/question/<question_id>')
def question_view(question_id):
    return f'{question_id=}' # TODO


@blueprint.route('/submission/<submission_id>')
def submission_view(submission_id):
    return f'{submission_id=}' # TODO


@blueprint.route('/download_submission/<submission_id>')
def download_submission(submission_id):
    return f'{submission_id=}' # TODO


@blueprint.route('/result/<result_id>')
def result_view(result_id):
    return f'{result_id=}' # TODO


@blueprint.route('/download_result/<result_id>')
def download_result(result_id):
    return f'{result_id=}' # TODO


@blueprint.route('/file/<file>')
def file_view(file_id):
    return f'{file_id=}' # TODO


@blueprint.route('/download_file/<file>')
def download_file(file_id):
    return f'{file_id=}' # TODO


# FORMS


@blueprint.route('/forms/user/', defaults={'user_id': None}, methods=('GET', 'POST'))
@blueprint.route('/forms/user/<user_id>', methods=('GET', 'POST'))
def user_form(user_id):
    context = get_context()
    # check permissions
    # normal users can only edit themselves, unless they are an admin
    permitted = (
        context['user'].admin
        or (user_id is not None and user_id == context['user'].id)
    )
    if not permitted:
        abort(403)
    form = UserForm()
    # if the form is being submitted, process it for data
    if form.validate_on_submit():
        if form.id.data:
            # if there is an ID, this is editing an existing User
            # make sure that the submitted ID is the same as the user ID
            if not context['user'].admin and int(form.id.data) != user_id:
                abort(403)
            user = User.query.filter_by(id=form.id.data).first()
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
        user = User.query.filter_by(id=user_id).first()
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


# REDIRECTS


@blueprint.errorhandler(401)
def unauthorized_error(error):
    return redirect(url_for('demograder.root'))
