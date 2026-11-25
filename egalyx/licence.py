"""
egalyx/licence.py — clé de licence des installations chez un client (on-premise).

Active seulement si EGALYX_LICENCE_REQUISE=1 (posé par le Dockerfile du kit on-premise). Sur Render : rien ne change.

La clé est émise par Egalyx avec outils/licence_egalyx.py (signée avec la clé privée d'Egalyx, qui ne quitte jamais
l'ordinateur d'Egalyx) ; l'application la vérifie hors ligne avec la clé publique de egalyx/licence_cle.py.
Elle contient : le client, la date de fin, et en option le nombre d'utilisateurs prévu.

  - plus de 30 jours avant la fin : rien de visible ;
  - 30 derniers jours : bandeau d'avertissement pour les administrateurs ;
  - après la fin : 15 jours de grâce (bandeau rouge), puis l'outil se met en pause : les utilisateurs voient
    « licence expirée » ; le super administrateur peut se connecter et coller une nouvelle clé (page /licence).
    Les données ne sont jamais touchées.

La clé se pose dans .env (EGALYX_LICENCE=EGX1-…) ou depuis la page /licence (enregistrée dans le dossier des données).
"""
import base64
import json
import logging
import os
import time
from datetime import date

from flask import Blueprint, abort, flash, redirect, render_template_string, request, url_for
from flask_login import current_user

journal = logging.getLogger('egalyx.licence')
bp = Blueprint('licence', __name__)

PREFIXE = 'EGX1-'
AVANT, GRACE = 30, 15                       # jours d'avertissement, jours de grâce après la fin
LIBRES = ('/static/', '/health', '/licence', '/login', '/auth/login_fullscreen', '/logout', '/2fa/', '/compte/securite',
          '/favicon', '/manifest', '/service-worker', '/sw.js')
_cache = {'t': 0, 'etat': None}


def requise():
    return os.environ.get('EGALYX_LICENCE_REQUISE') == '1'


def _b64d(s):
    return base64.urlsafe_b64decode(s + '=' * (-len(s) % 4))


def _cle_publique():
    try:
        from egalyx.licence_cle import CLE_PUBLIQUE
    except Exception:  # noqa: BLE001
        return None
    return CLE_PUBLIQUE or None


def _fichier():
    base = os.environ.get('EGALYX_DONNEES') or '.'
    return os.path.join(base, 'licence.txt')


def cle_installee():
    cle = (os.environ.get('EGALYX_LICENCE') or '').strip()
    if not cle:
        try:
            with open(_fichier(), encoding='utf-8') as f:
                cle = f.read().strip()
        except OSError:
            cle = ''
    return cle


def lire(cle, publique=None):
    """Vérifie la signature ; renvoie le contenu de la licence (dict) ou lève ValueError."""
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    publique = publique or _cle_publique()
    if not publique:
        raise ValueError("clé publique d'Egalyx absente de egalyx/licence_cle.py")
    cle = ''.join(cle.split())
    if not cle.startswith(PREFIXE) or cle.count('.') != 1:
        raise ValueError('format de clé non reconnu')
    corps, sig = cle[len(PREFIXE):].split('.')
    try:
        Ed25519PublicKey.from_public_bytes(_b64d(publique)).verify(_b64d(sig), corps.encode())
    except (InvalidSignature, ValueError, Exception):  # noqa: BLE001
        raise ValueError('signature invalide : clé modifiée ou non émise par Egalyx')
    contenu = json.loads(_b64d(corps))
    contenu['fin'] = date.fromisoformat(contenu['fin'])
    return contenu


def etat(force=False):
    """{'statut': valide|bientot|grace|expiree|absente|invalide|non_requise, 'jours': …, 'licence': …, 'message': …}"""
    if not force and _cache['etat'] and time.time() - _cache['t'] < 600:
        return _cache['etat']
    if not requise():
        e = {'statut': 'non_requise'}
    elif not _cle_publique():
        e = {'statut': 'non_requise', 'message': "Licence requise mais clé publique absente : vérification impossible"}
        journal.error(e['message'])
    else:
        cle = cle_installee()
        if not cle:
            e = {'statut': 'absente', 'message': 'Aucune clé de licence installée.'}
        else:
            try:
                lic = lire(cle)
                jours = (lic['fin'] - date.today()).days
                if jours < -GRACE:
                    statut = 'expiree'
                elif jours < 0:
                    statut = 'grace'
                elif jours <= AVANT:
                    statut = 'bientot'
                else:
                    statut = 'valide'
                e = {'statut': statut, 'jours': jours, 'licence': lic}
            except ValueError as ex:
                e = {'statut': 'invalide', 'message': f'Clé de licence refusée : {ex}.'}
    _cache.update(t=time.time(), etat=e)
    return e


