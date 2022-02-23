from sqlalchemy.exc import IntegrityError

from .models import db, User, Course, Assignment, Question, QuestionFile

import traceback 


def install_fixtures(app):
    with app.app_context():
        try:
            user = User(
                preferred_name='Justin',
                family_name='li',
                email='justinnhli@oxy.edu',
            )
            db.session.add(user)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
