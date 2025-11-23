from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField,PasswordField
from wtforms.validators import DataRequired,NumberRange, EqualTo, Regexp
from constants import PORT_MIN,PORT_MAX

class AccessServiceForm(FlaskForm):
    def __init__(this, enabled):
        this._enabled = enabled
        super().__init__()

    @property
    def is_enabled(this):
        return this._enabled

class SSHServiceForm(AccessServiceForm):
    port = IntegerField("Port",validators=[NumberRange(min=PORT_MIN,max=PORT_MAX,message=f"The port number must be between {PORT_MIN}-{PORT_MAX}")])
    username = StringField("Username",validators=[DataRequired(),Regexp(r'^[a-z_][a-z0-9_-]*[$]?$',message="Invalid username: must start with a letter or _, and contain only lowercase letters, digits, _ or -.")])
    password = PasswordField("Password")
    confirm_password = PasswordField("Confirm Password", validators=[EqualTo('password', message='Passwords must match')])

class FTPServiceForm(AccessServiceForm):
    ...


class NFSServiceForm(AccessServiceForm):
    ip = StringField("Hostname",validators=[DataRequired()])

class SMBServiceForm(AccessServiceForm):
    username = StringField("Username",validators=[DataRequired()])
    password = PasswordField("Password")
    confirm_password = PasswordField("Confirm Password", validators=[EqualTo('password', message='Passwords must match')])