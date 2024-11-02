import re
from datetime import datetime as DateTime
from io import BytesIO
from zipfile import ZipFile

from flask import Blueprint, render_template, url_for, redirect, abort, request, send_file
from sqlalchemy import select
from werkzeug.utils import secure_filename

from .context import get_context
from .forms import UserForm, CourseForm, AssignmentForm, QuestionForm, SubmissionForm
from .models import db, SiteRole, CourseRole, User, Course, Assignment, Question
from .models import QuestionDependency, QuestionFile
from .models import Submission, SubmissionFile
from .dispatch import enqueue_evaluate_submission, enqueue_reevaluate_submission, enqueue_reevaluate_result

blueprint = Blueprint(name='demograder', import_name='demograder')


@blueprint.route('/')
def root():
    context = get_context(login_required=False)
    if context['user']:
        return redirect(url_for('demograder.home'))
    return render_template('login.html')


@blueprint.route('/about')
def about():
    context = get_context(login_required=False)
    return render_template('about.html', **context)


@blueprint.route('/home')
def home():
    context = get_context()
    return render_template('home.html', **context)


@blueprint.route('/user/<page_user_email>')
def user_view(page_user_email):
    page_user = User.get_by_email(page_user_email)
    if not page_user:
        abort(403)
    context = get_context(user_id=page_user.id)
    allowed = (
        context['user'].admin
        or context['viewer'].id == context['user'].id
        or bool(context['viewer'].courses_with_student(page_user.id).first())
    )
    if not allowed:
        abort(403)
    context['page_user'] = page_user
    return render_template('user.html', **context)


# STUDENT


@blueprint.route('/course/<int:course_id>')
def course_view(course_id):
    context = get_context(course_id=course_id)
    return render_template('student/course.html', **context)


@blueprint.route('/question/<int:question_id>', defaults={'submission_id': None}, methods=('GET', 'POST'))
@blueprint.route('/submission/<int:submission_id>', defaults={'question_id': None}, methods=('GET', 'POST'))
def submission_view(question_id, submission_id):
    # get the context
    if submission_id:
        context = get_context(submission_id=submission_id)
        question_id = context['question'].id
    else:
        context = get_context(question_id=question_id)
    # create the form
    form = SubmissionForm.build(context)
    # if the form is not being submitted, populate the form and return
    if not context['viewer'].may_submit(context['question'].id) or not form.is_submitted():
        form.update_for(context['question'].id, context)
        return render_template('student/submission.html', **context, form=form)
    # if the submitted form does not validate, return
    if not form.validate():
        return render_template('student/submission.html', **context, form=form)
    # create the Submission
    submission = Submission(
        user_id=context['viewer'].id,
        question_id=context['question'].id,
    )
    db.session.add(submission)
    db.session.commit()
    # create the associated SubmissionFiles
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
    # evaluate the submission and return
    enqueue_evaluate_submission(submission.id)
    return redirect(url_for('demograder.submission_view', submission_id=submission.id))


@blueprint.route('/disable_submission/<int:submission_id>')
def disable_submission(submission_id):
    # FIXME what should happen to results that have already been computed?
    context = get_context(submission_id=submission_id)
    context['submission'].disabled = not context['submission'].disabled
    db.session.add(context['submission'])
    db.session.commit()
    return redirect(url_for('demograder.submission_view', question_id=context['question'].id))


@blueprint.route('/reevaluate_submission/<int:submission_id>')
def reevaluate_submission(submission_id):
    enqueue_reevaluate_submission(submission_id)
    return redirect(url_for('demograder.submission_view', submission_id=submission_id))


@blueprint.route('/download_submission/<int:submission_id>')
def download_submission(submission_id):
    context = get_context(submission_id=submission_id)
    filename = f'submission{submission_id}'
    memory_file = BytesIO()
    with ZipFile(memory_file, 'w') as zip_file:
        for submission_file in context['submission'].files:
            zip_file.writestr(f'{filename}/{submission_file.filename}', submission_file.contents)
    memory_file.seek(0)
    return send_file(memory_file, download_name=f'{filename}.zip', as_attachment=True)


@blueprint.route('/result/<int:result_id>')
def result_view(result_id):
    context = get_context(result_id=result_id)
    return render_template('student/result.html', **context)


