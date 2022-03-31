from flask import Blueprint, render_template, url_for, redirect, abort
from werkzeug.utils import secure_filename

from .context import get_context, Role
from .forms import UserForm, CourseForm, AssignmentForm
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
                print('hi')
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
    context = get_context(course=course_id, min_role='faculty')
    form = CourseForm()

    # add logic for the 'add me as instructor' option from form
    # ask about how this should work

    # goes here when the form is actually submitted
    if form.validate_on_submit():

        # extract the emails from the instructor & student fields
        instructor_emails = extract_emails(form.instructors.data.strip())
        student_emails = extract_emails(form.students.data.strip())

        # retrieve/generate User objects for the email addresses
        instructor_emails = map(check_db_user, instructor_emails)
        student_emails = map(check_db_user, student_emails)

        # if the course already exists in the DB
        if form.id.data:
            # is there anything that should be restrictured to just admin?
            q = Course.query.get(int(form.id.data))
            if not q:
                abort(403)
            course = q.first()
            course.season = form.season.data.strip()
            course.year = form.year.data.strip()
            course.department_code = form.department_code.data.strip()
            course.number = form.number.data.strip()
            course.section = form.section.data.strip()
            course.title = form.title.data.strip()

        # if the course doesn't already exist in the DB
        else:
            course = Course(
                season=form.season.data.strip(),
                year=form.year.data.strip(),
                department_code=form.department_code.data.strip(),
                number=form.number.data.strip(),
                section=form.section.data.strip(),
                title=form.title.data.strip(),
                instructors=[],
                students=[],
            )
        
        # add the Users for instructors and students to the course
        for user in instructor_emails:
            course.instructors.append(user)
        for user in student_emails:
            course.students.append(user)
    
        db.session.add(course)
        db.session.commit()

        return redirect(url_for('demograder.home'))

    # pre-fills the fields if the course_id is specified in the URL
    # happens when they load the page initially
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
    
    return render_template('forms/course.html', form=form, **context)


# NEW ROUTE for Assignments
# double check that these URLs are correct
@blueprint.route('/forms/course/assignment', defaults={'assignment_id': None}, methods=('GET', 'POST'))
@blueprint.route('/forms/course/assignment/<int:assignment_id>', methods=('GET', 'POST'))
def assignment_form(assignment_id):
    context = get_context(assignment=assignment_id, min_role='faculty')
    form = AssignmentForm()

    # goes here when the form is actually submitted
    if form.validate_on_submit():

        # if the assignment already exists in the DB
        if form.id.data:
            q = Assignment.query.get(int(form.id.data))
            if not q:
                abort(403)
            assignment = q.first()
            assignment.course_id = form.course_id.data.strip()
            assignment.name = form.name.data.strip()
            assignment.due_date = form.due_date.data

        # if the assignment doesn't already exist in the DB
        else:
            assignment = Assignment(
                course_id=form.course_id.data.strip(),
                name=form.name.data.strip(),
                due_date=form.due_date.data,
            )
        
        # commit this assignment to the DB
        db.session.add(assignment)
        db.session.commit()

        # end, redirecct to home page
        return redirect(url_for('demograder.home'))

    # if the id is specified in the URL, pre-fill the form with existing data
    # this implies that the assignment already exists in the DB
    elif assignment_id:
        assignment = Assignment.query.filter_by(id=assignment_id).first()
        form.id.default = assignment.id
        form.course_id.default = assignment.course_id
        form.name.default = assignment.name
        form.due_date.default = assignment.due_date
        form.process()

    return render_template('forms/assignment.html', form=form, **context)


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
