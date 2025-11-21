from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField,PasswordField
from wtforms.validators import DataRequired,NumberRange, EqualTo, Regexp
from constants import PORT_MIN,PORT_MAX

class AccessServiceForm(FlaskForm):
    port = IntegerField("Port",validators=[NumberRange(min=PORT_MIN,max=PORT_MAX,message=f"The port number must be between {PORT_MIN}-{PORT_MAX}")])
    username = StringField("Username",validators=[DataRequired(),Regexp(r'^[a-z_][a-z0-9_-]*[$]?$',message="Invalid username: must start with a letter or _, and contain only lowercase letters, digits, _ or -.")])
    password = PasswordField("Password")
    confirm_password = PasswordField("Confirm Password", validators=[EqualTo('password', message='Passwords must match')])
    # enable = SubmitField("Enable")
    # update = SubmitField("Change")
    # disable = SubmitField("Disable")

    def __init__(this, enabled):
        this._enabled = enabled

        super().__init__()

    @property
    def is_enabled(this):
        return this._enabled