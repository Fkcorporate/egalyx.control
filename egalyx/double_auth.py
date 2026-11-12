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
           'securite_compte.index', 'securite_compte.guide',
           # fichiers chargés par les pages (traduction, etc.) : sans donnée privée, nécessaires à la page de code
           'langue.dictionnaire', 'langue.changer'}

# Ressources chargées par une page (scripts, styles, images…) : jamais une destination après le code de sécurité.
_EXTENSIONS_RESSOURCES = ('.js', '.css', '.map', '.json', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico', '.webp',
                          '.woff', '.woff2', '.ttf', '.txt', '.xml', '.webmanifest')
_PREFIXES_RESSOURCES = ('/static/', '/langue/', '/api/', '/favicon', '/manifest', '/service-worker', '/sw.js')


def destination_valable(chemin):
    """Vrai seulement pour une page interne vers laquelle on peut revenir après le code de sécurité."""
    if not chemin or not chemin.startswith('/') or chemin.startswith('//'):
        return False
    base = chemin.split('?', 1)[0].lower()
    return not base.endswith(_EXTENSIONS_RESSOURCES) and not base.startswith(_PREFIXES_RESSOURCES)


def _navigation_de_page():
    """Le navigateur ouvre une page (et non un script, une image ou un appel en arrière-plan)."""
    dest = request.headers.get('Sec-Fetch-Dest')
    if dest:
        return dest in ('document', 'iframe')
    return 'text/html' in (request.headers.get('Accept') or 'text/html')


def reglage_organisation(client_id):
    """True si l'organisation exige la double authentification pour TOUS ses utilisateurs."""
    if not client_id:
        return False
    try:
        from models import ClientConfiguration
        conf = ClientConfiguration.query.filter_by(client_id=client_id).first()
        return bool(((conf.preferences or {}).get('securite') or {}).get('2fa_tous')) if conf else False
    except Exception:  # noqa: BLE001
        return False


def obligatoire_pour(u):
    if getattr(u, 'role', None) != 'super_admin' and reglage_organisation(getattr(u, 'client_id', None)):
        return True
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
    if destination_valable(cible):
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
        if request.method == 'GET' and _navigation_de_page() and destination_valable(request.full_path):
            session['2fa_suite'] = request.full_path.rstrip('?')
        elif request.method == 'GET' and not _navigation_de_page():
            return ('', 401)          # ressource demandée avant le code : pas de redirection, destination conservée
        return redirect(url_for('securite_compte.verification'))
    if obligatoire_pour(current_user) and not session.get('auth_sso'):   # SSO : MFA assurée par le fournisseur
        if json_attendu:
            return jsonify({'erreur': 'double_authentification_a_activer'}), 403
        flash("Votre organisation exige la double authentification. Activez-la pour continuer : cela prend 2 minutes."
              if reglage_organisation(getattr(current_user, 'client_id', None)) else
              "Votre rôle d'administrateur exige la double authentification. Activez-la pour continuer.", 'warning')
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


@bp.route('/guide')
def guide():
    """Guide pas à pas, public et imprimable, à envoyer aux nouveaux utilisateurs (aucune donnée personnelle)."""
    return render_template('egalyx/2fa_guide.html')


@bp.route('/organisation', methods=['GET', 'POST'])
@connexion_requise
def organisation():
    """Administrateur du client (ou super admin) : exiger la 2FA pour tous, suivre qui l'a activée, réinitialiser."""
    from flask import abort
    from models import db, User, ClientConfiguration
    from egalyx.commun import client_id_courant
    if not (est_admin_client() or est_super_admin()):
        abort(403)
    cid = client_id_courant()
    if not cid:
        abort(404)
    if request.method == 'POST':
        conf = ClientConfiguration.query.filter_by(client_id=cid).first()
        if conf is None:
            conf = ClientConfiguration(client_id=cid, couleurs={}, preferences={})
            db.session.add(conf)
        prefs = dict(conf.preferences or {})
        sec = dict(prefs.get('securite') or {})
        sec['2fa_tous'] = request.form.get('2fa_tous') == '1'
        prefs['securite'] = sec
        conf.preferences = prefs
        journaliser('2fa_reglage_organisation', {'obligatoire_pour_tous': sec['2fa_tous']}, client_id=cid)
        db.session.commit()
        flash('Double authentification obligatoire pour tous les utilisateurs : à leur prochaine connexion, chacun '
              'sera guidé pour l\'activer.' if sec['2fa_tous'] else
              'Double authentification : obligatoire pour les administrateurs seulement.', 'success')
        return redirect(url_for('.organisation', client_id=cid if est_super_admin() else None))
    users = User.query.filter_by(client_id=cid).order_by(User.is_active.desc(), User.username).all()
    actifs = [u for u in users if u.is_active]
    return render_template('egalyx/2fa_organisation.html', users=users, tous=reglage_organisation(cid),
                           nb_actives=sum(1 for u in actifs if u.totp_actif), nb_actifs=len(actifs),
                           guide_url=__import__('egalyx.bienvenue', fromlist=['url_guide']).url_guide(), obligatoire_pour=obligatoire_pour)


def enregistrer(app):
    from egalyx.commun import exempter_controle_ancien
    app.register_blueprint(bp)
    exempter_controle_ancien(app, {'securite_compte.guide', 'securite_compte.organisation'})
    app.before_request(garde_double_auth)
    user_logged_in.connect(_a_la_connexion, app)
    user_logged_out.connect(_a_la_deconnexion, app)
