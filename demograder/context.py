from flask import session, request, abort
from sqlalchemy import select

from .models import db, SiteRole, CourseRole, User, Course, Assignment, Question, Submission, SubmissionFile, Result


def forbidden(context):
    if context['user'].admin:
        abort(418)
    else:
        abort(403)


def _set_site_role_context(context, url_args, **kwargs):
    if context['user'].admin:
        context['site_role'] = SiteRole.ADMIN
    elif context['user'].faculty:
        context['site_role'] = SiteRole.FACULTY
    else:
        context['site_role'] = SiteRole.STUDENT


def _set_viewer_context(context, url_args, **kwargs):
    if 'viewer' in url_args:
        context['viewer'] = db.session.scalar(select(User).where(User.email == url_args['viewer']))
    if not context.get('viewer', None):
        context['viewer'] = context['user']
    context['alternate_view'] = (context['user'] != context['viewer'])
    # check that the viewer is in a course taught by the user
    if context['alternate_view'] and not bool(context['user'].courses_with_student(context['viewer'].id).first()):
        forbidden(context)


def _set_course_context(context, url_args, **kwargs):
    if kwargs.get('submission_file_id', None):
        context['submission_file'] = db.session.scalar(
            select(SubmissionFile).where(SubmissionFile.id == kwargs['submission_file_id'])
        )
    else:
        context['submission_file'] = None
    if kwargs.get('result_id', None):
        context['result'] = db.session.scalar(
            select(Result).where(Result.id == kwargs['result_id'])
        )
    else:
        context['result'] = None
    # FIXME this might get confused when we're looking at support files
    if kwargs.get('submission_id', None):
        context['submission'] = db.session.scalar(
            select(Submission).where(Submission.id == kwargs['submission_id'])
        )
    elif context['result']:
        context['submission'] = context['result'].submission
    elif context['submission_file']:
        context['submission'] = context['submission_file'].submission
    else:
        context['submission'] = None
    if kwargs.get('question_id', None):
        context['question'] = db.session.scalar(
            select(Question).where(Question.id == kwargs['question_id'])
        )
    elif context['submission']:
        context['question'] = context['submission'].question
    else:
        context['question'] = None
    if kwargs.get('assignment_id', None):
        context['assignment'] = db.session.scalar(
            select(Assignment).where(Assignment.id == kwargs['assignment_id'])
        )
    elif context['question']:
        context['assignment'] = context['question'].assignment
    else:
        context['assignment'] = None
    if kwargs.get('course_id', None):
        context['course'] = db.session.scalar(
            select(Course).where(Course.id == kwargs['course_id'])
        )
    elif context['assignment']:
        context['course'] = context['assignment'].course
    else:
        context['course'] = None


def _set_course_role_context(context, url_args, **kwargs):
    is_instructor = (
        context['viewer'].admin
        or context['viewer'].is_teaching(context['course'].id)
    )
    if is_instructor:
        context['course_role'] = CourseRole.INSTRUCTOR
    else:
        context['course_role'] = CourseRole.STUDENT
    context['instructor'] = (context['course_role'] >= CourseRole.INSTRUCTOR)


def get_context(**kwargs):
    """Get the context for a request.

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
        FIXME assignment, question, submission, result

    Permission Parameters:
        login_required (bool): If the user must be logged in.
        user_id (int): The only user (or an admin) who is permitted.
            Note that this is _user_, not _viewer_ - this parameter is for
            things like account management.
        min_site_role (SiteRole): The minimum site role the viewer must have.
        min_course_role (CourseRole): The minimum course role the viewer must have.
    """
    # get URL parameters
    url_args = request.args.to_dict()
    context = {
        'SiteRole': SiteRole, # including the Enum allows templates to branch on site role
        'CourseRole': CourseRole, # including the Enum allows templates to branch on course role
        'user': db.session.scalar(select(User).where(User.email == session.get('user_email'))),
    }
    # if the user is not logged in, we can stop here
    if not context['user']:
        if kwargs.get('login_required', True):
            abort(401)
        else:
            return context
    # set site role context
    _set_site_role_context(context, url_args, **kwargs)
    # check that the user is the specific user required
    if 'user_id' in kwargs and kwargs['user_id'] != context['user'].id:
        forbidden(context)
    # check that the user has the site role required
    if context['site_role'] < kwargs.get('min_site_role', SiteRole.STUDENT):
        forbidden(context)
    # set viewer context
    _set_viewer_context(context, url_args, **kwargs)
    # if login is not required, no need to do anything else
    if not kwargs.get('login_required', True):
        return context
    # set course context
    _set_course_context(context, url_args, **kwargs)
    # FIXME user pages don't have a course context
    # check that both the user and the viewer are related to the course
    if context['course']:
        user = context['user']
        viewer = context['viewer']
        course = context['course']
        # check that the user is related to the course
        if not (user.is_teaching(course.id) or user.is_taking(course.id)):
            forbidden(context)
        # check that the viewer is related to the course
        if not (viewer.is_teaching(course.id) or viewer.is_taking(course.id)):
            forbidden(context)
        # set the course role context with respect to the course
        _set_course_role_context(context, url_args, **kwargs)
        # check that the viewer has the site role required
        # we don't need to check the user since the user is (non-strictly) more powerful
        if context['course_role'] < kwargs.get('min_course_role', CourseRole.STUDENT):
            forbidden(context)
        # backfill the submission; we do this here because the instructor context wasn't set
        if context['question'] and not context['submission']:
            context['submission'] = context['question'].submissions(
                user_id=context['viewer'].id,
                include_hidden=context['instructor'],
                include_disabled=context['instructor'],
                limit=1,
            ).first()
    return context
