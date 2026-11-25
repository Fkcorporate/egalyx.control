"""
egalyx/securite.py — protections communes ajoutées par-dessus l'application.

1. Outils de débogage et pages de test (/debug…, /api/debug/…, /test-…) : fermés en production (404),
   sauf pour un super administrateur connecté. Certains étaient ouverts sans connexion, et l'un d'eux
   écrivait dans les journaux tous les en-têtes reçus, cookie de session compris.
2. Connexion : au plus 20 ÉCHECS de connexion par adresse IP et par 10 minutes (en plus du blocage du compte
   après 10 mots de passe erronés, déjà en place dans models.py). Contre les essais en masse sur plusieurs comptes.
   Seuls les échecs comptent : tout un bureau derrière la même adresse peut se connecter le matin sans être gêné.
3. En-têtes de sécurité complémentaires, choisis pour ne casser aucune page existante :
   Content-Security-Policy (pas d'intégration du site dans un autre, pas de plug-in, formulaires vers le site
   seulement…), Permissions-Policy, Cross-Origin-Opener-Policy.

Désactivation d'urgence, sans redéployer le code : variables d'environnement
  EGALYX_OUTILS_DEBUG=1        → rouvre les outils de débogage à tous les utilisateurs connectés
  EGALYX_LIMITE_CONNEXION=0    → supprime la limite par adresse IP
"""
import os
import re
import threading
import time
from collections import defaultdict, deque

from flask import abort, request

# outils de débogage / pages de test (aucune page de l'application ne les appelle)
_OUTILS = re.compile(
    r'^/(?:'
    r'debug(?:[-_/].*)?'                                  # /debug/…, /debug-routes, /debug_audit_access/…
    r'|api/debug/.*'
    r'|api/test/.*'
    r'|test-[a-z-]+(?:/.*)?'                              # /test-api, /test-formulaire, /test-matrice/…
    r'|super-admin/debug-filter'
    r'|admin/debug-form-action|admin/test-logo'
    r'|api/chronogramme/v2/test'
    r'|api/logigramme/test-fix'
    r'|api/questionnaire/\d+/(?:debug|reponse/test)'
    r'|api/audit/\d+/debug-fichiers'
    r')$')

_LOGIN = {'/login', '/auth/login_fullscreen', '/login-fullscreen', '/login_fullscreen'}   # /auth/login_fullscreen : la vraie page de connexion
_FENETRE, _MAXI = 600, 20
_essais = defaultdict(deque)
_verrou = threading.Lock()


def _production(app):
    return not app.debug and not app.testing


def _ip():
    """Adresse du visiteur : Render la transmet dans X-Forwarded-For (sinon on verrait celle de son proxy)."""
    xff = request.headers.get('X-Forwarded-For', '')
    return (xff.split(',')[0].strip() if xff else '') or request.remote_addr or '?'


def _est_super_admin():
    try:
        from flask_login import current_user
        if not current_user.is_authenticated:
            return False
        sa = getattr(current_user, 'is_super_admin', False)
        sa = sa() if callable(sa) else sa                    # propriété ou méthode selon les versions du modèle
        return bool(sa) or getattr(current_user, 'role', '') == 'super_admin'
    except Exception:  # noqa: BLE001
        return False


def enregistrer(app):
    @app.before_request
    def _garde_securite():
        chemin = request.path.rstrip('/') or '/'
        # 1. outils de débogage
        if _production(app) and _OUTILS.match(chemin) and os.environ.get('EGALYX_OUTILS_DEBUG') != '1':
            if not _est_super_admin():
                abort(404)
        # 2. tentatives de connexion par adresse IP
        if request.method == 'POST' and chemin in _LOGIN and os.environ.get('EGALYX_LIMITE_CONNEXION', '1') != '0':
            maintenant, cle = time.time(), _ip()
            with _verrou:
                file = _essais[cle]
                while file and maintenant - file[0] > _FENETRE:
                    file.popleft()
                if len(file) >= _MAXI:                       # trop d'ÉCHECS récents depuis cette adresse
                    attente = int(_FENETRE - (maintenant - file[0])) // 60 + 1
                    return (f"<!doctype html><meta charset='utf-8'><title>Trop de tentatives</title>"
                            f"<div style='font-family:sans-serif;max-width:520px;margin:15vh auto;text-align:center'>"
                            f"<h1 style='font-size:1.4rem'>Trop de tentatives de connexion</h1>"
                            f"<p>Par sécurité, réessayez dans {attente} minute{'s' if attente > 1 else ''}.</p>"
                            f"<p><a href='/login'>Retour à la connexion</a></p></div>", 429,
                            {'Retry-After': str(attente * 60)})

    @app.after_request
    def _compter_echecs(reponse):
        # connexion réussie = redirection (302) ; échec = la page de connexion réaffichée (200)
        if (request.method == 'POST' and (request.path.rstrip('/') or '/') in _LOGIN and reponse.status_code == 200
                and os.environ.get('EGALYX_LIMITE_CONNEXION', '1') != '0'):
            with _verrou:
                _essais[_ip()].append(time.time())
                if len(_essais) > 50000:                     # mémoire bornée
                    for k in list(_essais)[:10000]:
                        _essais.pop(k, None)
        return reponse

    @app.after_request
    def _entetes_securite(reponse):
        h = reponse.headers
        # directives sans effet sur les scripts et styles des pages (elles n'interdisent rien de ce que le site utilise)
        h.setdefault('Content-Security-Policy',
                     "frame-ancestors 'self'; base-uri 'self'; object-src 'none'; form-action 'self' https:; upgrade-insecure-requests")
        h.setdefault('Permissions-Policy', 'camera=(self), microphone=(self), geolocation=(self), payment=(), usb=()')
        h.setdefault('Cross-Origin-Opener-Policy', 'same-origin-allow-popups')
        h.pop('X-XSS-Protection', None)                      # en-tête obsolète, déconseillé par les navigateurs actuels
        return reponse
