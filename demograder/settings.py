import os
import pathlib

APP_PATH = pathlib.Path(__file__).expanduser().resolve().parent

SQLALCHEMY_DATABASE_PATH = str(APP_PATH / 'database.sqlite')
SQLALCHEMY_DATABASE_URI = 'sqlite:///' + SQLALCHEMY_DATABASE_PATH
SQLALCHEMY_TRACK_MODIFICATIONS = False

SUBMISSION_PATH = APP_PATH / 'submissions'
SUBMISSION_PATH.mkdir(exist_ok=True)

OAUTH_URL = 'https://accounts.google.com/.well-known/openid-configuration'

FLASK_SECRET_KEY = os.environ['FLASK_SECRET_KEY']
GOOGLE_CLIENT_ID = os.environ['GOOGLE_CLIENT_ID']
GOOGLE_CLIENT_SECRET = os.environ['GOOGLE_CLIENT_SECRET']
