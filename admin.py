from flask import url_for, redirect, request
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView

from .models import db
from .models import User, Instructor, Student
from .models import Semester, Course, Assignment, Question, QuestionDependency, QuestionFile
from .models import Submission, Upload, Result, ResultDependency

from .routes import get_user_context

admin = Admin(url='/dbadmin')


class DemograderModelView(ModelView):

    def is_accessible(self):
        context = get_user_context()
        return context['user'] and context['user'].admin

    def inaccessible_callback(self, name, **kwargs):
        # redirect to login page if user doesn't have access
        return redirect(url_for('login', next=request.url))


admin.add_view(DemograderModelView(User, db.session, category='Tables'))
admin.add_view(DemograderModelView(Instructor, db.session, category='Tables'))
admin.add_view(DemograderModelView(Student, db.session, category='Tables'))
admin.add_view(DemograderModelView(Semester, db.session, category='Tables'))
admin.add_view(DemograderModelView(Course, db.session, category='Tables'))
admin.add_view(DemograderModelView(Assignment, db.session, category='Tables'))
admin.add_view(DemograderModelView(QuestionDependency, db.session, category='Tables'))
admin.add_view(DemograderModelView(Question, db.session, category='Tables'))
admin.add_view(DemograderModelView(QuestionFile, db.session, category='Tables'))
admin.add_view(DemograderModelView(Submission, db.session, category='Tables'))
admin.add_view(DemograderModelView(Upload, db.session, category='Tables'))
admin.add_view(DemograderModelView(Result, db.session, category='Tables'))
admin.add_view(DemograderModelView(ResultDependency, db.session, category='Tables'))
