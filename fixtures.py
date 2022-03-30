from datetime import datetime
from sqlalchemy.exc import IntegrityError

from .models import Student, Submission, db, User, Course, Assignment, Question, QuestionFile


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
                admin=False,
                faculty=False,
            )
            user3 = User(
                preferred_name='Alec',
                family_name='Phillips',
                email='aphillips2@oxy.edu',
                admin=False,
                faculty=False,
            )
            # student1 = Student(
            #     id = 1,
            #     user_id = 2,
            #     course_id = 2293
            # )
            # student2 = Student(
            #     id = 2,
            #     user_id = 3,
            #     course_id = 2295
            # )
            course = Course(
                id=2293,
                season='Spring',
                year=2022,
                department_code='COMP',
                number=229,
                section=1,
                title='Data Structures',
                students=[user2],
                instructors=[user],
            )
            
            course2 = Course(
                id=2295,
                season='Spring',
                year=2022,
                department_code='UBW',
                number=201,
                section=3,
                title='Underwater Basketweaving',
                students=[user2, user3],
                instructors=[user],
            )

            assignment = Assignment(
                id=1,
                course_id=2293,
                name='RiverCrossingProblem',
                due_date = datetime(2022, 4, 1, 23, 59, 59)
            )
            assignment2 = Assignment(
                id=2,
                course_id=2293,
                name='MiniMax',
                due_date = datetime(2022, 3, 1, 23, 59, 59)
            )
            assignment3 = Assignment(
                id=3,
                course_id=2295,
                name='Make A Basket!',
                due_date = datetime(2022, 5, 1, 23, 59, 59)
            )
            question1 = Question(
                id=1,
                assignment_id=1
            )
            submission1 = Submission (
                id=1,
                user_id=2,
                question_id=1,
                timestamp = datetime.now()
            )
            db.session.add(user)
            db.session.add(user2)
            db.session.add(course)
            db.session.add(course2)
            db.session.add(assignment)
            db.session.add(assignment2)
            db.session.add(assignment3)
            db.session.add(question1)
            db.session.add(submission1)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
