from pathlib import Path

from flask import Flask

from .auth import oauth, blueprint as auth_blueprint
from .models import db
from .routes import blueprint as routes_blueprint


def create_app():
    # create app
    app = Flask(
        __name__,
        root_path=Path(__file__).expanduser().resolve().parent,
    )
    # configure app
    app.config.from_pyfile('settings.py')
    app.secret_key = app.config['FLASK_SECRET_KEY']
    # initialize extensions
    db.init_app(app)
    oauth.init_app(app)
    oauth.register(
        name='google',
        server_metadata_url=app.config['OAUTH_URL'],
        client_kwargs={
            'scope': 'openid email profile',
        }
    )
    # register blueprints
    app.register_blueprint(routes_blueprint)
    app.register_blueprint(auth_blueprint)
    # return
    return app
