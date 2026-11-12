"""
egalyx/garde_mot_de_passe.py — CORRECTIF DE SÉCURITÉ : un mauvais mot de passe était accepté.

User.check_password renvoie un couple (succès, message). Or toutes les pages l'utilisent comme un oui/non
(« if user and user.check_password(...) ») : en Python un couple non vide est TOUJOURS vrai, donc n'importe quel mot de
passe ouvrait la session (connexion, changement de mot de passe, confirmation de signature…).

Correctif : le résultat devient un couple qui vaut aussi True/False dans un « if » (ResultatMotDePasse). Il est posé
ici au démarrage, quelle que soit la version de models.py, et un contrôle vérifie au démarrage qu'un mauvais mot de
passe est bien refusé (sinon le serveur refuse de démarrer plutôt que d'ouvrir les comptes).
"""
import functools
import logging

journal = logging.getLogger(__name__)


class ResultatMotDePasse(tuple):
    """(succès, message) — se dépaquette comme avant et vaut succès dans un « if »."""

    def __new__(cls, succes, message=''):
        return super().__new__(cls, (bool(succes), message))

    def __bool__(self):
        return self[0]

    @property
    def succes(self):
        return self[0]

    @property
    def message(self):
        return self[1]


def corriger(User):
    origine = User.check_password
    if getattr(origine, '_egalyx_garde', False):
        return

    @functools.wraps(origine)
    def check_password(self, password):
        r = origine(self, password)
        if isinstance(r, ResultatMotDePasse):
            return r
        if isinstance(r, tuple):
            return ResultatMotDePasse(r[0] if r else False, r[1] if len(r) > 1 else '')
        return ResultatMotDePasse(bool(r), '' if r else 'Nom d\'utilisateur ou mot de passe incorrect')

    check_password._egalyx_garde = True
    User.check_password = check_password


def controle(User):
    """Un mauvais mot de passe doit être refusé, le bon accepté (sur un utilisateur en mémoire, jamais enregistré)."""
    from werkzeug.security import generate_password_hash
    u = User()
    u.password_hash = generate_password_hash('Controle-Egalyx-42!')
    for attr, val in (('is_blocked', False), ('locked_until', None), ('failed_login_attempts', 0)):
        if hasattr(User, attr):
            setattr(u, attr, val)
    if bool(u.check_password('mauvais-mot-de-passe')):
        raise RuntimeError('SÉCURITÉ : un mauvais mot de passe est accepté par User.check_password — démarrage arrêté.')
    if not bool(u.check_password('Controle-Egalyx-42!')):
        raise RuntimeError('SÉCURITÉ : le bon mot de passe est refusé par User.check_password — démarrage arrêté.')


def enregistrer(app):
    import models
    corriger(models.User)
    with app.app_context():
        controle(models.User)
    journal.info('Contrôle des mots de passe : mauvais mot de passe refusé, bon mot de passe accepté.')
