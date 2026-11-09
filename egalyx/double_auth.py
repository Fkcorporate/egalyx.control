"""
egalyx/double_auth.py — double authentification (TOTP, RFC 6238) et page « Sécurité du compte ».

- Activation : clé + QR code à scanner (Google Authenticator, Microsoft Authenticator,
  FreeOTP…), confirmation par un premier code, 8 codes de secours affichés une seule fois
  (seule leur empreinte est conservée).
- Après chaque connexion (mot de passe, cookie « se souvenir », SSO), un code est exigé
  avant tout accès ; 5 erreurs => déconnexion.
- Administrateurs : 2FA obligatoire (EGALYX_2FA_OBLIGATOIRE_ADMINS=0 pour désactiver).
- Un administrateur peut réinitialiser la 2FA d'un utilisateur de son organisation
  (téléphone perdu) ; l'utilisateur la réactive à sa connexion suivante.
"""
import os
from datetime import datetime

from flask import (Blueprint, flash, jsonify, redirect, render_template, request,
                   session, url_for)
from flask_login import current_user, logout_user, user_logged_in, user_logged_out
from werkzeug.security import check_password_hash, generate_password_hash

from egalyx import calculs
from egalyx.commun import connexion_requise, est_admin_client, est_super_admin, journaliser

bp = Blueprint('securite_compte', __name__, url_prefix='/compte/securite')

CLE_SESSION = '2fa_uid'                  # id de l'utilisateur dont la 2FA a été validée dans cette session
CLE_TENTATIVES = '2fa_tentatives'
CLE_SECRET_PROVISOIRE = '2fa_secret_provisoire'
CLE_CODES_A_AFFICHER = '2fa_codes_affichage'
MAX_TENTATIVES = 5

# Pages accessibles tant que la 2FA n'est pas validée / pas encore activée
_LIBRES = {'static', 'logout', 'login', 'login_fullscreen', 'home',
           'securite_compte.verification', 'securite_compte.activer', 'securite_compte.codes_secours',
           'securite_compte.index'}


def obligatoire_pour(u):
    if os.environ.get('EGALYX_2FA_OBLIGATOIRE_ADMINS', '1') != '1':
        return False
    return est_admin_client(u)


def _secret(u):
    from models import dechiffrer_secret
    return dechiffrer_secret(u.totp_secret_chiffre) if u.totp_secret_chiffre else None


def _nom_compte(u):
    return getattr(u, 'email', None) or getattr(u, 'username', 'compte')


def verifier_code(u, code):
    """Code TOTP ou code de secours. Met à jour l'utilisateur (sans commit). Retourne 'totp', 'secours' ou None."""
    from models import marquer_json_modifie
    code = (code or '').strip()
    secret = _secret(u)
    if secret:
        pas = calculs.totp_verifier(secret, code, u.totp_dernier_pas)
        if pas is not None:
            u.totp_dernier_pas = pas
            return 'totp'
    normalise = calculs.normaliser_code_secours(code)
    if len(normalise) == 8:
        restants = list(u.totp_codes_secours or [])
        for i, empreinte in enumerate(restants):
            if check_password_hash(empreinte, normalise):
                restants.pop(i)
                u.totp_codes_secours = restants
                marquer_json_modifie(u, 'totp_codes_secours')
                return 'secours'
    return None


def _nouveaux_codes(u):
    from models import marquer_json_modifie
    codes = calculs.codes_secours(8)
    u.totp_codes_secours = [generate_password_hash(calculs.normaliser_code_secours(c)) for c in codes]
    marquer_json_modifie(u, 'totp_codes_secours')
    return codes


def _destination_apres():
    cible = session.pop('2fa_suite', None)
    if cible and cible.startswith('/') and not cible.startswith('//'):
        return cible
    return url_for('dashboard')


