from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField,PasswordField,BooleanField
from wtforms.validators import DataRequired,NumberRange, EqualTo, Regexp,StopValidation
from constants import PORT_MIN,PORT_MAX

class DependentDataRequired(DataRequired):
    def __init__(self, fieldnames, message=None):
        super().__init__(message)
        self.fieldnames = fieldnames
        self.field_flags = {}

    def __call__(self, form, field):
        if any(form[name].data and \
            (not isinstance(form[name].data, str) or form[name].data.strip()) \
            for name in self.fieldnames
        ):
            super().__call__(form, field)
        else:
            raise StopValidation()

class AccessServiceForm(FlaskForm):
    def __init__(this, enabled):
        this._enabled = enabled
        super().__init__()

        prefix = this.__class__.__name__.lower()
        for name, field in this._fields.items():
            field.id = f"{prefix}_{name}"

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

class WEBServiceForm(AccessServiceForm):
    port = IntegerField("Port",validators=[NumberRange(min=PORT_MIN,max=PORT_MAX,message=f"The port number must be between {PORT_MIN}-{PORT_MAX}")])
    username = StringField("Username", validators=[
        DependentDataRequired(["authentication"],message="You must specify a username if authentication is enabled."),
        Regexp(r'^[a-z_][a-z0-9_-]*[$]?$',message="Invalid username: must start with a letter or _, and contain only lowercase letters, digits, _ or -.")
    ])
    password = PasswordField("Password")
    confirm_password = PasswordField("Confirm Password",
                                     validators=[EqualTo('password', message='Passwords must match')])
    authentication = BooleanField("Authentication:")


