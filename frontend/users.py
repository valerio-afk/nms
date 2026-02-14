from . import frontend as bp
from .api.backend_proxy import NMSBACKEND as BACKEND, show_flash
from .utils.forms import ChangePasswordForm
from .utils.widget import get_widgets_html, get_widgets_css_files, render_widget
from flask import session, render_template, g, flash, redirect, url_for, request, Response
from flask_babel import _
from flask_wtf.csrf import validate_csrf, ValidationError
from nms_shared.enums import UserPermissions
from nms_shared.msg import ErrorMessages
from typing import Dict, Tuple

USER_PERMISSIONS={
    "client" : lambda : _("Web Client"),
    "dashboard":lambda : _("Dashboard"),
    "access":lambda : _("Access"),
    "networks":lambda : _("Network"),
    "services":lambda : _("Access Services"),
    "users":lambda : _("Users"),
    "advanced":lambda : _("Advanced"),

    "pool":lambda : _("Disk Array"),
    "disks": lambda : _("Disks"),
    "health":lambda : _("Health"),
    "format": lambda : _("Format"),
    "tools":lambda : _("Tools"),
    "verify":lambda : _("Verify"),
    "mount":lambda : _("Mount"),
    "conf":lambda : _("Configuration"),
    "create":lambda : _("Create"),
    "import":lambda : _("Import"),
    "expand":lambda : _("Expand"),
    "destroy":lambda : _("Destroy"),

    "network":lambda : _("Network"),
    "interface" :lambda : _("Interface"),
    "manage":lambda : _("Manage"),
    "ddns": lambda : _("Dynamic DNS"),
    "vpn":lambda : _("VPN"),

    "sys": lambda : _("System"),
    "admin":lambda : _("Administration"),
    "acpi":lambda : _("Power Control"),
    "updates":lambda : _("Updates"),
    "systemctl":lambda : _("System Services"),
    "logs":lambda : _("Logs"),

    "account":lambda :_("Account"),
}

def check_permission(user:dict,perm:UserPermissions) -> bool:
    user_permissions = user.get("permissions",[])

    if "*" in user_permissions:
        return True

    parts = perm.value.split(".")

    for i in range(len(parts), 0, -1):
        candidate = ".".join(parts[:i])
        if candidate in user_permissions:
            return True

        wildcard = candidate + ".*"
        if wildcard in user_permissions:
            return True

    return False

def nest_permissions(permissions:Dict[str,bool]) -> Dict[str,bool]:
    result = {}

    def lang_key(key:str) -> str:
        if (key in USER_PERMISSIONS.keys()):
            return USER_PERMISSIONS[key]()
        else:
            return key.upper()

    for key, value in permissions.items():
        parts = key.split(".")
        current = result

        for part in parts[:-1]:
            current = current.setdefault(lang_key(part), {})


        current[lang_key(parts[-1])] = value

    return result

def widget_user_account() -> Tuple[str,str]:
    user = session.get("user")
    user_permissions = {p.value:check_permission(user,p) for p in sorted([x for x in UserPermissions],key=lambda y:y.value)}

    user_permissions = nest_permissions(user_permissions)

    return render_widget("account",user=user,user_permissions=user_permissions)

def widget_access_services() -> Tuple[str,str]:
    user = session.get("user")

    selected_services = ['ssh','smb']

    permissions = {
        service: UserPermissions[f'SERVICES_{service.upper()}_ACCESS'] for service in selected_services
    }

    forms = {}

    for s,p in permissions.items():
        if (check_permission(user,p)):
            forms[s] = ChangePasswordForm()

    return render_widget("account_services",forms=forms)

@bp.route("/account")
def user_account() -> str:
    dashboard_widgets = [
        widget_user_account(),
        widget_access_services(),
    ]

    return render_template("account.html",
                           csp_nonce=g.csp_nonce,
                           widgets=get_widgets_html(dashboard_widgets),
                           extra_css=get_widgets_css_files(dashboard_widgets)
                           )

@bp.route("/account/fullname",methods=["POST"])
def account_fullname() -> Response:
    form = request.form

    try:
        validate_csrf(request.form.get("csrf_token"))
    except ValidationError:
        show_flash(code=ErrorMessages.E_CSRF.name)
    else:
        user = session.get("user")
        BACKEND.set_user_fullname(user.get("username"),form["fullname"])
        session["user"] = BACKEND.current_user

    return redirect(url_for("main.user_account"))



@bp.route("/account/service/<string:service>",methods=["POST"])
def user_service_account(service:str):
    user = session.get("user")

    form = ChangePasswordForm()

    if (form.validate_on_submit()):
        BACKEND.change_password_to_service(service,user.get("username"),form.password.data)

    else:
        for errors in form.errors.values():
            for error in errors:
                flash(error,"error")

    return redirect(url_for("main.user_account"))