# ------------------------------------------------------------------ garde globale
def garde_double_auth():
    if not getattr(current_user, 'is_authenticated', False):
        return None
    ep = request.endpoint or ''
    if ep in _LIBRES or ep.startswith('sso.') or ep.endswith('.static'):
        return None
    json_attendu = request.path.startswith('/api/') or request.is_json or \
        'application/json' in (request.headers.get('Accept') or '')
    if getattr(current_user, 'totp_actif', False):
        if session.get(CLE_SESSION) == current_user.id:
            return None
        if json_attendu:
            return jsonify({'erreur': 'double_authentification_requise'}), 401
        if request.method == 'GET':
            session['2fa_suite'] = request.full_path.rstrip('?')
        return redirect(url_for('securite_compte.verification'))
    if obligatoire_pour(current_user) and not session.get('auth_sso'):   # SSO : MFA assurée par le fournisseur
        if json_attendu:
            return jsonify({'erreur': 'double_authentification_a_activer'}), 403
        flash("Votre rôle d'administrateur exige la double authentification. Activez-la pour continuer.", 'warning')
        return redirect(url_for('securite_compte.activer'))
    return None


def _a_la_connexion(sender, user, **extra):
    session.pop(CLE_SESSION, None)
    session.pop(CLE_TENTATIVES, None)
    session.pop('auth_sso', None)


def _a_la_deconnexion(sender, user, **extra):
    for k in (CLE_SESSION, CLE_TENTATIVES, CLE_SECRET_PROVISOIRE, CLE_CODES_A_AFFICHER, '2fa_suite', 'auth_sso'):
        session.pop(k, None)


def valider_session(u):
    """À appeler après une vérification réussie (ou par le SSO si la 2FA n'est pas activée)."""
    session[CLE_SESSION] = u.id
    session.pop(CLE_TENTATIVES, None)


# ------------------------------------------------------------------ pages
@bp.route('/')
@connexion_requise
def index():
    from egalyx import sso
    return render_template('egalyx/securite_compte.html',
                           u=current_user, obligatoire=obligatoire_pour(current_user),
                           codes_restants=len(current_user.totp_codes_secours or []),
                           fournisseurs_sso=sso.fournisseurs_actifs())


@bp.route('/2fa/activer', methods=['GET', 'POST'])
@connexion_requise
def activer():
    from models import db, chiffrer_secret
    u = current_user
    if u.totp_actif:
        return redirect(url_for('.index'))
    secret = session.get(CLE_SECRET_PROVISOIRE)
    if not secret:
        secret = calculs.totp_nouveau_secret()
        session[CLE_SECRET_PROVISOIRE] = secret
    if request.method == 'POST':
        pas = calculs.totp_verifier(secret, request.form.get('code'))
        if pas is None:
            flash("Code incorrect. Vérifiez l'heure de votre téléphone et réessayez.", 'danger')
        else:
            u.totp_secret_chiffre = chiffrer_secret(secret)
            u.totp_actif = True
            u.totp_active_le = datetime.utcnow()
            u.totp_dernier_pas = pas
            codes = _nouveaux_codes(u)
            journaliser('2fa_activee', {'utilisateur': u.id})
            db.session.commit()
            session.pop(CLE_SECRET_PROVISOIRE, None)
            valider_session(u)
            session[CLE_CODES_A_AFFICHER] = codes
            flash('Double authentification activée.', 'success')
            return redirect(url_for('.codes_secours'))
    return render_template('egalyx/2fa_activer.html', secret=secret,
                           uri=calculs.totp_uri(secret, _nom_compte(u)),
                           obligatoire=obligatoire_pour(u))


