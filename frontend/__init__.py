from .api.backend_proxy import NMSBACKEND
from flask import Blueprint, flash, session, redirect, Response ,url_for, request
from flask_babel import get_locale
from nms_shared import constants
from nms_shared.msg import ErrorMessages, WarningMessages, ERROR_MESSAGES, WARNING_MESSAGES
from typing import Optional
from urllib.parse import urlparse,urlencode
import time
from .utils.exception import NotAuthenticatedError

frontend:Blueprint = Blueprint('main',__name__)

@frontend.before_request
def check_scrub_status() -> None:
    NMSBACKEND.get_tasks_by_metadata("scrub")
    # this operation will also deal with flash msg and whatnots
    # no further operation is required

@frontend.before_request
def check_pool_warnings() -> None:
    msgid = NMSBACKEND.pool_status_id
    if (msgid is not None):
        code = constants.MSGID.get(msgid,None)
        if (code is not None):
            if (isinstance(code,ErrorMessages)):
                flash(ERROR_MESSAGES[code](),"error")
            elif (isinstance(code,WarningMessages)):
                flash(WARNING_MESSAGES[code](), "warning")


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
        if session.get("authenticated",False) is not True:
            redirection = request.full_path
            parsed = urlparse(redirection)

            redirect_params = {}

            if (parsed.path != url_for('main.login')):
                redirect_params["next"] = parsed.path

            return redirect(url_for("main.login",**redirect_params))



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
def handle_token_expired(_):
    session.clear()
    return redirect(url_for("main.login"))

# @frontend.after_request
# def debug_session(response):
#     BACKEND.logger.error(f"SESSION CONTENT: {session}")
#     return response

from . import dashboard, services, disks, utilities, auth, advanced