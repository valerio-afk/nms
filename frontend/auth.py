import time
import pyotp
import qrcode
from typing import Union, Tuple
from io import BytesIO

from msg import SuccessMessage
from . import frontend as bp, BACKEND, request, flash, redirect, url_for, session
from flask import Response, render_template, send_file, g
from flask_wtf.csrf import generate_csrf, validate_csrf, ValidationError



#MAIN PAGES

@bp.route("/login",methods=['GET','POST'])
def login() -> Union[Response,str]:
    authenticated = False
    if (BACKEND.is_otp_configured):

        if (request.method == 'POST'):

            try:
                validate_csrf(request.form.get("csrf_token"))
            except ValidationError:
                flash("CSRF validation failed", "error")
                return redirect(url_for("main.advanced"))

            otp = request.form.get("otp")

            BACKEND.logger.info(f"Login request. OTP: {otp}")

            if (BACKEND.verify_otp(otp)):
                session["authenticated"] = True
                session["login_time"] = time.time()
                session["last_activity"] = time.time()
                session["ip"] = request.remote_addr
                authenticated = True
                BACKEND.logger.info(f"OTP accepted")
            else:
                BACKEND.logger.warning(f"Invalid OTP")

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
                raise Exception("CSRF validation failed")
                abort(400)

            otp = request.form.get("otp")

            BACKEND.logger.info(f"Login request. OTP: {otp}")

            if (BACKEND.verify_otp(otp)):
                session["dz_authorisation"] = {"time":time.time(),"timestamp":time.time(),"operation":operation}
                BACKEND.logger.info(f"OTP accepted")
                flash(SuccessMessage.get_message(SuccessMessage.S_OTP_DANGEROUS), "success")
            else:
                BACKEND.logger.warning(f"Invalid OTP")
                flash("Invalid OTP","error")



            return redirect(url_for("main.advanced"))

        return render_template("login.reauth.html",csp_nonce=g.csp_nonce,csrf_token= generate_csrf())
    else:
        return redirect(url_for("main.configure_otp"))

@bp.route("/login/config/show_qrcode")
def otp_qr() -> Union[Response,Tuple[str,int]]:
    secret = session.get("pending_otp_secret")
    if not secret:
        return "Setup not started", 400

    totp = pyotp.TOTP(secret)
    uri = totp.provisioning_uri(
        issuer_name="NMS"
    )

    img = qrcode.make(uri)
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png")


@bp.route("/login/config",methods=['GET','POST'])
def configure_otp() -> Union[Response,str]:

    if (BACKEND.is_otp_configured):
        return redirect(url_for("main.login"))

    if (request.method == 'POST'):
        secret = session.get("pending_otp_secret")
        if secret is not None:
            del session['pending_otp_secret']
            BACKEND.set_otp_secret(secret)
            return redirect(url_for("main.login"))


    secret = pyotp.random_base32()
    session['pending_otp_secret'] = secret

    return render_template("login.otp.html",csrf_token= generate_csrf())


# ACTION PAGES

@bp.route("/logout",methods=['POST'])
def logout() -> Response:
    session.clear()
    return redirect(url_for("main.login"))