@blueprint.route('/reevaluate_result/<int:result_id>')
def reevaluate_result(result_id):
    enqueue_reevaluate_result(result_id)
    return redirect(url_for('demograder.result_view', result_id=result_id))


@blueprint.route('/download_result/<int:result_id>')
def download_result(result_id):
    return f'{result_id=}' # TODO


@blueprint.route('/file/<int:submission_file_id>')
def submission_file_view(submission_file_id):
    context = get_context(submission_file_id=submission_file_id)
    return render_template('student/submission_file.html', **context)


@blueprint.route('/download_file/<int:submission_file_id>')
def download_file(submission_file_id):
    context = get_context(submission_file_id=submission_file_id)
    submission_file = context['submission_file']
    return send_file(
        submission_file.filepath,
        download_name=submission_file.question_file.filename,
        as_attachment=True,
    )


# INSTRUCTOR


@blueprint.route('/user_submissions/<int:user_id>')
def user_submissions_view(user_id):
    page_user = db.session.get(User, user_id)
    if not page_user:
        abort(403)
    context = get_context(user_id=user_id)
    allowed = (
        context['user'].admin
        or context['viewer'].id == context['user'].id
        or bool(context['viewer'].courses_with_student(page_user.id).first())
    )
    if not allowed:
        abort(403)
    context['page_user'] = page_user
    return render_template('user_submissions.html', **context)


@blueprint.route('/course_enrollment/<int:course_id>')
def course_enrollment_view(course_id):
    context = get_context(course_id=course_id, min_course_role=CourseRole.INSTRUCTOR)
    return render_template('instructor/course_enrollment.html', **context)


@blueprint.route('/course_submissions/<int:course_id>')
def course_submissions_view(course_id):
    context = get_context(course_id=course_id, min_course_role=CourseRole.INSTRUCTOR)
    return render_template('instructor/course_submissions.html', **context)


@blueprint.route('/assignment_grades/<int:assignment_id>')
def assignment_grades_view(assignment_id):
    context = get_context(assignment_id=assignment_id, min_course_role=CourseRole.INSTRUCTOR)
    url_args = request.args.to_dict()
    try:
        iso_date = f'{url_args["date"]} {url_args["hour"]}:{url_args["minute"]}'
        context['before'] = DateTime.fromisoformat(iso_date)
    except (KeyError, ValueError):
        context['before'] = None
    return render_template('instructor/assignment_grades.html', **context)


@blueprint.route('/assignment_submissions/<int:assignment_id>')
def assignment_submissions_view(assignment_id):
    context = get_context(assignment_id=assignment_id, min_course_role=CourseRole.INSTRUCTOR)
    return render_template('instructor/assignment_submissions.html', **context)


@blueprint.route('/question_grades/<int:question_id>')
def question_grades_view(question_id):
    context = get_context(question_id=question_id, min_course_role=CourseRole.INSTRUCTOR)
    url_args = request.args.to_dict()
    try:
        iso_date = f'{url_args["date"]} {url_args["hour"]}:{url_args["minute"]}'
        context['before'] = DateTime.fromisoformat(iso_date)
    except (KeyError, ValueError):
        context['before'] = None
    return render_template('instructor/question_grades.html', **context)


@blueprint.route('/question_submissions/<int:question_id>')
def question_submissions_view(question_id):
    context = get_context(question_id=question_id, min_course_role=CourseRole.INSTRUCTOR)
    return render_template('instructor/question_submissions.html', **context)


# FORMS


@blueprint.route('/forms/user/', defaults={'user_id': None}, methods=('GET', 'POST'))
@blueprint.route('/forms/user/<int:user_id>', methods=('GET', 'POST'))
def user_form(user_id):
    # get the context
    context = get_context(user_id=user_id)
    # create the form
    form = UserForm.build(context)
    # if the form is not being submitted, populate the form and return
    if not form.is_submitted():
        if user_id is not None:
            form.update_for(user_id, context)
        return render_template('forms/user.html', form=form, **context)
    # if the submitted form does not validate, return
    if not form.validate():
        return render_template('forms/user.html', form=form, **context)
    # either get or create the User
    if form.id.data:
        # make sure the URL parameter matches the form id field
        if int(form.id.data) != user_id:
            abort(403)
        user = db.session.get(User, int(form.id.data))
        user.preferred_name = form.preferred_name.data.strip()
        user.family_name = form.family_name.data.strip()
        # only an admin can change the email or the admin/faculty statuses
        if context['user'].admin:
            user.email = form.email.data.strip()
            user.admin = form.admin.data
            user.faculty = form.faculty.data
    else:
        user = User(
            preferred_name=form.preferred_name.data.strip(),
            family_name=form.family_name.data.strip(),
            email=form.email.data.strip(),
            admin=form.admin.data,
            faculty=form.faculty.data,
        )
    # commit and return
    db.session.add(user)
    db.session.commit()
    return redirect(url_for('demograder.home'))