def _bloque(e):
    return e['statut'] in ('expiree', 'absente', 'invalide')


def _est_super_admin():
    try:
        if not current_user.is_authenticated:
            return False
        sa = getattr(current_user, 'is_super_admin', False)
        sa = sa() if callable(sa) else sa
        return bool(sa) or getattr(current_user, 'role', '') == 'super_admin'
    except Exception:  # noqa: BLE001
        return False


def _est_admin():
    try:
        return current_user.is_authenticated and (_est_super_admin() or getattr(current_user, 'is_client_admin', False)
                                                  or getattr(current_user, 'role', '') in ('admin', 'client_admin'))
    except Exception:  # noqa: BLE001
        return False


PAGE_PAUSE = """<!doctype html><html lang="fr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Licence Egalyx Control</title>
<body style="font-family:system-ui,sans-serif;background:#0B1F3A;color:#fff;margin:0;display:grid;place-items:center;min-height:100vh">
<div style="max-width:560px;padding:2rem;text-align:center">
<h1 style="font-size:1.5rem">Egalyx Control est en pause</h1>
<p style="color:#B9C6D8;line-height:1.6">{{ message }}<br>Vos données sont intactes. Votre administrateur peut contacter Egalyx
(<a style="color:#8FB4F0" href="mailto:contact@egalyx.com">contact@egalyx.com</a>) pour renouveler la licence.</p>
<p><a style="color:#8FB4F0" href="/login">Se connecter en super administrateur</a></p></div></body></html>"""

PAGE_LICENCE = """<!doctype html><html lang="fr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Licence — Egalyx Control</title>
<body style="font-family:system-ui,sans-serif;background:#F3F5F8;color:#14202E;margin:0">
<div style="max-width:720px;margin:3rem auto;padding:0 1rem">
<p><a href="/">← Retour à l'outil</a></p>
<h1 style="font-size:1.5rem">Licence Egalyx Control</h1>
{% with m = get_flashed_messages(with_categories=true) %}{% for c, t in m %}
<div style="padding:.8rem 1rem;border-radius:8px;margin:.8rem 0;background:{{ '#D7F5E8' if c == 'success' else '#FDE2E2' }}">{{ t }}</div>{% endfor %}{% endwith %}
<div style="background:#fff;border:1px solid #DDE3EA;border-radius:10px;padding:1.2rem 1.4rem;margin:1rem 0">
{% if e.licence %}
<p style="margin:.2rem 0"><b>Client :</b> {{ e.licence.client }}</p>
<p style="margin:.2rem 0"><b>Valable jusqu'au :</b> {{ e.licence.fin.strftime('%d/%m/%Y') }}
 {% if e.jours >= 0 %}(encore {{ e.jours }} jour{{ 's' if e.jours > 1 }}){% else %}(<b style="color:#B42318">expirée depuis {{ -e.jours }} jour{{ 's' if -e.jours > 1 }}</b>){% endif %}</p>
{% if e.licence.get('utilisateurs') %}<p style="margin:.2rem 0"><b>Utilisateurs prévus :</b> {{ e.licence.utilisateurs }}
 {% if actifs is not none %}— actifs aujourd'hui : {{ actifs }}{% endif %}</p>{% endif %}
{% else %}<p style="margin:0">{{ e.get('message') or 'Licence non requise sur cette installation.' }}</p>{% endif %}
</div>
<form method="post" style="background:#fff;border:1px solid #DDE3EA;border-radius:10px;padding:1.2rem 1.4rem">
<input type="hidden" name="csrf_token" value="{{ csrf_token() if csrf_token is defined else '' }}">
<label for="cle" style="font-weight:600">Nouvelle clé de licence (fournie par Egalyx)</label>
<textarea id="cle" name="cle" rows="4" style="width:100%;margin:.5rem 0;font-family:monospace;font-size:.85rem" placeholder="EGX1-…" required></textarea>
<button style="background:#0B5FD3;color:#fff;border:0;border-radius:8px;padding:.6rem 1.2rem;font-weight:600">Installer la clé</button>
</form></div></body></html>"""

