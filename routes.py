from flask import Blueprint, render_template, url_for, redirect, abort
from werkzeug.utils import secure_filename

from .context import get_context, Role
from .forms import UserForm, CourseForm, AssignmentForm, QuestionForm
from .models import db, User, Course, Assignment, Question, QuestionFile
from .dispatch import evaluate_submission

blueprint = Blueprint(name='demograder', import_name='demograder')


# --------------------------- 
# ROUTES
# ---------------------------
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


# --------------------------- 
# FORMS
# ---------------------------

# User Form
@blueprint.route('/forms/user/', defaults={'user_id': None}, methods=('GET', 'POST'))
@blueprint.route('/forms/user/<int:user_id>', methods=('GET', 'POST'))
def user_form(user_id):
    context = get_context(user=user_id)
    form = UserForm()
    if form.validate_on_submit():
        # if the form is being submitted, process it for data
        if form.id.data:
             # if there is an ID, this is editing an existing User
            if not (context['user'].admin or int(form.id.data) == user_id):
                # make sure that the submitted ID is the same as the user ID
                abort(403)
            user = User.query.get(form.id.data).first()
            user.preferred_name = form.preferred_name.data.strip()
            user.family_name = form.family_name.data.strip()
            if context['user'].admin:
                # only an admin can change the email or the admin/faculty statuses
                user.email = form.email.data.strip()
                user.admin = form.admin.data
                user.faculty = form.faculty.data
        # otherwise, this is creating a new User        
        else:
            user = User(
                preferred_name=form.preferred_name.data.strip(),
                family_name=form.family_name.data.strip(),
                email=form.email.data.strip(),
                admin=form.admin.data,
                faculty=form.faculty.data,
            )
        db.session.add(user)
        db.session.commit()
        return redirect(url_for('demograder.home'))
    if user_id:
        # the form is not being submitted
        # a user ID is provided; set the defaults to the user being edited
        user = User.query.get(user_id).first()
        form.id.default = user.id
        form.preferred_name.default = user.preferred_name
        form.family_name.default = user.family_name
        form.email.default = user.email
        form.admin.default = user.admin
        form.faculty.default = user.faculty
        if context['role'] < Role.ADMIN:
            # disable the email field for non-admins
            form.email.render_kw['disabled'] = ''
        form.process()
    return render_template('forms/user.html', form=form, **context)


# Course Form
@blueprint.route('/forms/course/', defaults={'course_id': None}, methods=('GET', 'POST'))
@blueprint.route('/forms/course/<int:course_id>', methods=('GET', 'POST'))
def course_form(course_id):
    context = get_context(course=course_id, min_role='faculty')
    form = CourseForm()
    if form.validate_on_submit():
        # extract the emails from the instructor & student fields
        instructor_emails = extract_emails(form.instructors.data.strip())
        student_emails = extract_emails(form.students.data.strip())
        # retrieve/generate User objects for the email addresses
        instructors = map(check_db_user, instructor_emails)
        students = map(check_db_user, student_emails)
        
        if form.id.data:
             # if the course already exists in the DB
            course = Course.query.get(int(form.id.data))
            if not course:
                abort(403)
            course = q.first()
            course.season = form.season.data.strip()
            course.year = form.year.data.strip()
            course.department_code = form.department_code.data.strip()
            course.number = form.number.data.strip()
            course.section = form.section.data.strip()
            course.title = form.title.data.strip()
        else:
            # if the course doesn't already exist in the DB
            course = Course(
                season=form.season.data.strip(),
                year=form.year.data.strip(),
                department_code=form.department_code.data.strip(),
                number=form.number.data.strip(),
                section=form.section.data.strip(),
                title=form.title.data.strip(),
            )
        
        # add the Users for instructors and students to the course
        for user in instructors:
            course.instructors.append(user)
        for user in students:
            course.students.append(user)
    
        db.session.add(course)
        db.session.commit()

        return redirect(url_for('demograder.home'))
    elif course_id:
        # pre-fills the fields if the course_id is specified in the URL
        course = Course.query.filter_by(id=course_id).first()
        form.id.default = course.id
        form.season.default = course.season
        form.year.default = course.year
        form.department_code.default = course.department_code
        form.number.default = course.number
        form.section.default = course.section
        form.title.default = course.title
        # create str representation of users to show in text boxes
        instructor_str = ''
        student_str = ''
        for user in course.instructors:
            instructor_str += str(user) + '\n'
        for user in course.students:
            student_str += str(user) + '\n'
        form.instructors.default = instructor_str
        form.students.default = student_str
        form.process()
    return render_template('forms/course.html', form=form, **context)


