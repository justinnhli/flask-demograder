from flask import Blueprint, render_template, url_for, redirect, session
from authlib.integrations.flask_client import OAuth

from .models import db, User

blueprint = Blueprint(name='auth', import_name='auth')

oauth = OAuth()


@blueprint.route('/login')
def login():
    redirect_uri = url_for('auth.login_redirect', _external=True)
    return oauth.google.authorize_redirect(redirect_uri)


@blueprint.route('/login-redirect')
def login_redirect():
    token = oauth.google.authorize_access_token()
    user_info = oauth.google.parse_id_token(token)
    # get the user's email address
    user_email = user_info.get('email', 'user@example.com')
    # find or create the user
    user = User.query.filter(User.email == user_email).first()
    if not user or not user.logged_in:
        if 'nickname' in user_info:
            preferred_name = user_info['nickname']
        elif 'given_name' in user_info:
            preferred_name = user_info['given_name']
        else:
            preferred_name = 'PREFERRED_NAME_PLACEHOLDER'
        family_name = user_info.get('family_name', 'FAMILY_NAME_PLACEHOLDER')
        if user:
            user.preferred_name = preferred_name
            user.family_name = family_name
        else:
            user = User(
                preferred_name=preferred_name,
                family_name=family_name,
                email=user_email,
            )
        user.logged_in = True
        db.session.add(user)
        db.session.commit()
    session['user_email'] = user_email
    return redirect('/')


@blueprint.route('/logout')
def logout():
    session.pop('user_email')
    return redirect('/')
