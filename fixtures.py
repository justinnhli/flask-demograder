from sqlalchemy.exc import IntegrityError

from .models import db, User, Course, Assignment, Question, QuestionFile


def install_fixtures(app):
    with app.app_context():
        try:
            user1 = User(
                preferred_name='Justin',
                family_name='Li',
                email='justinnhli@oxy.edu',
                admin=True,
                faculty=True,
            )
            user2 = User(
                preferred_name='Kathy',
                family_name='Liu',
                email='kliu4@oxy.edu',
                admin=False,
                faculty=False,
            )
            db.session.add(user1)
            db.session.add(user2)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