@bp.route('/2fa/codes-secours', methods=['GET', 'POST'])
@connexion_requise
def codes_secours():
    """Affiche une seule fois les nouveaux codes ; POST = en générer de nouveaux (code TOTP exigé)."""
    from models import db
    u = current_user
    if not u.totp_actif:
        return redirect(url_for('.activer'))
    if request.method == 'POST':
        if session.get(CLE_SESSION) != u.id or verifier_code(u, request.form.get('code')) != 'totp':
            flash("Code de l'application incorrect.", 'danger')
            return redirect(url_for('.index'))
        session[CLE_CODES_A_AFFICHER] = _nouveaux_codes(u)
        journaliser('2fa_codes_regeneres', {'utilisateur': u.id})
        db.session.commit()
        return redirect(url_for('.codes_secours'))
    codes = session.pop(CLE_CODES_A_AFFICHER, None)
    if not codes:
        return redirect(url_for('.index'))
    return render_template('egalyx/2fa_codes.html', codes=codes)


@bp.route('/2fa/verification', methods=['GET', 'POST'])
@connexion_requise
def verification():
    from models import db
    u = current_user
    if not u.totp_actif or session.get(CLE_SESSION) == u.id:
        return redirect(_destination_apres())
    if request.method == 'POST':
        methode = verifier_code(u, request.form.get('code'))
        if methode:
            db.session.commit()
            valider_session(u)
            if methode == 'secours':
                n = len(u.totp_codes_secours or [])
                flash(f"Code de secours utilisé. Il vous en reste {n}." +
                      (" Générez-en de nouveaux." if n <= 2 else ''), 'warning')
            return redirect(_destination_apres())
        session[CLE_TENTATIVES] = session.get(CLE_TENTATIVES, 0) + 1
        if session[CLE_TENTATIVES] >= MAX_TENTATIVES:
            journaliser('2fa_echecs_repetes', {'utilisateur': u.id}, client_id=getattr(u, 'client_id', None))
            db.session.commit()
            logout_user()
            flash('Trop de codes incorrects : vous avez été déconnecté.', 'danger')
            return redirect(url_for('login'))
        flash(f"Code incorrect ({MAX_TENTATIVES - session[CLE_TENTATIVES]} essai(s) restant(s)).", 'danger')
    return render_template('egalyx/2fa_verification.html')


@bp.route('/2fa/desactiver', methods=['POST'])
@connexion_requise
def desactiver():
    from models import db
    u = current_user
    if obligatoire_pour(u):
        flash('La double authentification est obligatoire pour les administrateurs.', 'warning')
        return redirect(url_for('.index'))
    if not u.check_password(request.form.get('mot_de_passe') or '') or verifier_code(u, request.form.get('code')) is None:
        flash('Mot de passe ou code incorrect.', 'danger')
        return redirect(url_for('.index'))
    _reinitialiser(u)
    journaliser('2fa_desactivee', {'utilisateur': u.id})
    db.session.commit()
    flash('Double authentification désactivée.', 'info')
    return redirect(url_for('.index'))


def _reinitialiser(u):
    u.totp_actif = False
    u.totp_secret_chiffre = None
    u.totp_codes_secours = None
    u.totp_dernier_pas = None
    u.totp_active_le = None


@bp.route('/2fa/reinitialiser/<int:user_id>', methods=['POST'])
@connexion_requise
def reinitialiser(user_id):
    """Un administrateur réinitialise la 2FA d'un membre de son organisation (téléphone perdu)."""
    from models import db, User
    cible = db.session.get(User, user_id)
    autorise = cible and (est_super_admin() or (est_admin_client() and cible.client_id == current_user.client_id))
    if not autorise or cible.id == current_user.id:
        flash('Action non autorisée.', 'danger')
        return redirect(request.referrer or url_for('dashboard'))
    _reinitialiser(cible)
    journaliser('2fa_reinitialisee_par_admin', {'utilisateur': cible.id, 'par': current_user.id},
                client_id=cible.client_id)
    db.session.commit()
    flash(f"Double authentification de {cible.username} réinitialisée : elle devra la réactiver.", 'success')
    return redirect(request.referrer or url_for('dashboard'))


def enregistrer(app):
    app.register_blueprint(bp)
    app.before_request(garde_double_auth)
    user_logged_in.connect(_a_la_connexion, app)
    user_logged_out.connect(_a_la_deconnexion, app)
