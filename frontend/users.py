from . import frontend as bp
from .api.backend_proxy import NMSBACKEND as BACKEND, show_flash
from .utils.forms import ChangePasswordForm
from .utils.widget import get_widgets_html, get_widgets_css_files, render_widget
from flask import session, render_template, g, flash, redirect, url_for, request, Response
from flask_babel import _
from flask_wtf.csrf import validate_csrf, ValidationError
from nms_shared.enums import UserPermissions
from nms_shared.msg import ErrorMessages
from nms_shared.utils import match_permissions
from typing import Dict, Tuple, Optional, List

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
    "recovery": lambda : _("Recover"),
    "replace": lambda : _("Replace"),
    "get_info": lambda : _("Get Information"),

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
    return match_permissions(user_permissions,perm)

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

        current[lang_key(parts[-1])] = (key.replace('.','-'),value)

    return result

def widget_user_account() -> Optional[Tuple[str,str]]:
    user = session.get("user")
    user_permissions = {p.value:check_permission(user,p) for p in sorted([x for x in UserPermissions],key=lambda y:y.value)}

    user_permissions = nest_permissions(user_permissions)

    return render_widget("account",user=user,user_permissions=user_permissions)

def widget_user_account_admin(user:dict,move_to_users:List[dict]) -> Tuple[str,str]:
    user_permissions = {p.value:check_permission(user,p) for p in sorted([x for x in UserPermissions],key=lambda y:y.value)}

    user_permissions = nest_permissions(user_permissions)

    return render_widget("account_admin",
                         user=user,
                         user_permissions=user_permissions,
                         move_to_users=move_to_users)

def widget_access_services() -> Optional[Tuple[str,str]]:
    user = session.get("user")

    selected_services = ['ssh','smb']

    permissions = {
        service: UserPermissions[f'SERVICES_{service.upper()}_ACCESS'] for service in selected_services
    }

    forms = {}

    for s,p in permissions.items():
        if (check_permission(user,p)):
            forms[s] = ChangePasswordForm()

    if (len(forms) == 0):
        return None

    return render_widget("account_services",forms=forms)

def widget_access_services_admin(user:dict) -> Optional[Tuple[str,str]]:
    selected_services = ['ssh','smb']

    permissions = {
        service: UserPermissions[f'SERVICES_{service.upper()}_ACCESS'] for service in selected_services
    }

    forms = {}

    for s,p in permissions.items():
        if (check_permission(user,p)):
            forms[s] = ChangePasswordForm()

    if (len(forms) == 0):
        return None

    return render_widget("user_admin_services",forms=forms,user=user)

