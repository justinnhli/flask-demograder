from flask import Blueprint, render_template, url_for, request, session, redirect, abort
from werkzeug.utils import secure_filename

from .forms import SemesterForm
from .models import db, User, Semester, Course, Assignment, Question, QuestionFile
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
    context['semesters'] = Semester.query.all()
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


@blueprint.route('/forms/semester/', defaults={'semester_id': None}, methods=('GET', 'POST'))
@blueprint.route('/forms/semester/<semester_id>', methods=('GET', 'POST'))
def semester_form(semester_id):
    context = get_context()
    form = SemesterForm()
    if form.validate_on_submit():
        # if the form is being submitted, process it for data
        if form.id.data:
            # if there is a UID, this is editing an existing semester
            semester = Semester.query.filter_by(id=form.id.data).first()
            semester.season = form.season.data
            semester.year = form.year.data
        else:
            # otherwise, this is creating a new semester
            semester = Semester(season=form.season.data, year=form.year.data)
        db.session.add(semester)
        db.session.commit()
        return redirect(url_for('demograder.home')) # FIXME
    elif semester_id is not None:
        semester = Semester.query.filter_by(id=semester_id).first()
        form.id.default = semester.id
        form.season.default = semester.season
        form.year.default = semester.year
        form.process()
    return render_template('forms/semester.html', form=form, **context)


# REDIRECTS


@blueprint.errorhandler(401)
def unauthorized_error(error):
    return redirect(url_for('demograder.root'))
