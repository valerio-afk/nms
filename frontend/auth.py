from nms_shared import ErrorMessages, SuccessMessages
from . import frontend as bp, request, redirect, url_for, session, NMSBACKEND as BACKEND, set_user_main_pages_visibility
from flask import Response, render_template, send_file, g, abort
from flask_wtf.csrf import generate_csrf, validate_csrf, ValidationError
from io import BytesIO
from typing import Union, Tuple
import qrcode
import time

from .api.backend_proxy import show_flash


#MAIN PAGES

@bp.route("/login",methods=['GET','POST'])
def login() -> Union[Response,str]:
    authenticated = False
    temp_token = session.get("temp_token",False)

    first_login_token = request.args.get("token",None)
    is_otp_conf = False

    if (first_login_token):
        if (not BACKEND.verify_first_login_token(first_login_token)):
            is_otp_conf = False
        else:
            abort(401)
    else:
        is_otp_conf = BACKEND.is_otp_configured # to check for admin first time login

    if (is_otp_conf or temp_token):

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
                session["user"] = BACKEND.current_user
                set_user_main_pages_visibility()
                authenticated = True
            elif (not is_otp_conf):
                session.clear()

        elif session.get("authenticated",False):
            authenticated = True

        if authenticated:
            next_url = request.args.get("next")
            return redirect(next_url or url_for("main.dashboard"))


        return render_template("login.auth.html",csp_nonce=g.csp_nonce,csrf_token= generate_csrf())
    else:
        return redirect(url_for("main.configure_otp",token=first_login_token))

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
    token = request.args.get("token")
    uri = BACKEND.get_new_otp(token)


    img = qrcode.make(uri)
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png")


@bp.route("/login/config",methods=['GET','POST'])
def configure_otp() -> Union[Response,str]:
    token = request.args.get("token")

    is_otp_configured = BACKEND.is_otp_configured if token is None else BACKEND.verify_first_login_token(token)

    if (is_otp_configured or (request.method == 'POST')):
        session["temp_token"] = True
        return redirect(url_for("main.login"))

    return render_template("login.otp.html",token=token,csrf_token= generate_csrf())


# ACTION PAGES

@bp.route("/logout",methods=['POST'])
def logout() -> Response:
    BACKEND.logout()
    return redirect(url_for("main.login"))