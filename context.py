from enum import IntEnum

from flask import session, request, abort

from .models import User, Instructor, Student, Course


class Role(IntEnum):
    '''A class representing the role of the viewer.

    This exists to allow dynamically checking what the page looks like for different people.
    '''
    STUDENT = 0
    INSTRUCTOR = 1
    FACULTY = 2
    ADMIN = 3


def _set_user_context(context, url_args, **kwargs):
    context['user'] = User.query.filter_by(email=session.get('user_email')).first()


def _set_viewer_context(context, url_args, **kwargs):
    if context['user'].admin and 'viewer' in url_args:
        context['viewer'] = User.query.filter_by(email=url_args['viewer']).first()
    if not context.get('viewer', None):
        context['viewer'] = context['user']
    context['alternate_view'] = (context['user'] != context['viewer'])


def _set_course_context(context, url_args, **kwargs):
    # TODO determine question, assignment, and course
    # TODO check course access permissions
    if 'course_id' in kwargs:
        context['course'] = Course.query.filter_by(id=kwargs['course_id']).first()


def _set_instructor_context(context, url_args, **kwargs):
    if context['viewer'].admin:
        context['instructor'] = True
    elif context.get('course', None):
        context['instructor'] = bool(Instructor.query.filter_by(
            course_id=context['course'].id,
            user_id=context['viewer'].id,
        ).first())
    else:
        context['instructor'] = False


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
    elif context['instructor']:
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

    Parameters:
        login_required (bool): If the user must be logged in.
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
    _set_viewer_context(context, url_args, **kwargs)
    _set_course_context(context, url_args, **kwargs)
    _set_instructor_context(context, url_args, **kwargs)
    _set_role_context(context, url_args, **kwargs)
    return context
