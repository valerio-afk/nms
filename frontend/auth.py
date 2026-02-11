from nms_shared import ErrorMessages, SuccessMessages
from . import frontend as bp, request, flash, redirect, url_for, session, NMSBACKEND as BACKEND
from flask import Response, render_template, send_file, g
from flask_wtf.csrf import generate_csrf, validate_csrf, ValidationError
from io import BytesIO
from typing import Union, Tuple
import pyotp
import qrcode
import time

from .api.backend_proxy import show_flash


#MAIN PAGES

@bp.route("/login",methods=['GET','POST'])
def login() -> Union[Response,str]:
    authenticated = False
    if (BACKEND.is_otp_configured or BACKEND.is_new_otp_ready):

        if (request.method == 'POST'):

            try:
                validate_csrf(request.form.get("csrf_token"))
            except ValidationError:
                show_flash(code=ErrorMessages.E_CSRF.name)
                return redirect(url_for("main.advanced"))

            otp = request.form.get("otp")

            if (BACKEND.login(otp)):
                session["authenticated"] = True
                session["login_time"] = time.time()
                session["last_activity"] = time.time()
                session["ip"] = request.remote_addr
                authenticated = True

        elif session.get("authenticated",False):
            authenticated = True

        if authenticated:
            next_url = request.args.get("next")
            return redirect(next_url or url_for("main.dashboard"))

        return render_template("login.auth.html",csp_nonce=g.csp_nonce,csrf_token= generate_csrf())
    else:
        return redirect(url_for("main.configure_otp"))

@bp.route("/login/reauth/<string:operation>",methods=['GET','POST'])
def reauth(operation:str) -> Union[Response,str]:

    if (BACKEND.is_otp_configured):

        if (request.method == 'POST'):
            try:
                validate_csrf(request.form.get("csrf_token"))
            except ValidationError:
                show_flash(code=ErrorMessages.E_CSRF.name)
            else:
                otp = request.form.get("otp")

                if (token:=BACKEND.verify_otp(otp,purpose=operation,duration=1)):
                    session["dz_authorisation"] = {"time":time.time(),"timestamp":time.time(),"purpose":operation}
                    BACKEND.set_session_token(operation,token)
                    show_flash(type="success", code=SuccessMessages.S_OTP_DANGEROUS.name)

            return redirect(url_for("main.advanced"))

        return render_template("login.reauth.html",csp_nonce=g.csp_nonce,csrf_token= generate_csrf())
    else:
        return redirect(url_for("main.configure_otp"))

@bp.route("/login/config/show_qrcode")
def otp_qr() -> Union[Response,Tuple[str,int]]:
    uri = BACKEND.get_new_otp()


    img = qrcode.make(uri)
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png")


@bp.route("/login/config",methods=['GET','POST'])
def configure_otp() -> Union[Response,str]:
    if ((BACKEND.is_otp_configured) or (request.method == 'POST')):
        return redirect(url_for("main.login"))


    return render_template("login.otp.html",csrf_token= generate_csrf())


# ACTION PAGES

@bp.route("/logout",methods=['POST'])
def logout() -> Response:
    BACKEND.logout()
    return redirect(url_for("main.login"))