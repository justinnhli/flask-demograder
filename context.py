from enum import IntEnum

from flask import session, request, abort


class Role(IntEnum):
    '''A class representing the role of the viewer.

    This exists to allow dynamically checking what the page looks like for different people.
    '''
    STUDENT = 0
    INSTRUCTOR = 1
    FACULTY = 2
    ADMIN = 3


def get_context(**kwargs):
    user = User.query.filter_by(email=session.get('user_email')).first()
    context = {}
    context['user'] = user
    # check if login is required
    if not kwargs.get('login_required', True):
        return context
    elif not user:
        abort(401)
    # check if the user is an instructor of the course
    if 'course' in context:
        context['instructor'] = True # FIXME
    else:
        context['instructor'] = False
    # get URL parameters
    args = request.args.to_dict()
    # Set admin rendering parameters, viewer and role.
    # These two parameters overlap in semantics slightly. The viewer parameter
    # is used to render a page as though they are the user. This is helpful for
    # checking that a page renders correctly. However, an appropriate viewer
    # is not always available; for example, if an admin is the sole instructor
    # of a course, and wants to see the page as a non-admin faculty, there is
    # no viewer that could provide that. Hence the role parameter, which can 
    # restrict the privileges of the user. In sum:
    # * the user is for checking actual permissions
    # * the viewer is for acting as a specific person
    # * the role is for checking renders
    # set viewer
    if user.admin and 'viewer' in args:
        context['viewer'] = User.query.filter_by(email=args['viewer']).first()
    if not context.get('viewer', None):
        context['viewer'] = user
    context['alternate_view'] = (context['user'] != context['viewer'])
    # set role
    context['Role'] = Role # this allows templates to branch on role
    if 'role' in args and args['role'].upper() not in Role.__members__.keys():
        del args['role']
    if context['viewer'].admin:
        context['role'] = min(
            Role[args.get('role', 'admin').upper()],
            Role.ADMIN,
        )
        context['alternate_view'] = context['alternate_view'] or (context['role'] != Role.ADMIN)
    elif context['viewer'].faculty:
        context['role'] = min(
            Role[args.get('role', 'faculty').upper()],
            Role.FACULTY,
        )
        context['alternate_view'] = context['alternate_view'] or (context['role'] != Role.FACULTY)
    elif context['instructor']:
        context['role'] = min(
            Role[args.get('role', 'instructor').upper()],
            Role.INSTRUCTOR,
        )
        context['alternate_view'] = context['alternate_view'] or (context['role'] != Role.INSTRUCTOR)
    else:
        context['role'] = Role.STUDENT
        context['alternate_view'] = context['alternate_view'] or (context['role'] != Role.STUDENT)
    return context
