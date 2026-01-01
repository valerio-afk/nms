from flask_wtf import FlaskForm
from flask_babel import lazy_gettext as _
from wtforms import StringField, IntegerField,PasswordField,BooleanField, SelectMultipleField, HiddenField, FileField
from wtforms.fields.choices import RadioField
from wtforms.validators import DataRequired,NumberRange, EqualTo, Regexp,StopValidation
from wtforms.widgets.core import CheckboxInput, ListWidget
from disk import Disk
from constants import PORT_MIN,PORT_MAX, POOLNAME,DATASETNAME
from typing import List

class ToggleInput(CheckboxInput):

    def __call__(this,field,**kwargs):
        classes = kwargs.get("class","")

        classes += " form-check-input"

        kwargs['class'] = classes.strip()

        return f"<span class='form-switch me-2'>{super().__call__(field,**kwargs)}</span>"

class MultiCheckboxField(SelectMultipleField):
	widget			= ListWidget(prefix_label=False)
	option_widget	= ToggleInput()

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

class AtLeastOneField:
    def __init__(this,message=None):
        this._message = message

    def __call__(this, form, field):
        if (not field.data) or (len(field.data) == 0):
            raise StopValidation(this._message)

class AddDisksForm(FlaskForm):
    disks = RadioField("Disks",validators=[DataRequired()])

    def __init__(this,disks:List[Disk],*args, **kwargs):
        super().__init__(*args,**kwargs)

        this.disks.choices = [(
            d.physical_paths[0] if isinstance(d.physical_paths, list) else d.physical_paths,
            d.path
        ) for d in disks]

        if not this.is_submitted():
            if (len(this.disks.choices) > 0):
                this.disks.default = this.disks.choices[0][0]
            this.process()

class CreatePoolForm(FlaskForm):
    redundancy = BooleanField(_("Redundancy"))
    encryption = BooleanField(_("Encryption"))
    compression = BooleanField(_("Compression"))
    pool_name = StringField(_("Pool Name"),validators=[DataRequired()], default=POOLNAME)
    dataset_name = StringField(_("Dataset Name"), validators=[DataRequired()], default=DATASETNAME)
    disks = MultiCheckboxField(_("Disks"),validators=[AtLeastOneField(_("You must select at least one disk to create an array"))])

    def __init__(this,disks:List[Disk],*args, **kwargs):
        super().__init__(*args,**kwargs)

        this.disks.choices = [(
            d.physical_paths[0] if isinstance(d.physical_paths, list) else d.physical_paths,
            d.path
        ) for d in disks]


        if not this.is_submitted():
            this.disks.default = [x[0] for x in this.disks.choices]
            this.process()

class ImportPoolForm(FlaskForm):
    key = FileField(_("Key"))


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
    port = IntegerField(_("Port"),validators=[NumberRange(min=PORT_MIN,max=PORT_MAX,message=_("The port number must be between %(port_min)s-%(port_max)s",port_min=PORT_MIN,port_max=PORT_MAX))])
    username = StringField(_("Username"),validators=[DataRequired(),Regexp(r'^[a-z_][a-z0-9_-]*[$]?$',message=_("Invalid username: must start with a letter or _, and contain only lowercase letters, digits, _ or -."))])
    password = PasswordField(_("Password"))
    confirm_password = PasswordField(_("Confirm Password"), validators=[EqualTo('password', message=_('Passwords must match'))])

class FTPServiceForm(AccessServiceForm):
    ...


class NFSServiceForm(AccessServiceForm):
    ip = StringField(_("Hostname"),validators=[DataRequired()])

class SMBServiceForm(AccessServiceForm):
    username = StringField(_("Username"),validators=[DataRequired()])
    password = PasswordField(_("Password"))
    confirm_password = PasswordField(_("Confirm Password"), validators=[EqualTo('password', message=_('Passwords must match'))])

class WEBServiceForm(AccessServiceForm):
    port = IntegerField(_("Port"),validators=[NumberRange(min=PORT_MIN,max=PORT_MAX,message=_("The port number must be between %(port_min)s-%(port_max)s",port_min=PORT_MIN,port_max=PORT_MAX))])
    username = StringField(_("Username"), validators=[
        DependentDataRequired(["authentication"],message=_("You must specify a username if authentication is enabled.")),
        Regexp(r'^[a-z_][a-z0-9_-]*[$]?$',message=_("Invalid username: must start with a letter or _, and contain only lowercase letters, digits, _ or -."))])
    password = PasswordField(_("Password"))
    confirm_password = PasswordField(_("Confirm Password"),
                                     validators=[EqualTo('password', message=_('Passwords must match'))])
    authentication = BooleanField(_("Authentication:"))


