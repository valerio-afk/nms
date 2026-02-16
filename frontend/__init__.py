from .api.backend_proxy import NMSBACKEND, show_flash
from .utils.exception import NotAuthenticatedError
from flask import Blueprint, flash, session, redirect, Response ,url_for, request, render_template
from flask_babel import get_locale
from nms_shared import constants
from nms_shared.enums import DiskStatus, UserPermissions
from nms_shared.msg import ErrorMessages, WarningMessages, ERROR_MESSAGES, WARNING_MESSAGES
from nms_shared.utils import  match_permissions
from typing import Optional, Tuple
from urllib.parse import urlparse,urlencode
import time

frontend:Blueprint = Blueprint('main',__name__)

@frontend.before_request
def check_scrub_status() -> None:
    NMSBACKEND.get_tasks_by_metadata("scrub")
    # this operation will also deal with flash msg and whatnots
    # no further operation is required

@frontend.before_request
def check_pool_warnings() -> None:
    if (not NMSBACKEND.is_authenticated):
        return

    msgid = NMSBACKEND.pool_status_id
    if (msgid is not None):
        code = constants.MSGID.get(msgid,None)
        if (code is not None):
            if (isinstance(code,ErrorMessages)):
                flash(ERROR_MESSAGES[code](),"error")
            elif (isinstance(code,WarningMessages)):
                flash(WARNING_MESSAGES[code](), "warning")

    disks = NMSBACKEND.pool_disks

    if (any(d.status == DiskStatus.OFFLINE for d in disks)):
        show_flash(type="warning",code=WarningMessages.W_POOL_DISK_OFFLINE.name)


@frontend.before_request
def detect_and_set_language() -> Optional[Response]:
    lang = request.args.get("lang")
    # lang_cookie = request.cookies.get("lang")
    #raise Exception("detect_and_set_language")

    if lang:
        # Build a clean URL without the lang query param
        args = request.args.to_dict()
        args.pop("lang")


        clean_url = request.path
        if args:
            clean_url += "?" + urlencode(args)

        # Redirect to clean URL, setting cookie in response
        resp = redirect(clean_url)
        resp.set_cookie("lang", lang, max_age=60*60*24*365)  # 1 year
        return resp


@frontend.before_request
def require_login() -> Optional[Response]:
    last_activity = session.get("last_activity",None)

    if (last_activity is not None):
        current_time = time.time()
        if ((current_time - last_activity) > (60*30)):
            session.clear()
        else:
            session["last_activity"] = current_time


    if request.endpoint not in ("main.login", "static","main.configure_otp","main.otp_qr"):
        if (not NMSBACKEND.is_authenticated):
            return handle_token_expired(None)



@frontend.before_request
def resilvering_ongoing() -> Optional[Response]:
    wait_endpoint = "main.replace_disk_wait"

    skip_endpoints = ["main.check_tasks", "main.check_task_by_id", wait_endpoint]

    if (request.endpoint in skip_endpoints):
        return None

    tasks = NMSBACKEND.get_tasks_by_metadata("resilver")

    if len(tasks) > 0:
        return redirect(url_for(wait_endpoint))

@frontend.context_processor
def user_data():
    initials = None

    if ((user:=session.get("user")) is not None):
        if (user.get("initials") is None):
            if ((initials := user.get("visible_name")) is None):
                if ((initials := user.get("username")) is not None):
                    initials = initials[:2]

            else:
                parts = initials.split(" ")
                if (len(parts) >= 2):
                    initials = f"{parts[0][0]}{parts[-1][0]}"
                else:
                    initials = initials[:2]

            initials = initials.upper() if initials is not None else "?"
            user['initials'] = initials

        if (user.get("main_pages") is None):
            p = user.get("permissions",[])
            user['main_pages'] = {
                "disks": match_permissions(p,UserPermissions.CLIENT_DASHBOARD_DISKS),
                "network": match_permissions(p, UserPermissions.CLIENT_DASHBOARD_NETWORKS),
                "users": match_permissions(p, UserPermissions.CLIENT_DASHBOARD_USERS),
                "access": match_permissions(p, UserPermissions.CLIENT_DASHBOARD_ACCESS),
                "advanced": match_permissions(p,UserPermissions.CLIENT_DASHBOARD_ADVANCED),
            }



    return dict(
        current_user=user

    )


@frontend.after_request
def no_cache(response) -> Response:
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

@frontend.context_processor
def set_language_frontend() -> dict:
    current_locale = get_locale()
    current_lang = current_locale.language if current_locale is not None else "en"

    def language_url(lang:str='en')-> str:
        args = request.args.to_dict()
        args.update(lang=lang)
        return url_for(
            request.endpoint,
            **(request.view_args or {}),
            **args
        )

    return {
        "langs": constants.LANGS,
        "current_language": constants.LANGS[current_lang][0],
        "language_url" : language_url,
    }


@frontend.errorhandler(NotAuthenticatedError)
def handle_token_expired(_) -> Response:
    session.clear()

    redirection = request.full_path
    parsed = urlparse(redirection)

    redirect_params = {}

    if (parsed.path != url_for('main.login')):
        redirect_params["next"] = parsed.path

    return redirect(url_for("main.login", **redirect_params))


@frontend.errorhandler(401)
def unauthorized(_) -> Tuple[str,int]:
    return render_template("401.html"), 401

from . import dashboard, services, disks, utilities, auth, advanced, network, users