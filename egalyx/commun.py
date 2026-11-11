"""
egalyx/commun.py — outils partagés par les modules ajoutés en v4.

Aucun import de app.py ici (évite les imports circulaires) : les modèles sont
importés depuis models.py au moment de l'appel.
"""
from functools import wraps

from flask import abort, flash, redirect, request, session, url_for, current_app
from flask_login import current_user


# --------------------------------------------------------------------- rôles
def est_super_admin(u=None):
    u = u or current_user
    return bool(getattr(u, 'is_authenticated', False) and getattr(u, 'role', None) == 'super_admin')


def est_admin_client(u=None):
    """Administrateur de son organisation (ou super admin)."""
    u = u or current_user
    if not getattr(u, 'is_authenticated', False):
        return False
    return getattr(u, 'role', None) in ('admin', 'super_admin') or bool(getattr(u, 'is_client_admin', False))


def client_id_courant():
    """Organisation sur laquelle on travaille : celle de l'utilisateur, ou celle que le super admin consulte."""
    if not getattr(current_user, 'is_authenticated', False):
        return None
    if est_super_admin():
        cid = request.args.get('client_id', type=int) or session.get('viewing_client_id')
        return cid or getattr(current_user, 'client_id', None)
    return getattr(current_user, 'client_id', None)


# --------------------------------------------------------------- décorateurs
def connexion_requise(f):
    @wraps(f)
    def enveloppe(*a, **k):
        if not getattr(current_user, 'is_authenticated', False):
            return redirect(url_for('login', next=request.full_path))
        return f(*a, **k)
    return enveloppe


def client_requis(f):
    """Connexion + organisation identifiée (sinon : message clair, pas de plantage)."""
    @wraps(f)
    @connexion_requise
    def enveloppe(*a, **k):
        if not client_id_courant():
            flash("Sélectionnez d'abord une organisation à consulter.", 'warning')
            return redirect(url_for('dashboard'))
        return f(*a, **k)
    return enveloppe


def admin_client_requis(f):
    @wraps(f)
    @client_requis
    def enveloppe(*a, **k):
        if not est_admin_client():
            flash("Accès réservé aux administrateurs de l'organisation.", 'danger')
            return redirect(url_for('dashboard'))
        return f(*a, **k)
    return enveloppe


def super_admin_requis(f):
    @wraps(f)
    @connexion_requise
    def enveloppe(*a, **k):
        if not est_super_admin():
            abort(404)
        return f(*a, **k)
    return enveloppe


# ------------------------------------------------------------------- divers
def adresse_ip():
    fwd = request.headers.get('X-Forwarded-For', '')
    return (fwd.split(',')[0].strip() if fwd else request.remote_addr) or ''


def journaliser(action, details=None, client_id=None):
    """Trace dans journal_activite_client ; ne fait jamais échouer l'action principale."""
    try:
        from models import db, JournalActiviteClient
        cid = client_id or client_id_courant()
        if not cid:
            return
        db.session.add(JournalActiviteClient(
            client_id=cid,
            utilisateur_id=getattr(current_user, 'id', None) if getattr(current_user, 'is_authenticated', False) else None,
            action=action[:100], details=details or {},
            ip_address=adresse_ip()[:45], user_agent=(request.user_agent.string or '')[:500]))
    except Exception as e:  # pragma: no cover
        current_app.logger.warning(f"Journalisation impossible ({action}) : {e}")


def envoyer_courriel(destinataire, sujet, texte, html=None):
    """Passe par le service d'e-mail de l'application (egalyx/courriel.py). Retourne True/False."""
    try:
        from egalyx.courriel import envoyer
        return envoyer(destinataire, sujet, texte, html)
    except Exception as e:
        current_app.logger.warning(f"Courriel non envoyé à {destinataire} : {e}")
        return False


def entier(valeur, defaut=None, mini=None, maxi=None):
    try:
        v = int(str(valeur).strip())
    except (TypeError, ValueError):
        return defaut
    if mini is not None and v < mini:
        return defaut
    if maxi is not None and v > maxi:
        return defaut
    return v


def decimal(valeur, defaut=None):
    try:
        return float(str(valeur).replace(' ', '').replace(' ', '').replace(',', '.'))
    except (TypeError, ValueError):
        return defaut


# --------------------------------------------------------------- permissions de l'application
def a_permission(*permissions, u=None):
    """Vrai si l'utilisateur a AU MOINS UNE des permissions (système de permissions de models.User).
    Le super admin a tout ; un utilisateur sans méthode has_permission n'a rien."""
    u = u or current_user
    if not getattr(u, 'is_authenticated', False):
        return False
    if getattr(u, 'role', None) == 'super_admin':
        return True
    verifier = getattr(u, 'has_permission', None)
    if not callable(verifier):
        return False
    return any(verifier(p) for p in permissions)


def permission_requise(*permissions):
    """Connexion + organisation + au moins une des permissions. Sinon : message, ou 403 pour les appels JSON."""
    def deco(f):
        @wraps(f)
        @client_requis
        def enveloppe(*a, **k):
            if not a_permission(*permissions):
                if request.path.startswith('/api/') or request.is_json:
                    from flask import jsonify
                    return jsonify({'erreur': 'permission_insuffisante'}), 403
                flash("Vous n'avez pas la permission d'accéder à cette fonctionnalité. "
                      "Demandez-la à l'administrateur de votre organisation.", 'warning')
                return redirect(url_for('dashboard'))
            return f(*a, **k)
        return enveloppe
    return deco


def jeton_lien_valide():
    """Action déclenchée par un lien (GET) : exige le jeton CSRF dans l'adresse (?csrf_token=…)."""
    try:
        from flask_wtf.csrf import validate_csrf
        validate_csrf(request.args.get('csrf_token') or '')
        return True
    except Exception:
        return False


# ---------------------------------------------------------------- ancien contrôle des permissions d'app.py
# check_permissions_middleware (app.py) associe en dur une page à UNE permission (ex. détail d'un incident =
# « Gérer les incidents »). Les modules refondus (incidents, signalements, PCA, qualité) appliquent leur propre
# grille de droits, plus fine : leurs pages sont retirées de cet ancien contrôle.
ENDPOINTS_GERES = set()


def exempter_controle_ancien(app, endpoints):
    ENDPOINTS_GERES.update(endpoints)
    liste = app.before_request_funcs.setdefault(None, [])
    for i, f in enumerate(liste):
        nom = getattr(f, '__name__', '')
        if nom in ('check_permissions_middleware', 'check_permissions_middleware_complete') \
                and not getattr(f, '_egalyx', False):
            def enveloppe(_f=f):
                if request.endpoint in ENDPOINTS_GERES:
                    return None
                return _f()
            enveloppe.__name__ = nom
            enveloppe._egalyx = True
            liste[i] = enveloppe
