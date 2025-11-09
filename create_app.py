import os

from celery import Celery, Task
from flask import Flask, g
from flask_wtf import CSRFProtect
import base64

from filters import human_readable_bytes, enabled_fmt,disk_charm
from nms import bp

def generate_nonce(length=16):
    return base64.b64encode(os.urandom(length)).decode('ascii').rstrip('=')

def create_flask_app():
    app = Flask("NMS")
    app.register_blueprint(bp)
    app.config.from_mapping(
        CELERY=dict(
            broker_url="redis://localhost:6379/0",
            result_backend="redis://localhost:6379/1",
        ),
    )

    app.add_template_filter(human_readable_bytes,"human_readable_bytes")
    app.add_template_filter(enabled_fmt, "enabled_fmt")
    app.add_template_filter(disk_charm, "disk_charm")

    app.secret_key = os.environ.get("NMS_SECRET_KEY")

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

    csrf = CSRFProtect(app)

    celery_init_app(app)

    return app


def celery_init_app(app):
    class FlaskTask(Task):
        def __call__(self, *args: object, **kwargs: object) -> object:
            with app.app_context():
                return self.run(*args, **kwargs)

    celery_app = Celery(app.name, task_cls=FlaskTask)
    celery_app.config_from_object(app.config["CELERY"])
    celery_app.set_default()
    app.extensions["celery"] = celery_app
    return celery_app