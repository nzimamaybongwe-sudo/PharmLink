"""Auth forms"""
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, SelectField, TelField
from wtforms.validators import DataRequired, Email, Length, EqualTo, Optional, ValidationError
from app.models.user import User


class LoginForm(FlaskForm):
    email = StringField('Email Address', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember me')
    submit = SubmitField('Sign In')


class RegistrationForm(FlaskForm):
    first_name = StringField('First Name', validators=[DataRequired(), Length(1, 100)])
    last_name = StringField('Last Name', validators=[DataRequired(), Length(1, 100)])
    email = StringField('Email Address', validators=[DataRequired(), Email(), Length(max=255)])
    phone = TelField('Phone Number', validators=[Optional(), Length(max=20)])
    password = PasswordField('Password', validators=[
        DataRequired(), Length(min=8, message='Password must be at least 8 characters.')
    ])
    password2 = PasswordField('Confirm Password', validators=[
        DataRequired(), EqualTo('password', message='Passwords must match.')
    ])
    submit = SubmitField('Create Account')

    def validate_email(self, field):
        if User.query.filter_by(email=field.data.lower()).first():
            raise ValidationError('An account with this email already exists.')


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField('Current Password', validators=[DataRequired()])
    new_password = PasswordField('New Password', validators=[
        DataRequired(), Length(min=8, message='Password must be at least 8 characters.')
    ])
    confirm_password = PasswordField('Confirm New Password', validators=[
        DataRequired(), EqualTo('new_password', message='Passwords must match.')
    ])
    submit = SubmitField('Update Password')


class EditProfileForm(FlaskForm):
    first_name = StringField('First Name', validators=[DataRequired(), Length(1, 100)])
    last_name = StringField('Last Name', validators=[DataRequired(), Length(1, 100)])
    phone = TelField('Phone Number', validators=[Optional(), Length(max=20)])
    profession = StringField('Profession/Title', validators=[Optional(), Length(max=100)])
    licence_number = StringField('Licence / Registration Number', validators=[Optional(), Length(max=100)])
    submit = SubmitField('Save Changes')

