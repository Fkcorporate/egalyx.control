"""Double minimal de Flask-Login pour les tests (le paquet n'est pas installable dans cet environnement)."""
from blinker import Namespace
from flask import g
from werkzeug.local import LocalProxy

_signaux = Namespace()
user_logged_in = _signaux.signal('logged-in')
user_logged_out = _signaux.signal('logged-out')


class AnonymousUserMixin:
    is_authenticated = False
    is_anonymous = True
    is_active = False
    id = None
    role = None
    client_id = None


class UserMixin:
    is_authenticated = True
    is_anonymous = False


def _utilisateur():
    from flask import session
    uid = session.get('_uid')
    if uid is None:
        return AnonymousUserMixin()
    import models
    return models.User.query.get(uid) or AnonymousUserMixin()


current_user = LocalProxy(_utilisateur)


def login_user(u, remember=False):
    from flask import current_app
    from flask import session
    session['_uid'] = u.id
    user_logged_in.send(current_app._get_current_object(), user=u)
    return True


def logout_user():
    from flask import current_app
    from flask import session
    u = _utilisateur()
    session.pop('_uid', None)
    user_logged_out.send(current_app._get_current_object(), user=u)
    return True


def login_required(f):
    return f


class LoginManager:
    def __init__(self, app=None):
        pass
