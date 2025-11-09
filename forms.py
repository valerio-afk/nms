from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField,PasswordField,SubmitField
from wtforms.validators import DataRequired,NumberRange
from constants import PORT_MIN,PORT_MAX

class AccessServiceForm(FlaskForm):
    port = IntegerField("Port",validators=[NumberRange(min=PORT_MIN,max=PORT_MAX,message=f"The port number must be between {PORT_MIN}-{PORT_MAX}")])
    username = StringField("Username",validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])
    enable = SubmitField("Enable")
    update = SubmitField("Update")
    disable = SubmitField("Disable")

    def __init__(this, enabled):
        this._enabled = enabled

        super().__init__()

    @property
    def is_enabled(this):
        return this._enabled