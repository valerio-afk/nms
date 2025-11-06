from celery import Celery, Task
from flask import Flask

from filters import human_readable_bytes, enabled_fmt,disk_charm
from nms import bp

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

    app.secret_key = "5dkD$RhJ2#y^%9nJyZMWsmR*aZZFB3z^jKgpr@X6dmgbgpRGHH4HEpstPHs&QDcW"

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