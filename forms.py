from flask_wtf import FlaskForm
from wtforms import BooleanField, HiddenField, StringField, SubmitField
from wtforms.validators import Regexp

from .models import User


class UserForm(FlaskForm):
    id = HiddenField('id')
    preferred_name = StringField('Preferred name')
    family_name = StringField('Family Name')
    email = StringField(
        'Email',
        validators=[Regexp(
            r'^[\w.+-]+@[\w-]+(\.[\w-]+)+$',
            message='Please enter a valid email address',
        ),],
    )
    admin = BooleanField('Admin')
    faculty = BooleanField('Faculty')
    submit = SubmitField('Submit')

    def validate(self):
        # validate() via the super class; if it doesn't pass, we're done
        if not FlaskForm.validate(self):
            return False
        # validate by seeing if the season and year combination already exists
        user = User.query.filter_by(email=self.email.data).first()
        if user and user.id != self.id.data:
            self.email.errors.append('A User already exists with this email')
            return False
        return True
