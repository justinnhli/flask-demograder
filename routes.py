from flask import Blueprint, render_template, url_for, request, session, redirect
from werkzeug.utils import secure_filename

from .forms import SubmitForm
from .models import User, Semester, Course, Assignment, Question, QuestionFile
from .dispatch import evaluate_submission

blueprint = Blueprint(name='main', import_name='main')


def get_demograder_context():
    context = {}
    user_email = session.get('user_email')
    if not user_email:
        context['logged_in'] = False
        return context
    context['logged_in'] = True
    context['user'] = User.query.filter(User.email == user_email).first()
    #print(request)

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
    context = get_demograder_context()
    return render_template('index.html', **context)


@blueprint.route('/person/<person_id>')
def person_view(person_id):
    return f'{person_id=}' # TODO


@blueprint.route('/question/<question_id>')
def question_view(question_id):
    return f'{question_id=}' # TODO


@blueprint.route('/submission/<submission_id>')
def submission_view(submission_id):
    return f'{submission_id=}' # TODO


@blueprint.route('/submit', methods=['GET', 'POST'])
def form_view():
    form = SubmitForm()
    if form.validate_on_submit():
        submitted = form.submitted.data
        save_path = current_app.config['SUBMISSION_PATH'] / secure_filename(submitted.filename)
        submitted.save(save_path)
        evaluate_submission()
        return redirect(url_for('success'))
    return render_template('submit.html', form=form)


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
