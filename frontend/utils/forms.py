from flask_wtf import FlaskForm
from flask_babel import lazy_gettext as _
from wtforms import StringField, IntegerField,PasswordField,BooleanField, SelectMultipleField, FileField
from wtforms.fields.choices import RadioField
from wtforms.fields.simple import HiddenField, TextAreaField
from wtforms.validators import DataRequired,NumberRange, EqualTo, Regexp,StopValidation
from wtforms.widgets.core import CheckboxInput, ListWidget
from nms_shared.disks import Disk
from nms_shared.constants import PORT_MIN,PORT_MAX, POOLNAME,DATASETNAME
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

class ListTextAreaField(TextAreaField):
    def _value(self) -> str:
        if isinstance(self.data, list):
            return "\n".join(self.data)
        return super()._value()

    def process_formdata(self, valuelist) -> None:
        if valuelist:
            self.data = [
                line.strip()
                for line in valuelist[0].splitlines()
                if line.strip()
            ]
        else:
            self.data = []

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
    # username = StringField(_("Username"),validators=[DataRequired(),Regexp(r'^[a-z_][a-z0-9_-]*[$]?$',message=_("Invalid username: must start with a letter or _, and contain only lowercase letters, digits, _ or -."))])
    # password = PasswordField(_("Password"))
    # confirm_password = PasswordField(_("Confirm Password"), validators=[EqualTo('password', message=_('Passwords must match'))])

class FTPServiceForm(AccessServiceForm):
    ...


class NFSServiceForm(AccessServiceForm):
    ip = StringField(_("Hostname"),validators=[DataRequired()])

class SMBServiceForm(AccessServiceForm):
    ...
    # username = StringField(_("Username"),validators=[DataRequired()])
    # password = PasswordField(_("Password"))
    # confirm_password = PasswordField(_("Confirm Password"), validators=[EqualTo('password', message=_('Passwords must match'))])

class WEBServiceForm(AccessServiceForm):
   ...


class IFaceEnableForm(FlaskForm):
    iface_enabler = BooleanField()

class IPForm(FlaskForm):
    version = HiddenField()
    dynamic = BooleanField(_("Dynamic IP"),render_kw = {"class" :"toggle toggle-reverse toggle-target enabled"})
    address = StringField(_("Address"), render_kw =  {"class": "toggle-target dynamic enabled"})
    netmask = StringField(_("Netmask"), render_kw =  {"class": "toggle-target dynamic enabled"})
    gateway = StringField(_("Gateway"), render_kw =  {"class": "toggle-target dynamic enabled"})
    dns = ListTextAreaField(_("DNS"), render_kw =  {"class": "toggle-target dynamic enabled"})

class IPEnableForm(IPForm):
    enabled = BooleanField(_("Enabled"),render_kw = {"class" :"toggle"})

class VPNForm(FlaskForm):
    address = StringField(_("Address"))
    netmask = StringField(_("Netmask"))
    public_ip = StringField(_("Public IP"))

class ChangePasswordForm(FlaskForm):
    password = PasswordField(_("Password"), validators=[DataRequired()])
    confirm_password = PasswordField(_("Confirm Password"), validators=[EqualTo('password', message=_('Passwords must match'))])