def find_emails(text):
    return [
        re_match.group(0) for re_match in
        re.finditer(r'[0-9a-z._]+@[0-9a-z]+(\.[0-9a-z]+)+', text, flags=re.IGNORECASE)
    ]


@blueprint.route('/forms/course/', defaults={'course_id': None}, methods=('GET', 'POST'))
@blueprint.route('/forms/course/<int:course_id>', methods=('GET', 'POST'))
def course_form(course_id):
    # get the context
    context = get_context(course_id=course_id, min_site_role=SiteRole.FACULTY)
    # create the form
    form = CourseForm.build(context)
    # if the form is not being submitted, populate the form and return
    if not form.is_submitted():
        if course_id is None:
            form.instructors.data = str(context['viewer'])
        else:
            form.update_for(course_id, context)
        return render_template('forms/course.html', form=form, **context)
    # if the submitted form does not validate, return
    if not form.validate():
        return render_template('forms/course.html', form=form, **context)
    # either get or create the Course
    if form.id.data:
        # make sure the URL parameter matches the form id field
        if int(form.id.data) != course_id:
            abort(403)
        course = db.session.get(Course, int(form.id.data))
        course.season = form.season.data.strip()
        course.year = int(form.year.data)
        course.department_code = form.department_code.data.strip()
        course.number = int(form.number.data)
        course.section = int(form.section.data)
        course.title = form.title.data.strip()
    else:
        course = Course(
            season=form.season.data,
            year=int(form.year.data),
            department_code = form.department_code.data.strip(),
            number=int(form.number.data),
            section=int(form.section.data),
            title=form.title.data.strip(),
        )
    # register instructors
    form_instructors = set(find_emails(form.instructors.data.strip()))
    curr_instructors = set(user.email for user in course.instructors)
    for email in form_instructors - curr_instructors:
        user = User.get_by_email(email)
        if not user:
            user = User(email=email)
            db.session.add(user)
        course.instructors.append(user)
    for email in curr_instructors - form_instructors:
        course.instructors.remove(User.get_by_email(email))
    # register students
    form_students = set(find_emails(form.students.data.strip()))
    curr_students = set(user.email for user in course.students)
    for email in form_students - curr_students:
        user = User.get_by_email(email)
        if not user:
            user = User(email=email)
            db.session.add(user)
        course.students.append(user)
    for email in curr_students - form_students:
        course.students.remove(User.get_by_email(email))
    # commit and return
    db.session.add(course)
    db.session.commit()
    return redirect(url_for('demograder.course_view', course_id=course.id))


@blueprint.route('/forms/assignment/<int:course_id>/', defaults={'assignment_id': None}, methods=('GET', 'POST'))
@blueprint.route('/forms/assignment/<int:course_id>/<int:assignment_id>/', methods=('GET', 'POST'))
def assignment_form(course_id, assignment_id):
    # get the context
    context = get_context(course_id=course_id, assignment_id=assignment_id, min_course_role=CourseRole.INSTRUCTOR)
    # create the form
    form = AssignmentForm.build(context)
    # if the form is not being submitted, populate the form and return
    if not form.is_submitted():
        if assignment_id is not None:
            form.update_for(assignment_id, context)
        return render_template('forms/assignment.html', form=form, **context)
    # if the submitted form does not validate, return
    if not form.validate():
        return render_template('forms/assignment.html', form=form, **context)
    # either get or create the Assignment
    if form.id.data:
        # make sure the URL parameter matches the form id field
        if int(form.id.data) != assignment_id:
            abort(403)
        assignment = db.session.get(Assignment, int(form.id.data))
        assignment.name = form.name.data.strip()
    else:
        assignment = Assignment(
            course_id=course_id,
            name=form.name.data.strip(),
        )
    # commit and return
    db.session.add(assignment)
    db.session.commit()
    return redirect(url_for('demograder.course_view', course_id=context['course'].id))


