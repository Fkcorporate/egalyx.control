"""
egalyx/sso.py — connexion unique (OpenID Connect) Microsoft Entra ID et Google Workspace.

Désactivé tant que les variables ne sont pas définies :

  Microsoft : SSO_MICROSOFT_CLIENT_ID, SSO_MICROSOFT_CLIENT_SECRET,
              SSO_MICROSOFT_TENANTS = identifiant(s) d'annuaire autorisé(s), séparés par des virgules
              (obligatoire : sans restriction d'annuaire, n'importe quel locataire Microsoft
               pourrait présenter une adresse e-mail qu'il ne possède pas).
  Google    : SSO_GOOGLE_CLIENT_ID, SSO_GOOGLE_CLIENT_SECRET,
              SSO_GOOGLE_DOMAINES = domaines Workspace autorisés (facultatif, recommandé).
  URL de retour à déclarer chez le fournisseur : <EGALYX_URL_PUBLIQUE>/sso/<microsoft|google>/retour

Règles : seul un compte Egalyx existant, actif et non bloqué, dont l'adresse e-mail est
celle renvoyée (et vérifiée) par le fournisseur, peut se connecter. Aucun compte n'est créé.
L'authentification forte est alors assurée par le fournisseur d'identité.
"""
import base64
import hashlib
import json
import os
import secrets
import urllib.parse
import urllib.request
from datetime import datetime

from flask import Blueprint, abort, current_app, flash, redirect, request, session, url_for
from flask_login import login_user

bp = Blueprint('sso', __name__, url_prefix='/sso')

FOURNISSEURS = {
    'microsoft': {
        'nom': 'Microsoft',
        'icone': 'fab fa-microsoft',
        'autorisation': 'https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize',
        'jeton': 'https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token',
        'infos': 'https://graph.microsoft.com/oidc/userinfo',
        'portee': 'openid email profile',
    },
    'google': {
        'nom': 'Google',
        'icone': 'fab fa-google',
        'autorisation': 'https://accounts.google.com/o/oauth2/v2/auth',
        'jeton': 'https://oauth2.googleapis.com/token',
        'infos': 'https://openidconnect.googleapis.com/v1/userinfo',
        'portee': 'openid email profile',
    },
}


def _liste_env(nom):
    return [x.strip().lower() for x in (os.environ.get(nom) or '').split(',') if x.strip()]


def configuration(code):
    p = code.upper()
    cid, secret = os.environ.get(f'SSO_{p}_CLIENT_ID'), os.environ.get(f'SSO_{p}_CLIENT_SECRET')
    if code not in FOURNISSEURS or not cid or not secret:
        return None
    cfg = dict(FOURNISSEURS[code], code=code, client_id=cid, secret=secret)
    if code == 'microsoft':
        tenants = _liste_env('SSO_MICROSOFT_TENANTS')
        if not tenants:
            return None
        autorite = tenants[0] if len(tenants) == 1 else 'organizations'
        cfg['tenants'] = tenants
        cfg['autorisation'] = cfg['autorisation'].format(tenant=autorite)
        cfg['jeton'] = cfg['jeton'].format(tenant=autorite)
    else:
        cfg['domaines'] = _liste_env('SSO_GOOGLE_DOMAINES')
    return cfg


def fournisseurs_actifs():
    return [{'code': c, 'nom': FOURNISSEURS[c]['nom'], 'icone': FOURNISSEURS[c]['icone']}
            for c in FOURNISSEURS if configuration(c)]


def _url_retour(code):
    base = (os.environ.get('EGALYX_URL_PUBLIQUE') or '').rstrip('/')
    chemin = url_for('sso.retour', fournisseur=code)
    return base + chemin if base else url_for('sso.retour', fournisseur=code, _external=True)


def _b64url(octets):
    return base64.urlsafe_b64encode(octets).rstrip(b'=').decode()


def decoder_charge_jwt(jeton):
    """Charge utile d'un JWT (sans vérification de signature : le jeton vient directement
    du point de terminaison du fournisseur, en TLS vérifié, conformément à OIDC §3.1.3.7)."""
    try:
        charge = jeton.split('.')[1]
        charge += '=' * (-len(charge) % 4)
        return json.loads(base64.urlsafe_b64decode(charge))
    except Exception:
        return {}


def _http_json(url, donnees=None, entetes=None):
    corps = urllib.parse.urlencode(donnees).encode() if donnees is not None else None
    req = urllib.request.Request(url, data=corps, headers=dict({'Accept': 'application/json'}, **(entetes or {})))
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode())