# Assignment Form
@blueprint.route('/forms/course/<int:course_id>/assignment/', defaults={'assignment_id': None}, methods=('GET', 'POST'))
@blueprint.route('/forms/course/<int:course_id>/assignment/<int:assignment_id>', methods=('GET', 'POST'))
def assignment_form(course_id=None, assignment_id=None):
    context = get_context(course_id=course_id, assignment_id=assignment_id, min_role='faculty')
    form = AssignmentForm()
    # check course exists in db
    course = Course.query.filter_by(id=course_id).first()
    if not course:
        abort(403)
    if form.validate_on_submit():
        if form.id.data:
             # if the assignment already exists in the DB
            assignment = context['assignment']
            assignment.course_id = course_id
            assignment.name = form.name.data.strip()
            assignment.due_date = form.due_date.data
        else:
            # if the assignment doesn't already exist in the DB
            assignment = Assignment(
                course_id=course_id,
                name=form.name.data.strip(),
                due_date=form.due_date.data,
            )
        db.session.add(assignment)
        db.session.commit()
        return redirect(url_for('demograder.home'))
    elif assignment_id:
        # if the id is specified in the URL, pre-fill the form with existing data
        # this implies that the assignment already exists in the DB
        assignment = Assignment.query.filter_by(id=assignment_id).first()
        form.id.default = assignment.id
        form.course_id.default = assignment.course_id
        form.name.default = assignment.name
        form.due_date.default = assignment.due_date
        form.process()
    else:
        form.course_id.default = context["course"].id
        form.process()
    return render_template('forms/assignment.html', form=form, **context)


# Question Form
@blueprint.route('/forms/assignment/<assignment_id>/question/', defaults={'question_id': None}, methods=('GET', 'POST'))
@blueprint.route('/forms/assignment/<assignment_id>/question/<question_id>', methods=('GET', 'POST'))
def question_form(assignment_id=None, question_id=None):
    context = get_context(assignment_id=assignment_id, question_id=question_id, min_role='faculty')
    form = QuestionForm()
    assignment = Assignment.query.filter_by(id=assignment_id).first()
    if not assignment:
         # check assignment exists in db
        abort(403)
    if form.validate_on_submit():
        if form.id.data:
             # if the question already exists in the DB
            question = context['question']
            question.assignment_id = assignment_id
            question.cooldown_seconds = form.cooldown_seconds.data.strip()
            question.timeout_seconds = form.timeout_seconds.data.strip()
            question.hide_output = form.hide_output.data
            question.visible = form.visible.data
            question.locked = form.locked.data
        else:
            # if the question doesn't already exist in the DB
            question = Question(
                assignment_id=assignment_id,
                cooldown_seconds=form.cooldown_seconds.data.strip(),
                timeout_seconds = form.timeout_seconds.data.strip(),
                hide_output = form.hide_output.data,
                visible = form.visible.data,
                locked = form.locked.data
            )
        db.session.add(question)
        db.session.commit()
        return redirect(url_for('demograder.home'))
    elif question_id: 
        # if the id is specified in the URL, pre-fill the form with existing data
        # this implies that the question already exists in the DB
        question = Question.query.filter_by(id=question_id).first()
        form.id.default = question.id
        form.assignment_id.default = question.assignment_id
        form.cooldown_seconds.default = question.cooldown_seconds
        form.timeout_seconds.default = question.timeout_seconds
        form.hide_output.default = question.hide_output
        form.visible.default = question.visible
        form.locked.default = question.locked
        form.process()
    else:
        form.assignment_id.default = context["assignment"].id
        form.process()
    return render_template('forms/question.html', form=form, **context)


# --------------------------- 
# UTILITY FUNCTIONS
# ---------------------------
def extract_emails(students):
    '''
    in: text/str list of all the students being enrolled
    return: a list of just the email addresses
    desc: grabs the email addresses from the 'students' field
    '''
    students_list = [item.strip(',/-.') for item in students.split(' ') if '@' in item]
    return students_list


def check_db_user(email):
    '''
    in: str email address
    return: User object
    desc: 
      - checks the db for a user with the provided email
      - returns the target User object if they exist,
      - else generates and returns a new user object with the email
    '''
    # query the db for the target user 
    # (not totally sure how querying works in sqlalchemy)
    #   - will it return None if no email found?
    #     - put in try, catch just incase
   
    user = User.query.filter_by(email=email).first()
    # usr.first()
    if user: 
        return user
   
    new_user = User(
        preferred_name='',
        family_name='',
        email=email,
        # what should these last two be set to?
        admin=False,
        faculty=False,
        # other attributes to define?
        )
    db.session.add(new_user)
    db.session.commit()
    return new_user


# --------------------------- 
# ERROR HANDLERS
# ---------------------------
@blueprint.errorhandler(401)
def unauthorized_error(error):
    return redirect(url_for('demograder.root'))
