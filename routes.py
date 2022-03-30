from flask import Blueprint, render_template, url_for, redirect, abort
from pandas import concat
from werkzeug.utils import secure_filename

from .context import _set_student_context, get_context, Role
import os.path
from .forms import UserForm
from .models import db, Student, User, Course, Assignment, Question, QuestionFile
from .dispatch import evaluate_submission

blueprint = Blueprint(name="demograder", import_name="demograder")


@blueprint.route("/")
def root():
    context = get_context(login_required=False)
    if context["user"]:
        return redirect(url_for("demograder.home"))
    return render_template("root.html")


@blueprint.route("/home")
def home():
    context = get_context()
    if context['role'] >= Role.ADMIN:
        context['users'] = User.query.all()
        context['courses'] = Course.query.all()
        context['assignments'] = Assignment.query.all()
        context['questions'] = Question.query.all()
        context['question_files'] = QuestionFile.query.all()
        return render_template('home-admin.html', **context)
    elif context['role'] >= Role.STUDENT:
        # Assuming the alternative view takes care of the difference with MASQ?
        context['courses'] = context['user'].courses_taking
        context['assignments'] = []
        for course in context['courses']:
            context['assignments'] += course.assignments
        return render_template('home-student.html', **context)
    else:
        return render_template('home.html', **context)


@blueprint.route('/user/<int:user_id>')
    if context["role"] >= Role.ADMIN:
        context["users"] = User.query.all()
        context["courses"] = Course.query.all()
        context["assignments"] = Assignment.query.all()
        context["questions"] = Question.query.all()
        context["question_files"] = QuestionFile.query.all()
    return render_template("home.html", **context)

def sizeof_fmt(num, suffix="B"):
    for unit in ["", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"]:
        if abs(num) < 1024.0:
            return f"{num:3.1f}{unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f}Yi{suffix}"

@blueprint.route("/overview")
def admin_overview():
    context = get_context()
    context["users"] = User.query.all()
    context["courses"] = Course.query.all()
    context["database_size"] = sizeof_fmt(os.path.getsize("database.sqlite"))
    return render_template("overview.html", **context)

@blueprint.route("/overview/users")
def users_overview():
    context = get_context()
    context["users"] = User.query.all()
    return render_template("users_overview.html", **context)

@blueprint.route("/overview/courses")
def courses_overview():
    context = get_context()
    context["courses"] = Course.query.all()
    return render_template("courses_overview.html", **context)

@blueprint.route("/user/<int:user_id>")
def user_view(user_id):
    return f"{user_id=}"  # TODO


@blueprint.route("/course/<int:course_id>")
def course_view(course_id):
    context = get_context()
    context['course'] = Course.query.get(course_id)
    print(context['course'].assignments[0].questions)
    return render_template('course-student.html', **context)

@blueprint.route("/question/<int:question_id>")
def question_view(question_id):
    return f"{question_id=}"  # TODO


@blueprint.route("/submission/<int:submission_id>")
def submission_view(submission_id):
    return f"{submission_id=}"  # TODO


@blueprint.route("/download_submission/<int:submission_id>")
def download_submission(submission_id):
    return f"{submission_id=}"  # TODO


@blueprint.route("/result/<int:result_id>")
def result_view(result_id):
    return f"{result_id=}"  # TODO


@blueprint.route("/download_result/<int:result_id>")
def download_result(result_id):
    return f"{result_id=}"  # TODO


@blueprint.route("/file/<int:file>")
def file_view(file_id):
    return f"{file_id=}"  # TODO


@blueprint.route("/download_file/<int:file>")
def download_file(file_id):
    return f"{file_id=}"  # TODO


# FORMS


@blueprint.route("/forms/user/", defaults={"user_id": None}, methods=("GET", "POST"))
@blueprint.route("/forms/user/<int:user_id>", methods=("GET", "POST"))
def user_form(user_id):
    context = get_context(user=user_id)
    form = UserForm()
    # if the form is being submitted, process it for data
    if form.validate_on_submit():
        if form.id.data:
            # if there is an ID, this is editing an existing User
            # make sure that the submitted ID is the same as the user ID
            if not (context["user"].admin or int(form.id.data) == user_id):
                abort(403)
            user = User.query.get(form.id.data).first()
            user.preferred_name = form.preferred_name.data.strip()
            user.family_name = form.family_name.data.strip()
            # only an admin can change the email or the admin/faculty statuses
            if context["user"].admin:
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
        return redirect(url_for("demograder.home"))  # FIXME
    # the form is not being submitted
    if user_id is not None:
        # a user ID is provided; set the defaults to the user being edited
        user = User.query.get(user_id)
        form.id.default = user.id
        form.preferred_name.default = user.preferred_name
        form.family_name.default = user.family_name
        form.email.default = user.email
        form.admin.default = user.admin
        form.faculty.default = user.faculty
        # disable the email field for non-admins
        if context["role"] < Role.ADMIN:
            form.email.render_kw["disabled"] = ""
        form.process()
    return render_template("forms/user.html", form=form, **context)


@blueprint.route(
    "/forms/course/", defaults={"course_id": None}, methods=("GET", "POST")
)
@blueprint.route("/forms/course/<int:course_id>", methods=("GET", "POST"))
def course_form(course_id):
    pass


# REDIRECTS


@blueprint.errorhandler(401)
def unauthorized_error(error):
    return redirect(url_for("demograder.root"))