def controler_identite(cfg, id_token, infos, nonce_attendu):
    """Retourne l'adresse e-mail validée ou lève ValueError (fonction pure, testée)."""
    claims = decoder_charge_jwt(id_token) if id_token else {}
    if claims.get('nonce') != nonce_attendu:
        raise ValueError('nonce invalide')
    aud = claims.get('aud')
    if cfg['client_id'] not in (aud if isinstance(aud, list) else [aud]):
        raise ValueError('audience invalide')
    if cfg['code'] == 'microsoft':
        if (claims.get('tid') or '').lower() not in cfg['tenants']:
            raise ValueError("annuaire Microsoft non autorisé")
        email = infos.get('email') or claims.get('email') or claims.get('preferred_username')
    else:
        if claims.get('iss') not in ('https://accounts.google.com', 'accounts.google.com'):
            raise ValueError('émetteur invalide')
        verifie = infos.get('email_verified', claims.get('email_verified'))
        if verifie not in (True, 'true'):
            raise ValueError('adresse e-mail non vérifiée par Google')
        email = infos.get('email') or claims.get('email')
        if cfg['domaines']:
            hd = (claims.get('hd') or infos.get('hd') or '').lower()
            if hd not in cfg['domaines']:
                raise ValueError('domaine Google non autorisé')
    if not email or '@' not in email:
        raise ValueError('adresse e-mail absente')
    return email.strip().lower()


@bp.route('/<fournisseur>')
def demarrer(fournisseur):
    cfg = configuration(fournisseur)
    if not cfg:
        abort(404)
    etat, nonce, verif = secrets.token_urlsafe(24), secrets.token_urlsafe(24), secrets.token_urlsafe(48)
    session['sso'] = {'f': fournisseur, 'etat': etat, 'nonce': nonce, 'verif': verif,
                      'suite': request.args.get('next') or ''}
    params = {
        'client_id': cfg['client_id'], 'response_type': 'code', 'redirect_uri': _url_retour(fournisseur),
        'scope': cfg['portee'], 'state': etat, 'nonce': nonce, 'prompt': 'select_account',
        'code_challenge': _b64url(hashlib.sha256(verif.encode()).digest()), 'code_challenge_method': 'S256',
    }
    if fournisseur == 'google' and len(cfg.get('domaines') or []) == 1:
        params['hd'] = cfg['domaines'][0]
    return redirect(cfg['autorisation'] + '?' + urllib.parse.urlencode(params))


@bp.route('/<fournisseur>/retour')
def retour(fournisseur):
    from models import db, User
    from egalyx.commun import journaliser
    from egalyx.double_auth import valider_session
    cfg = configuration(fournisseur)
    attente = session.pop('sso', None) or {}
    if not cfg or attente.get('f') != fournisseur or not attente.get('etat') \
            or not secrets.compare_digest(attente['etat'], request.args.get('state') or ''):
        flash('Connexion unique refusée : session expirée ou invalide. Recommencez.', 'danger')
        return redirect(url_for('login'))
    if request.args.get('error'):
        flash(f"Connexion {cfg['nom']} annulée ou refusée.", 'warning')
        return redirect(url_for('login'))
    try:
        jetons = _http_json(cfg['jeton'], {
            'grant_type': 'authorization_code', 'code': request.args.get('code') or '',
            'redirect_uri': _url_retour(fournisseur), 'client_id': cfg['client_id'],
            'client_secret': cfg['secret'], 'code_verifier': attente['verif']})
        infos = _http_json(cfg['infos'], entetes={'Authorization': f"Bearer {jetons['access_token']}"})
        email = controler_identite(cfg, jetons.get('id_token'), infos, attente['nonce'])
    except Exception as e:
        current_app.logger.warning("SSO %s refusé : %s", fournisseur, e)
        flash(f"Connexion {cfg['nom']} impossible : identité non validée.", 'danger')
        return redirect(url_for('login'))

    u = User.query.filter(db.func.lower(User.email) == email).first()
    if not u or not u.is_active or getattr(u, 'is_blocked', False) or getattr(u, 'deleted_at', None):
        flash(f"Aucun compte Egalyx actif n'est associé à {email}. Contactez votre administrateur.", 'danger')
        return redirect(url_for('login'))
    login_user(u)
    valider_session(u)
    session['auth_sso'] = fournisseur
    u.last_login = datetime.utcnow()
    if hasattr(u, 'failed_login_attempts'):
        u.failed_login_attempts = 0
    journaliser('connexion_sso', {'fournisseur': fournisseur}, client_id=u.client_id)
    db.session.commit()
    suite = attente.get('suite') or ''
    return redirect(suite if suite.startswith('/') and not suite.startswith('//') else url_for('dashboard'))


def enregistrer(app):
    app.register_blueprint(bp)
    app.jinja_env.globals['sso_fournisseurs'] = fournisseurs_actifs
