import time
from typing import Optional

from flask import Blueprint, flash, session, redirect, Response ,url_for, request
from backend import NMSBackend, LogFilter, NMSTask

BACKEND:NMSBackend = NMSBackend()
frontend:Blueprint = Blueprint('main',__name__)


@frontend.before_request
def check_flash_messages_from_tasks() -> None:
    tasks = BACKEND.pop_completed_tasks()

    reload_config = False

    for t in tasks:
        flash(t.result,"success" if t.successful else "error")
        reload_config = True


    if (reload_config):
        BACKEND.load_configuration_file()

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
            return redirect(url_for("main.login"))


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

from . import dashboard, access, disks, utilities, auth, advanced