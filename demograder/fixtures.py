from sqlalchemy.exc import IntegrityError

from .models import db, User, Course, Assignment, Question, QuestionFile


def install_fixtures(app):
    with app.app_context():
        try:
            user = User(
                preferred_name='Justin',
                family_name='Li',
                email='justinnhli@oxy.edu',
                admin=True,
                faculty=True,
            )
            db.session.add(user)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
