from pathlib import Path

from flask import Flask

from .models import db
from .auth import oauth, blueprint as auth_blueprint
from .routes import blueprint


def create_app():
    app = Flask(
        __name__,
        root_path=Path(__file__).expanduser().resolve().parent,
    )
    app.config.from_pyfile('settings.py')
    app.secret_key = app.config['FLASK_SECRET_KEY']
    db.init_app(app)
    oauth.init_app(app)
    oauth.register(
        name='google',
        server_metadata_url=app.config['OAUTH_URL'],
        client_kwargs={
            'scope': 'openid email profile',
        }
    )

    app.register_blueprint(blueprint)
    app.register_blueprint(auth_blueprint)
    return app
