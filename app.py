from create_app import create_flask_app

flask_app = create_flask_app()
# celery_app = flask_app.extensions["celery"]

if __name__ == '__main__':
     flask_app.run(host="0.0.0.0",debug=True)