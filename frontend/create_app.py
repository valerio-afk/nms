from frontend.utils.filters import (human_readable_bytes, enabled_fmt, disk_charm, markdown_filter, smart_label,
                                    boolean_fmt, disk_status_babel, iface_charm)
from flask import Flask, g, request
from flask_babel import Babel
from flask_session import Session
from flask_wtf import CSRFProtect
from frontend import frontend as bp
from nms_shared import constants
import base64
import os
import redis

babel = Babel()

def get_locale():
    lang = request.args.get('lang')
    if lang in constants.LANGS.keys():
        return lang

    lang_cookie = request.cookies.get("lang")

    if lang_cookie in constants.LANGS.keys():
        return lang_cookie

    return 'en'  # default

def generate_nonce(length=16):
    return base64.b64encode(os.urandom(length)).decode('ascii').rstrip('=')

def create_flask_app():
    app = Flask(
        "NMS",
        template_folder="frontend/templates",
        static_folder="frontend/static",
    )
    app.register_blueprint(bp)
    app.config['BABEL_DEFAULT_LOCALE'] = 'en'
    app.config['BABEL_SUPPORTED_LOCALES'] = ['en', 'it']

    app.add_template_filter(human_readable_bytes,"human_readable_bytes")
    app.add_template_filter(enabled_fmt, "enabled_fmt")
    app.add_template_filter(boolean_fmt, "boolean_fmt")
    app.add_template_filter(disk_charm, "disk_charm")
    app.add_template_filter(iface_charm, "iface_charm")
    app.add_template_filter(markdown_filter,"md")
    app.add_template_filter(smart_label,"smart_label")
    app.add_template_filter(disk_status_babel,"disk_status_babel")

    app.secret_key = os.environ.get("NMS_SECRET_KEY")

    if not app.secret_key:
        raise RuntimeError("NMS_SECRET_KEY environment variable is not set")

    app.config.update(
        SESSION_TYPE="redis",
        SESSION_PERMANENT=False,
        SESSION_USE_SIGNER=True,
        SESSION_KEY_PREFIX="flask:session:",

        SESSION_REDIS=redis.Redis(
            host="localhost",
            port=6379,
            db=2,
        ),
    )

    Session(app)


    @app.before_request
    def set_csp_nonce():
        # store nonce for templates
        g.csp_nonce = generate_nonce()

    @app.after_request
    def add_csp_header(response):
        nonce = getattr(g, 'csp_nonce', None)
        if nonce is None:
            return response

        csp = (
            "default-src 'none'; "
            f"script-src 'self' 'nonce-{nonce}'; "
            f"style-src 'self' 'nonce-{nonce}'; "
            "connect-src 'self'; "
            "img-src 'self' data:; "
            "font-src 'self'; "
            "object-src 'none'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self';"
        )
        response.headers['Content-Security-Policy'] = csp
        return response

    CSRFProtect(app)

    babel.init_app(app,locale_selector=get_locale,default_translation_directories="frontend/translations")

    return app