@bp.route("/account")
def user_account() -> str:
    widgets = [
        widget_user_account(),
        widget_access_services(),
    ]

    return render_template("account.html",
                           csp_nonce=g.csp_nonce,
                           widgets=get_widgets_html(widgets),
                           extra_css=get_widgets_css_files(widgets)
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

@bp.route("/users",methods=["GET"])
def users() -> str:

    widgets = []
    all_users = BACKEND.users
    user = None


    query = request.args.get("q")
    if (query is not None):
        for u in all_users:
            if (query == u.get("username")):
                user = u
                break

        if (user is not None):
            move_to_users = [u for u in all_users if u.get("username") != user.get("username")]
            widgets = [
                widget_user_account_admin(user,move_to_users),
                widget_access_services_admin(user),
            ]
        else:
            show_flash(code=ErrorMessages.E_USER_NOT_FOUND.name, params=[query])


    return render_template("users.html",
                           users = all_users,
                           widgets=get_widgets_html(widgets),
                           extra_css=get_widgets_css_files(widgets),
                           csp_nonce=g.csp_nonce
    )

@bp.route("/users/add",methods=["GET"])
def add_user() -> str:

    all_permissions = {p.value:False for p in UserPermissions}

    return render_template("user.add.html",
                           all_permissions = nest_permissions(all_permissions),
                           csp_nonce=g.csp_nonce
    )


@bp.route("/users/quota",methods=["POST"])
def user_quota() -> Response:
    username = request.form.get("username")

    try:
        validate_csrf(request.form.get("csrf_token"))
    except ValidationError:
        show_flash(code=ErrorMessages.E_CSRF.name)
    else:

        new_quota = request.form.get("quota")

        BACKEND.set_user_quota(username,new_quota)

    return redirect(url_for("main.users",q=username))

@bp.route("/users/username",methods=["POST"])
def change_username() -> Response:
    username = request.form.get("username")

    try:
        validate_csrf(request.form.get("csrf_token"))
    except ValidationError:
        show_flash(code=ErrorMessages.E_CSRF.name)
    else:

        new_username = request.form.get("new_username")

        BACKEND.change_username(username,new_username)

        return redirect(url_for("main.users", q=new_username))

    return redirect(url_for("main.users",q=username))


@bp.route("/users/sudo",methods=["POST"])
def set_sudo() -> Response:
    username = request.form.get("username")

    try:
        validate_csrf(request.form.get("csrf_token"))
    except ValidationError:
        show_flash(code=ErrorMessages.E_CSRF.name)
    else:
        sudo = request.form.get("sudo",False)
        BACKEND.set_sudo(username,sudo)


    return redirect(url_for("main.users",q=username))

@bp.route("/users/permissions",methods=["POST"])
def set_user_permissions() -> Response:
    try:
        validate_csrf(request.form.get("csrf_token"))
    except ValidationError:
        show_flash(code=ErrorMessages.E_CSRF.name)
    else:
        username = request.form.get("username")
        permissions = [p.split("--")[1].replace("-",".") for p in request.form if p.startswith("switch--")]

        BACKEND.set_permissions(username,permissions)

        return redirect(url_for("main.users", q=username))

    return redirect(url_for("main.users"))

@bp.route("/users/new",methods=["POST"])
def new_user() -> Response:
    try:
        validate_csrf(request.form.get("csrf_token"))
    except ValidationError:
        show_flash(code=ErrorMessages.E_CSRF.name)
    else:
        username = request.form.get("username")
        fullname = request.form.get("fullname")
        quota = request.form.get("quota")
        sudo = request.form.get("sudo", False)

        permissions = [p.split("--")[1].replace("-",".") for p in request.form if p.startswith("switch--")]


        BACKEND.new_user(username,fullname,quota,sudo,permissions)

        return redirect(url_for("main.users", q=username))

    return redirect(url_for("main.users"))

@bp.route("/users/delete",methods=["POST"])
def del_user() -> Response:
    try:
        validate_csrf(request.form.get("csrf_token"))
    except ValidationError:
        show_flash(code=ErrorMessages.E_CSRF.name)
    else:
        username = request.form.get("username")
        home_files = request.form.get("user_file")
        move_to = request.form.get("move_to_user",None)


        BACKEND.delete_user(username,home_files,move_to)

    return redirect(url_for("main.users"))

@bp.route("/users/service/<string:service>",methods=["POST"])
def user_service_account_admin(service:str):
    form_data = request.form
    user = form_data.get("username")

    form = ChangePasswordForm()

    if (form.validate_on_submit()):
        BACKEND.change_password_to_service(service,user,form.password.data)
        return redirect(url_for("main.users", q=user))
    else:
        for errors in form.errors.values():
            for error in errors:
                flash(error,"error")

    return redirect(url_for("main.users"))

@bp.route("/users/reset",methods=["POST"])
def reset_otp():
    form_data = request.form
    username = form_data.get("username")

    try:
        validate_csrf(request.form.get("csrf_token"))
    except ValidationError:
        show_flash(code=ErrorMessages.E_CSRF.name)
    else:
        BACKEND.reset_otp(username)
        return redirect(url_for("main.users", q=username))

    return redirect(url_for("main.users"))