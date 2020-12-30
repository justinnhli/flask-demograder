from .models import db, User, Semester, Course, Assignment, Question, QuestionFile


def init_db(app):
    # FIXME this is only necessary since we're testing via an in-memory DB
    with app.app_context():
        db.create_all()
        user = User(
            first_name='Justin',
            last_name='li',
            email='justinnhli@oxy.edu',
        )
        db.session.add(user)
        semester = Semester(
            season='spring',
            year=2021,
        )
        db.session.add(semester)
        db.session.flush()
        course = Course(
            semester_id=semester.id,
            department_code='COMP',
            number='337',
            title='Programming Languages',
        )
        db.session.add(course)
        db.session.flush()
        assignment = Assignment(
            course_id=course.id,
            name='Arithmetic Calculator',
        )
        db.session.add(assignment)
        db.session.flush()
        question = Question(
            assignment_id=assignment.id,
        )
        test_question = Question(
            assignment_id=assignment.id,
        )
        db.session.add(question)
        db.session.add(test_question)
        db.session.flush()
        question_file = QuestionFile(
            question_id=question.id,
            filename='hello.py',
        )
        test_question_file = QuestionFile(
            question_id=question.id,
            filename='hello.py',
        )
        db.session.add(question_file)
        db.session.add(test_question_file)
        db.session.commit()