BANDEAU = """<div role="status" style="position:fixed;left:0;right:0;bottom:0;z-index:2147483000;padding:.55rem 1rem;text-align:center;
font:600 14px system-ui,sans-serif;color:#fff;background:{c}">{t} <a href="/licence" style="color:#fff;text-decoration:underline">Voir la licence</a></div>"""


def enregistrer(app):
    if 'licence' not in app.blueprints:
        app.register_blueprint(bp)

    @app.before_request
    def _controle_licence():
        if not requise():
            return None
        p = request.path
        if any(p.startswith(x) for x in LIBRES):
            return None
        e = etat()
        if _bloque(e):
            if _est_super_admin():
                return redirect('/licence')
            return render_template_string(PAGE_PAUSE, message=e.get('message') or 'La licence de cet outil est arrivée à échéance.'), 503
        return None

    @app.after_request
    def _bandeau_licence(reponse):
        try:
            if not requise() or reponse.status_code != 200 or reponse.mimetype != 'text/html' or reponse.direct_passthrough:
                return reponse
            if request.path.startswith('/licence') or not _est_admin():
                return reponse
            e = etat()
            if e['statut'] == 'bientot':
                txt, coul = f"La licence Egalyx Control se termine dans {e['jours']} jour{'s' if e['jours'] > 1 else ''}.", '#B45309'
            elif e['statut'] == 'grace':
                reste = GRACE + e['jours']
                txt, coul = f"Licence expirée : l'outil se mettra en pause dans {reste} jour{'s' if reste > 1 else ''}.", '#B42318'
            else:
                return reponse
            html = reponse.get_data(as_text=True)
            if '</body>' in html:
                reponse.set_data(html.replace('</body>', BANDEAU.format(c=coul, t=txt) + '</body>', 1))
        except Exception:  # noqa: BLE001
            pass
        return reponse

    @app.cli.command('licence')
    def _cli_licence():
        """Affiche l'état de la licence de cette installation."""
        e = etat(force=True)
        if e.get('licence'):
            lic = e['licence']
            print(f"Licence {e['statut']} — client : {lic['client']} — fin : {lic['fin']:%d/%m/%Y} ({e['jours']} jours)"
                  + (f" — {lic['utilisateurs']} utilisateurs prévus" if lic.get('utilisateurs') else ''))
        else:
            print(f"Licence : {e['statut']}" + (f" — {e['message']}" if e.get('message') else ''))


@bp.route('/licence', methods=['GET', 'POST'])
def page_licence():
    if not _est_super_admin():
        if not current_user.is_authenticated:
            return redirect('/login')
        abort(404)
    if request.method == 'POST':
        cle = ''.join((request.form.get('cle') or '').split())
        try:
            lic = lire(cle)
            os.makedirs(os.path.dirname(_fichier()) or '.', exist_ok=True)
            with open(_fichier(), 'w', encoding='utf-8') as f:
                f.write(cle)
            _cache['etat'] = None
            if os.environ.get('EGALYX_LICENCE'):
                flash("Clé enregistrée, mais la variable EGALYX_LICENCE du fichier .env est prioritaire : "
                      "remplacez-la aussi (ou supprimez-la), puis redémarrez.", 'danger')
            else:
                flash(f"Licence installée : {lic['client']}, valable jusqu'au {lic['fin']:%d/%m/%Y}.", 'success')
        except ValueError as ex:
            flash(f'Clé refusée : {ex}.', 'danger')
        return redirect(url_for('licence.page_licence'))
    actifs = None
    try:
        from models import User
        actifs = User.query.filter_by(is_active=True).count()
    except Exception:  # noqa: BLE001
        pass
    return render_template_string(PAGE_LICENCE, e=etat(force=True), actifs=actifs)
