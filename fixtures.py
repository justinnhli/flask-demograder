from datetime import datetime
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
            user2 = User(
                preferred_name='Christopher',
                family_name='Linscott',
                email='clinscott@oxy.edu',
                admin=True,
                faculty=False,
            )
            assignment1 = Assignment(
                id=5328423,
                course_id=34,
                name='Homework 1',
                due_date=datetime(2022, 3, 24, 23, 59, 59),
            )
            assignment2 = Assignment(
                id=3435453,
                course_id=34,
                name='Homework 2',
                due_date=datetime(2022, 3, 24, 23, 59, 59),
            )
            assignment3 = Assignment(
                id=324342342,
                course_id=34,
                name='Homework 1',
                due_date=datetime(2022, 3, 24, 23, 59, 59),
            )
            db.session.add(user)
            db.session.add(user2)
            db.session.add(assignment1)
            db.session.add(assignment2)
            db.session.add(assignment3)

            db.session.commit()
        except IntegrityError:
            db.session.rollback()
