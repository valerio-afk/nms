from asgiref.wsgi import WsgiToAsgi
from frontend.create_app import create_flask_app

flask_app = create_flask_app()
frontend_app = WsgiToAsgi(flask_app)