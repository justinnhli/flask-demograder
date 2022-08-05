from enum import IntEnum

from flask import session, request, abort

from .models import User, Course, Assignment, Question


class Role(IntEnum):
    '''A class representing the role of the viewer.

    This exists to allow dynamically checking what the page looks like for different people.
    '''
    STUDENT = 0
    INSTRUCTOR = 1
    FACULTY = 2
    ADMIN = 3


def forbidden(context):
    if not context['user'].admin:
        abort(403)


def _set_user_context(context, url_args, **kwargs):
    context['user'] = User.query.filter_by(email=session.get('user_email')).first()


def _set_viewer_context(context, url_args, **kwargs):
    if 'viewer' in url_args:
        context['viewer'] = User.query.filter_by(email=url_args['viewer']).first()
    if not context.get('viewer', None):
        context['viewer'] = context['user']
    context['alternate_view'] = (context['user'] != context['viewer'])


def _set_course_context(context, url_args, **kwargs):
    if 'question_id' in kwargs:
        context['question'] = Question.query.get(kwargs['question_id'])
    else:
        context['question'] = None
    if 'assignment_id' in kwargs:
        context['assignment'] = Assignment.query.get(kwargs['assignment_id'])
    elif context['question']:
        context['assignment'] = context['question'].assignment
    else:
        context['assignment'] = None
    if 'course_id' in kwargs:
        context['course'] = Course.query.get(kwargs['course_id'])
    elif context['assignment']:
        context['course'] = context['assignment'].course
    else:
        context['course'] = None


def _set_instructor_context(context, url_args, **kwargs):
    if context['viewer'].admin:
        context['instructor'] = True
    elif context.get('course', None):
        context['instructor'] = context['viewer'].teaching(context['course'])
    else:
        context['instructor'] = False


def _set_student_context(context, url_args, **kwargs):
    if context.get('course', None):
        context['student'] = context['viewer'].taking(context['course'])
    else:
        context['student'] = False


def _set_role_context(context, url_args, **kwargs):
    context['Role'] = Role # this allows templates to branch on role
    if 'role' in url_args and url_args['role'].upper() not in Role.__members__:
        del url_args['role']
    if context['viewer'].admin:
        context['role'] = min(
            Role[url_args.get('role', 'admin').upper()],
            Role.ADMIN,
        )
        context['alternate_view'] = context['alternate_view'] or (context['role'] != Role.ADMIN)
    elif context['viewer'].faculty:
        context['role'] = min(
            Role[url_args.get('role', 'faculty').upper()],
            Role.FACULTY,
        )
        context['alternate_view'] = context['alternate_view'] or (context['role'] != Role.FACULTY)
    elif context.get('instructor', False):
        context['role'] = min(
            Role[url_args.get('role', 'instructor').upper()],
            Role.INSTRUCTOR,
        )
        context['alternate_view'] = context['alternate_view'] or (context['role'] != Role.INSTRUCTOR)
    else:
        context['role'] = Role.STUDENT
        context['alternate_view'] = context['alternate_view'] or (context['role'] != Role.STUDENT)


def get_context(**kwargs):
    '''Get the context for a request.

    This function also aborts if permissions are violated. Course and
    submission permissions (ie. the viewer must be an instructor or a student)
    is always checked, if appropriate. The keyword arguments specify additional
    permissions to check.

    The viewer and role contexts makes it easier to see how a page renders for
    another user. These two parameters overlap in semantics slightly. The
    viewer parameter is used to render a page as though they are the user. This
    is helpful for checking that a page renders correctly. However, an
    appropriate viewer is not always available; for example, if an admin is the
    sole instructor of a course, and wants to see the page as a non-admin
    faculty, there is no viewer that could provide that. Hence the role
    parameter, which can restrict the privileges of the user.

    In sum:
    * the user is for checking actual permissions
    * the viewer is for acting as a specific person
    * the role is for checking renders

    Context Parameters:
        course_id (int): The course ID of the page being viewed.

    Permission Parameters:
        login_required (bool): If the user must be logged in.
        user (int): The only user (or an admin) who is permitted.
            Note that this is _user_, not _viewer_ - this parameter is for
            things like account management.
        min_role (Role): The minimum role the viewer must have.
    '''
    # get URL parameters
    url_args = request.args.to_dict()
    context = {}
    _set_user_context(context, url_args, **kwargs)
    # check if login is required
    if not kwargs.get('login_required', True):
        return context
    if not context['user']:
        abort(401)
    user = context['user']
    # check if the user is the specific user required
    if 'user' in kwargs and kwargs['user'] != user.id:
        forbidden(context)
    _set_viewer_context(context, url_args, **kwargs)
    viewer = context['viewer']
    # check if the viewer is in a course taught by the user
    if context['alternate_view']:
        viewer_is_student = bool(user.courses_with_student(viewer))
        viewer_is_instructor = bool(user.courses_with_coinstructor(viewer))
        if not (viewer_is_student or viewer_is_instructor):
            forbidden(context)
    _set_course_context(context, url_args, **kwargs)
    course = context['course']
    # check if both the user and the viewer are related to the course
    if course:
        _set_instructor_context(context, url_args, **kwargs)
        _set_student_context(context, url_args, **kwargs)
        # check if the user is related to the course
        if not (user.teaching(course) or user.taking(course)):
            forbidden(context)
        # check if the viewer is related to the course
        if context['alternate_view'] and not (context['instructor'] or context['student']):
            forbidden(context)
    _set_role_context(context, url_args, **kwargs)
    # check if the viewer meets the minimum role requirements
    if kwargs.get('min_role', Role.STUDENT) > context['role']:
        forbidden(context)
    return context
