from backend import NMSBackend
from constants import MSGID
from flask import Blueprint, flash, session, redirect, Response ,url_for, request
from flask_babel import get_locale
from typing import Optional
from urllib.parse import urlparse,urlencode
import constants
import time

BACKEND:NMSBackend = NMSBackend()
frontend:Blueprint = Blueprint('main',__name__)


@frontend.before_request
def check_flash_messages_from_tasks() -> None:
    tasks = BACKEND.get_completed_tasks()
    reload_config = False

    for t in tasks:
        msg = str(t.result)

        raise Exception(str(t.result))

        flash(msg,"success" if t.successful else "error")
        reload_config = True


    if (reload_config):
        BACKEND.load_configuration_file()
        BACKEND.remove_completed_tasks()

@frontend.before_request
def check_pool_warnings() -> None:
    msgid = BACKEND.get_pool_status_id()
    if (msgid is not None):
        message = MSGID.get(msgid,None)
        if (message is not None):
            flash(message[1], message[0])

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
def scrub_checker(response) -> Response:

    BACKEND.check_scrub_status()
    return response

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




# @frontend.after_request
# def debug_session(response):
#     BACKEND.logger.error(f"SESSION CONTENT: {session}")
#     return response

from . import dashboard, access, disks, utilities, auth, advanced