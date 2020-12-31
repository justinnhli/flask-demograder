from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired
from wtforms import StringField
from wtforms.validators import DataRequired


class SubmitForm(FlaskForm):
    submitted = FileField('upload', validators=[FileRequired()])
