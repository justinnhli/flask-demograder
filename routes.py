from flask import Blueprint, render_template, url_for, request, session, redirect, abort
from werkzeug.utils import secure_filename

from .models import db, User, Course, Assignment, Question, QuestionFile
from .dispatch import evaluate_submission

blueprint = Blueprint(name='demograder', import_name='demograder')


def get_user():
    user_email = session.get('user_email')
    return User.query.filter(User.email == user_email).first()


def get_context():
    context = {}
    user = get_user()
    if not user:
        abort(401)
    context['user'] = user

    # FIXME temporary DB dump
    context['users'] = User.query.all()
    context['courses'] = Course.query.all()
    context['assignments'] = Assignment.query.all()
    context['questions'] = Question.query.all()
    context['question_files'] = QuestionFile.query.all()

    return context


@blueprint.route('/')
def root():
    user = get_user()
    if user:
        return redirect(url_for('demograder.home'))
    return render_template('index.html')


@blueprint.route('/home')
def home():
    context = get_context()
    return render_template('home.html', **context)


@blueprint.route('/person/<person_id>')
def person_view(person_id):
    return f'{person_id=}' # TODO


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


# REDIRECTS


@blueprint.errorhandler(401)
def unauthorized_error(error):
    return redirect(url_for('demograder.root'))
