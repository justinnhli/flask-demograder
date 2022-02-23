from datetime import datetime

from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired
from wtforms import HiddenField, SubmitField, IntegerField, SelectField
from wtforms.validators import DataRequired

from .models import User, Semester, Course, Assignment, Question, QuestionFile


class SemesterForm(FlaskForm):
    id = HiddenField('id')
    season = SelectField('Season', choices=['fall', 'spring'])
    year = IntegerField('Year', default=datetime.now().year)
    submit = SubmitField('Submit')

    def validate(self):
        # validate() via the super class; if it doesn't pass, we're done
        if not FlaskForm.validate(self):
            return False
        # validate by seeing if the season and year combination already exists
        semester = Semester.query.filter_by(season=self.season.data, year=self.year.data).first()
        if semester and semester.id != self.id.data:
            self.year.errors.append('A Semester already exists for this season and year')
            return False
        return True
