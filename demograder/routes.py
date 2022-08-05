import re
from datetime import datetime as DateTime

from flask import Blueprint, render_template, url_for, redirect, abort
from werkzeug.utils import secure_filename

from .context import get_context, Role
from .forms import UserForm, CourseForm, AssignmentForm, QuestionForm, SubmissionForm
from .models import db, User, Course, Assignment, Question
from .models import QuestionDependency, QuestionFile
from .models import Submission, SubmissionFile
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
    return render_template('home.html', **context)


@blueprint.route('/admin')
def admin():
    context = get_context(min_role=Role.ADMIN)
    context['users'] = User.query.all()
    context['courses'] = Course.query.all()
    context['assignments'] = Assignment.query.all()
    context['questions'] = Question.query.all()
    context['question_files'] = QuestionFile.query.all()
    context['submissions'] = Submission.query.all()
    return render_template('admin-home.html', **context)


@blueprint.route('/user/<int:user_id>')
def user_view(user_id):
    return f'{user_id=}' # TODO


@blueprint.route('/course/<int:course_id>')
def course_view(course_id):
    return f'{course_id=}' # TODO


@blueprint.route('/question/<int:question_id>', methods=('GET', 'POST'))
def question_view(question_id):
    context = get_context(question_id=question_id)
    form = SubmissionForm()
    if not form.is_submitted():
        form.update_for(question_id, context)
        return render_template('question.html', **context, form=form)
    elif form.validate_on_submit():
        submission = Submission(
            user_id=context['viewer'].id,
            question_id=question_id,
        )
        db.session.add(submission)
        db.session.commit()
        for file_submission_form in form.submission_files:
            submission_file = SubmissionFile(
                submission_id=submission.id,
                question_file_id=file_submission_form.question_file_id.data,
                filename=secure_filename(file_submission_form.file.data.filename),
            )
            db.session.add(submission_file)
            db.session.commit()
            submission_file.filepath.parent.mkdir(parents=True, exist_ok=True)
            file_submission_form.file.data.save(submission_file.filepath)
        db.session.commit()
        # FIXME dispatch job
        return redirect(url_for('demograder.question_view', question_id=question_id))


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
    form = UserForm.build(context)
    if not form.is_submitted():
        if user_id is not None:
            form.update_for(user_id, context)
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
    else:
        return render_template('forms/user.html', form=form, **context)


def find_emails(text):
    return [
        re_match.group(0) for re_match in
        re.finditer(r'[0-9a-z._]+@[0-9a-z]+(\.[0-9a-z]+)+', text, flags=re.IGNORECASE)
    ]


@blueprint.route('/forms/course/', defaults={'course_id': None}, methods=('GET', 'POST'))
@blueprint.route('/forms/course/<int:course_id>', methods=('GET', 'POST'))
def course_form(course_id):
    context = get_context(course_id=course_id, min_role=Role.INSTRUCTOR)
    form = CourseForm.build(context)
    if not form.is_submitted():
        if course_id is not None:
            form.update_for(course_id, context)
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
        return redirect(url_for('demograder.course_view', course_id=context['course'].id)) # FIXME
    else:
        return render_template('forms/course.html', form=form, **context)


@blueprint.route('/forms/assignment/<int:course_id>/', defaults={'assignment_id': None}, methods=('GET', 'POST'))
@blueprint.route('/forms/assignment/<int:course_id>/<int:assignment_id>/', methods=('GET', 'POST'))
def assignment_form(course_id, assignment_id):
    context = get_context(course_id=course_id, assignment_id=assignment_id, min_role=Role.INSTRUCTOR)
    form = AssignmentForm.build(context)
    if not form.is_submitted():
        if assignment_id is not None:
            form.update_for(assignment_id, context)
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
        return redirect(url_for('demograder.course_view', course_id=context['course'].id)) # FIXME
    else:
        return render_template('forms/assignment.html', form=form, **context)


@blueprint.route('/forms/question/<int:assignment_id>/', defaults={'question_id': None}, methods=('GET', 'POST'))
@blueprint.route('/forms/question/<int:assignment_id>/<int:question_id>/', methods=('GET', 'POST'))
def question_form(assignment_id, question_id):
    context = get_context(assignment_id=assignment_id, question_id=question_id, min_role=Role.INSTRUCTOR)
    form = QuestionForm.build(context)
    if not form.is_submitted():
        if question_id is not None:
            form.update_for(question_id, context)
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
        for dependency_form in form.dependencies:
            question_dependency = QuestionDependency.query.filter_by(
                producer_id=int(dependency_form.question_id.data),
                consumer_id=question.id,
            ).first()
            if dependency_form.is_dependency.data:
                if not question_dependency:
                    question_dependency = QuestionDependency(
                        producer_id=int(dependency_form.question_id.data),
                        consumer_id=question.id,
                    )
                question_dependency.input_type = dependency_form.submissions_used.data
                question_dependency.submitters = dependency_form.submitters_used.data
                question_dependency.viewable = dependency_form.viewable.data
                db.session.add(question_dependency)
            else:
                if question_dependency:
                    db.session.delete(question_dependency)
        question.name = form.name.data.strip()
        question.due_date = due_date
        question.cooldown = form.cooldown.data
        question.timeout = form.timeout.data
        question.visible = form.visible.data
        question.locked = form.locked.data
        question.hide_output = form.hide_output.data
        filenames = {
            question_file.filename: question_file
            for question_file in question.filenames
        }
        # FIXME this would destroy data if a filename needs to be changed
        if form.file_names.data.strip():
            for filename in form.file_names.data.split(','):
                if filename in filenames:
                    del filenames[filename]
                else:
                    db.session.add(QuestionFile(question_id=question_id, filename=filename))
        for _, question_file in filenames.items():
            db.session.delete(question_file)
        question.script = form.script.data
        db.session.add(question)
        db.session.commit()
        return redirect(url_for('demograder.course_view', course_id=context['course'].id)) # FIXME
    else:
        return render_template('forms/question.html', form=form, **context)


# REDIRECTS


@blueprint.errorhandler(401)
def unauthorized_error(error):
    return redirect(url_for('demograder.root'))