@blueprint.route('/forms/question/<int:assignment_id>/', defaults={'question_id': None}, methods=('GET', 'POST'))
@blueprint.route('/forms/question/<int:assignment_id>/<int:question_id>/', methods=('GET', 'POST'))
def question_form(assignment_id, question_id):
    # get the context
    context = get_context(assignment_id=assignment_id, question_id=question_id, min_course_role=CourseRole.INSTRUCTOR)
    # create the form
    form = QuestionForm.build(context)
    # if the form is not being submitted, populate the form and return
    if not form.is_submitted():
        if question_id is not None:
            form.update_for(question_id, context)
        else:
            form.update_for(None, context)
        return render_template('forms/question.html', form=form, **context)
    # if the submitted form does not validate, return
    if not form.validate():
        return render_template('forms/question.html', form=form, **context)
    # either get or create the Question
    if form.id.data:
        # make sure the URL parameter matches the form id field
        if int(form.id.data) != question_id:
            abort(403)
        question = db.session.get(Question, int(form.id.data))
    else:
        question = Question(assignment_id=assignment_id)
    # update the Question
    question.name = form.name.data.strip()
    if form.due_date.data:
        question.due_date = DateTime(
            form.due_date.year, form.due_date.month, form.due_date.day,
            int(form.due_hour.data), int(form.due_minute.data),
        )
    else:
        question.due_date = None
    question.cooldown_seconds = int(form.cooldown.data)
    question.timeout_seconds = int(form.timeout.data)
    question.visible = form.visible.data
    question.locked = form.locked.data
    question.allow_disable = form.allow_disable.data
    question.hide_output = form.hide_output.data
    question.script = form.script.data
    # update dependencies
    for dependency_form in form.dependencies:
        question_dependency = db.session.scalar(
            select(QuestionDependency)
            .where(
                QuestionDependency.producer_id == int(dependency_form.question_id.data),
                QuestionDependency.consumer_id == question.id,
            )
        )
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
    # update filenames
    # FIXME should be able to do the following, a la instructors/students in course_form
    # question.files.add(QuestionFile(...))
    # question.files.remove(QuestionFile(...))
    db.session.add(question)
    db.session.commit()
    filenames = {
        question_file.filename: question_file
        for question_file in question.filenames
    }
    # FIXME this would destroy data if a filename needs to be changed
    if form.file_names.data.strip():
        for filename in form.file_names.data.split(','):
            filename = filename.strip()
            if filename in filenames:
                del filenames[filename]
            else:
                db.session.add(QuestionFile(question_id=question.id, filename=filename))
    for _, question_file in filenames.items():
        db.session.delete(question_file)
    # commit and return
    db.session.commit()
    return redirect(url_for('demograder.submission_view', question_id=question.id))


# ADMIN


@blueprint.route('/admin')
def admin():
    context = get_context(min_site_role=SiteRole.ADMIN)
    return render_template('admin/home.html', **context)


@blueprint.route('/admin/users')
def admin_users_view():
    context = get_context(min_site_role=SiteRole.ADMIN)
    context['users'] = db.session.scalars(
        select(User)
        .order_by(User.id.desc())
    )
    return render_template('admin/users.html', **context)


@blueprint.route('/admin/courses')
def admin_courses_view():
    context = get_context(min_site_role=SiteRole.ADMIN)
    context['courses'] = db.session.scalars(
        select(Course)
        .order_by(Course.id.desc())
    )
    return render_template('admin/courses.html', **context)


@blueprint.route('/admin/submissions')
def admin_submissions_view():
    context = get_context(min_site_role=SiteRole.ADMIN)
    context['submissions'] = db.session.scalars(
        select(Submission)
        .order_by(Submission.timestamp.desc())
        .limit(200)
    )
    return render_template('admin/submissions.html', **context)


# REDIRECTS


@blueprint.errorhandler(401)
def unauthorized_error(error):
    return redirect(url_for('demograder.root'))
