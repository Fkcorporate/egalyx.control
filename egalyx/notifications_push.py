"""
egalyx/notifications_push.py — notifications sur le téléphone ou l'ordinateur (Web Push) et pastille sur l'icône.

Ce que voit l'utilisateur (Mes notifications → « Sur vos appareils ») :
  - « Activer sur cet appareil » : le navigateur demande l'autorisation, puis chaque nouvelle notification d'Egalyx
    apparaît comme une notification du téléphone ou de l'ordinateur, même application fermée ;
  - les types d'événements à recevoir (incidents, validations, échéances…), tous cochés par défaut ;
  - « Pastille sur l'icône » : le nombre de notifications non lues sur l'icône de l'application installée (oui/non) ;
  - « Contenu discret » : la notification affiche seulement « Nouvelle notification Egalyx » (rien de confidentiel
    sur l'écran verrouillé) ;
  - la liste de ses appareils (retirer un appareil), et « Envoyer une notification de test ».

Technique (aucune bibliothèque à installer, aucun service payant) :
  - protocole Web Push standard : chiffrement RFC 8291 (aes128gcm) et identification VAPID RFC 8292, écrits ici
    avec le module « cryptography » ; vérifié avec l'implémentation de référence (http_ece / pywebpush) ;
  - clés VAPID : variable EGALYX_VAPID_CLE_PRIVEE si elle existe (conseillé sur Render), sinon créées une fois et
    gardées dans instance/egalyx_reglages.json. Si la clé change, les appareils se réabonnent d'eux-mêmes ;
  - abonnements gardés dans users.preferences_notifications (clé « push ») : aucune migration de base ;
  - envoi après l'enregistrement de la notification, en arrière-plan ; un appareil désinstallé (404/410) est retiré.
Compatibilité : Chrome, Edge, Firefox (ordinateur et Android), Safari sur Mac (application ajoutée au Dock, macOS 14+),
iPhone/iPad iOS 16.4+ uniquement depuis l'application installée sur l'écran d'accueil.
EGALYX_PUSH=0 coupe les envois.
"""
import base64
import json
import logging
import os
import struct
import threading
import time
from datetime import datetime
from urllib.parse import urlparse

from flask import Blueprint, current_app, flash, jsonify, redirect, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import event

journal = logging.getLogger('egalyx.notifications_push')
bp = Blueprint('notifications_push', __name__, url_prefix='/notifications/push')
CLE = 'push'
MAX_APPAREILS = 10
_VERROU = threading.Lock()
_CLES = {}


# ================================================================== utilitaires
def b64u(b):
    return base64.urlsafe_b64encode(b).rstrip(b'=').decode()


def deb64u(s):
    s = (s or '').strip()
    return base64.urlsafe_b64decode(s + '=' * (-len(s) % 4))


def disponible():
    try:
        import cryptography  # noqa: F401
        import requests  # noqa: F401
        return os.environ.get('EGALYX_PUSH', '1') != '0'
    except ImportError:
        return False


# ================================================================== clés VAPID
def _depuis_scalaire(octets):
    from cryptography.hazmat.primitives.asymmetric import ec
    return ec.derive_private_key(int.from_bytes(octets, 'big'), ec.SECP256R1())


def _publique_brute(cle_privee):
    from cryptography.hazmat.primitives import serialization
    return cle_privee.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)


def cles():
    """(clé privée, clé publique en base64url) — variable d'environnement, sinon fichier de réglages (créée une fois)."""
    brut = (os.environ.get('EGALYX_VAPID_CLE_PRIVEE') or '').strip()
    if _CLES.get('source') == brut and _CLES.get('privee') is not None:
        return _CLES['privee'], _CLES['publique']
    with _VERROU:
        if brut:
            privee = _depuis_scalaire(deb64u(brut))
        else:
            from egalyx import ia as reglages_plateforme
            sauve = reglages_plateforme.reglages().get('vapid_cle_privee')
            if not sauve:
                verrou = os.path.join(current_app.instance_path, '.vapid.lock')
                os.makedirs(current_app.instance_path, exist_ok=True)
                try:
                    fd = os.open(verrou, os.O_CREAT | os.O_EXCL | os.O_WRONLY)       # un seul processus crée la clé
                    os.close(fd)
                    from cryptography.hazmat.primitives.asymmetric import ec
                    nouvelle = ec.generate_private_key(ec.SECP256R1())
                    reglages_plateforme.ecrire_reglage('vapid_cle_privee',
                                                       b64u(nouvelle.private_numbers().private_value.to_bytes(32, 'big')))
                    os.remove(verrou)
                except FileExistsError:
                    for _ in range(50):
                        time.sleep(0.1)
                        if reglages_plateforme.reglages().get('vapid_cle_privee'):
                            break
                sauve = reglages_plateforme.reglages().get('vapid_cle_privee')
            privee = _depuis_scalaire(deb64u(sauve))
        _CLES.update(source=brut, privee=privee, publique=b64u(_publique_brute(privee)))
        return _CLES['privee'], _CLES['publique']


def contact_vapid():
    c = (os.environ.get('EGALYX_VAPID_CONTACT') or os.environ.get('EGALYX_EMAIL_CONTACT') or '').strip()
    if c:
        return c if c.startswith(('mailto:', 'https://')) else f'mailto:{c}'
    return (os.environ.get('EGALYX_URL_PUBLIQUE') or 'https://egalyx.com').rstrip('/')


def entete_vapid(endpoint, cle_privee, cle_publique, maintenant=None):
    """Authorization: vapid t=<JWT ES256>, k=<clé publique> (RFC 8292)."""
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
    u = urlparse(endpoint)
    entete = b64u(json.dumps({'typ': 'JWT', 'alg': 'ES256'}, separators=(',', ':')).encode())
    charge = b64u(json.dumps({'aud': f'{u.scheme}://{u.netloc}', 'exp': int((maintenant or time.time()) + 12 * 3600),
                              'sub': contact_vapid()}, separators=(',', ':')).encode())
    a_signer = f'{entete}.{charge}'.encode()
    r, s = decode_dss_signature(cle_privee.sign(a_signer, ec.ECDSA(hashes.SHA256())))
    jeton = f'{entete}.{charge}.{b64u(r.to_bytes(32, "big") + s.to_bytes(32, "big"))}'
    return f'vapid t={jeton}, k={cle_publique}'


# ================================================================== chiffrement RFC 8291 (aes128gcm)
def _hkdf(sel, ikm, info, longueur):
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    return HKDF(algorithm=hashes.SHA256(), length=longueur, salt=sel, info=info).derive(ikm)


def chiffrer(donnees, p256dh, auth, cle_serveur=None, sel=None, taille_enregistrement=4096):
    """Chiffre un message pour un abonnement (clé p256dh et secret auth du navigateur). Renvoie le corps à envoyer."""
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    publique_ua = deb64u(p256dh) if isinstance(p256dh, str) else p256dh
    secret_auth = deb64u(auth) if isinstance(auth, str) else auth
    if len(publique_ua) != 65 or len(secret_auth) != 16:
        raise ValueError('abonnement invalide')
    cle_serveur = cle_serveur or ec.generate_private_key(ec.SECP256R1())
    publique_serveur = _publique_brute(cle_serveur)
    secret = cle_serveur.exchange(ec.ECDH(), ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), publique_ua))
    ikm = _hkdf(secret_auth, secret, b'WebPush: info\x00' + publique_ua + publique_serveur, 32)
    sel = sel or os.urandom(16)
    cek = _hkdf(sel, ikm, b'Content-Encoding: aes128gcm\x00', 16)
    nonce = _hkdf(sel, ikm, b'Content-Encoding: nonce\x00', 12)
    if len(donnees) + 17 > taille_enregistrement:
        raise ValueError('message trop long')
    chiffre = AESGCM(cek).encrypt(nonce, donnees + b'\x02', None)
    return sel + struct.pack('!L', taille_enregistrement) + bytes([len(publique_serveur)]) + publique_serveur + chiffre


def envoyer_un(abonnement, message, ttl=86400, urgence='normal', poster=None):
    """Envoie un message (dict) à un abonnement. Renvoie le code HTTP du service de notification (ou 0)."""
    import requests
    cle_privee, cle_publique = cles()
    corps = chiffrer(json.dumps(message, ensure_ascii=False).encode(), abonnement['p256dh'], abonnement['auth'])
    entetes = {'TTL': str(ttl), 'Content-Encoding': 'aes128gcm', 'Content-Type': 'application/octet-stream',
               'Urgency': urgence, 'Authorization': entete_vapid(abonnement['endpoint'], cle_privee, cle_publique)}
    try:
        r = (poster or requests.post)(abonnement['endpoint'], data=corps, headers=entetes, timeout=10)
        return r.status_code
    except Exception as e:  # noqa: BLE001
        journal.info("Envoi push impossible : %s", e)
        return 0


# ================================================================== réglages de l'utilisateur
def _prefs(u):
    p = getattr(u, 'preferences_notifications', None)
    p = p if isinstance(p, dict) else {}
    r = dict(p.get(CLE) or {})
    r.setdefault('abonnements', [])
    r.setdefault('pastille', True)
    r.setdefault('discret', False)
    r.setdefault('evenements', {})
    return r


def _ecrire(u, push):
    p = dict(u.preferences_notifications if isinstance(u.preferences_notifications, dict) else {})
    p[CLE] = push
    u.preferences_notifications = p


def reglages(u):
    from egalyx.notifications_prefs import EVENEMENTS
    r = _prefs(u)
    r['evenements'] = {c: r['evenements'].get(c, True) for c, _l, _g in EVENEMENTS}
    return r


def non_lues(u_id, session_=None):
    import models as m
    s = session_ or m.db.session
    return s.query(m.Notification).filter(m.Notification.destinataire_id == u_id, m.Notification.est_lue.is_(False)).count()


def _nom_appareil(ua):
    ua = (ua or '').lower()
    systeme = ('iPhone' if 'iphone' in ua else 'iPad' if 'ipad' in ua else 'Android' if 'android' in ua else
               'Mac' if 'mac os' in ua or 'macintosh' in ua else 'Windows' if 'windows' in ua else 'Linux' if 'linux' in ua else 'Appareil')
    nav = ('Edge' if 'edg/' in ua else 'Firefox' if 'firefox' in ua else 'Chrome' if 'chrome' in ua or 'crios' in ua else
           'Safari' if 'safari' in ua else 'navigateur')
    return f'{systeme} · {nav}'


# ================================================================== envoi à la création d'une notification
def _apres_flush(session_, _ctx):
    if os.environ.get('EGALYX_PUSH', '1') == '0':
        return
    import models as m
    nouvelles = [n for n in session_.new if isinstance(n, m.Notification) and n.destinataire_id]
    if not nouvelles:
        return
    from egalyx.notifications_prefs import evenement
    with session_.no_autoflush:
        for n in nouvelles:
            u = session_.get(m.User, n.destinataire_id)
            if u is None or getattr(u, 'is_active', True) is False:
                continue
            r = reglages(u)
            if not r['abonnements'] or not r['evenements'].get(evenement(n), True):
                continue
            if r['discret']:
                titre, corps = 'Egalyx', 'Nouvelle notification'
            else:
                titre = (n.titre or 'Egalyx')[:80]
                corps = ' '.join((n.message or '').split())[:180]
            message = {'titre': titre, 'corps': corps, 'url': f'/notifications/notification/{n.id}/lire' if n.id else '/notifications',
                       'tag': f'egalyx-{n.id}', 'pastille': bool(r['pastille']),
                       'non_lues': non_lues(u.id, session_) if r['pastille'] else None}
            session_.info.setdefault('egalyx_push', []).append((u.id, list(r['abonnements']), message))


def _apres_commit(session_):
    envois = session_.info.pop('egalyx_push', None)
    if not envois or not disponible():
        return
    try:
        app = current_app._get_current_object()
    except RuntimeError:
        return
    threading.Thread(target=_envoyer_lot, args=(app, envois), daemon=True).start()


def _envoyer_lot(app, envois, poster=None):
    with app.app_context():
        perimes = {}
        for uid, abonnements, message in envois:
            for a in abonnements:
                code = envoyer_un(a, message, urgence='high' if message.get('titre', '').lower().startswith(('incident', 'alerte')) else 'normal',
                                  poster=poster)
                if code in (404, 410) or (code == 403 and a.get('cle') and a['cle'] != cles()[1][:16]):
                    perimes.setdefault(uid, set()).add(a['endpoint'])
        if perimes:
            _retirer(perimes)


def _retirer(perimes):
    import models as m
    try:
        for uid, endpoints in perimes.items():
            u = m.db.session.get(m.User, uid)
            if u is None:
                continue
            r = _prefs(u)
            r['abonnements'] = [a for a in r['abonnements'] if a['endpoint'] not in endpoints]
            _ecrire(u, r)
        m.db.session.commit()
    except Exception as e:  # noqa: BLE001
        m.db.session.rollback()
        journal.info("Nettoyage des appareils : %s", e)


def _apres_rollback(session_):
    session_.info.pop('egalyx_push', None)


# ================================================================== adresses appelées par la page
def _abonnement_valide(d):
    try:
        e = str(d.get('endpoint') or '')
        k = d.get('keys') or {}
        if not e.startswith('https://') or len(e) > 1000:
            return None
        if len(deb64u(k.get('p256dh'))) != 65 or len(deb64u(k.get('auth'))) != 16:
            return None
        return {'endpoint': e, 'p256dh': k['p256dh'], 'auth': k['auth']}
    except Exception:  # noqa: BLE001
        return None


@bp.route('/cle')
@login_required
def cle_publique():
    if not disponible():
        return jsonify({'disponible': False})
    return jsonify({'disponible': True, 'cle': cles()[1]})


@bp.route('/abonner', methods=['POST'])
@login_required
def abonner():
    from models import db
    if not disponible():
        return jsonify({'success': False, 'error': "Le serveur ne peut pas envoyer de notifications (module « cryptography » absent)."}), 503
    a = _abonnement_valide(request.get_json(silent=True) or {})
    if a is None:
        return jsonify({'success': False, 'error': 'Abonnement invalide.'}), 400
    r = _prefs(current_user)
    r['abonnements'] = [x for x in r['abonnements'] if x['endpoint'] != a['endpoint']]
    a.update(appareil=_nom_appareil(request.user_agent.string), cree_le=datetime.utcnow().isoformat(timespec='seconds'),
             cle=cles()[1][:16])
    r['abonnements'] = (r['abonnements'] + [a])[-MAX_APPAREILS:]
    _ecrire(current_user, r)
    db.session.commit()
    return jsonify({'success': True, 'appareil': a['appareil'], 'nb': len(r['abonnements'])})


@bp.route('/desabonner', methods=['POST'])
@login_required
def desabonner():
    from models import db
    d = request.get_json(silent=True) or request.form
    endpoint = d.get('endpoint')
    r = _prefs(current_user)
    avant = len(r['abonnements'])
    r['abonnements'] = [x for x in r['abonnements'] if x['endpoint'] != endpoint]
    _ecrire(current_user, r)
    db.session.commit()
    if request.is_json:
        return jsonify({'success': True, 'retire': avant - len(r['abonnements'])})
    flash('Appareil retiré : il ne recevra plus de notifications.', 'success')
    return redirect(url_for('preferences_notifications') + '#appareils')


@bp.route('/reglages', methods=['POST'])
@login_required
def enregistrer_reglages():
    from models import db
    from egalyx.notifications_prefs import EVENEMENTS
    r = _prefs(current_user)
    r['pastille'] = request.form.get('pastille') == '1'
    r['discret'] = request.form.get('discret') == '1'
    r['evenements'] = {c: request.form.get(f'push_{c}') == '1' for c, _l, _g in EVENEMENTS}
    _ecrire(current_user, r)
    db.session.commit()
    flash('Réglages des notifications sur vos appareils enregistrés.', 'success')
    return redirect(url_for('preferences_notifications') + '#appareils')


@bp.route('/tester', methods=['POST'])
@login_required
def tester():
    r = _prefs(current_user)
    if not r['abonnements']:
        return jsonify({'success': False, 'error': "Aucun appareil activé : cliquez d'abord sur « Activer sur cet appareil »."}), 400
    if not disponible():
        return jsonify({'success': False, 'error': "Le serveur ne peut pas envoyer de notifications."}), 503
    message = {'titre': 'Egalyx', 'corps': ('Test réussi : vous recevrez ici vos notifications.' if not r['discret']
                                            else 'Nouvelle notification'),
               'url': '/notifications/preferences#appareils', 'tag': 'egalyx-test', 'pastille': bool(r['pastille']),
               'non_lues': non_lues(current_user.id) if r['pastille'] else None}
    resultats, perimes = [], set()
    for a in r['abonnements']:
        code = envoyer_un(a, message, ttl=600, urgence='high')
        resultats.append({'appareil': a.get('appareil'), 'ok': 200 <= code < 300, 'code': code})
        if code in (404, 410):
            perimes.add(a['endpoint'])
    if perimes:
        _retirer({current_user.id: perimes})
    ok = sum(1 for x in resultats if x['ok'])
    return jsonify({'success': ok > 0, 'envoyes': ok, 'resultats': resultats,
                    'message': f"Notification de test envoyée à {ok} appareil(s) sur {len(resultats)}." if ok else
                               "La notification n'a pu être remise à aucun appareil : réactivez-la sur cet appareil."})


@bp.route('/compteur')
@login_required
def compteur():
    r = _prefs(current_user)
    return jsonify({'non_lues': non_lues(current_user.id) if r['pastille'] else 0, 'pastille': bool(r['pastille']),
                    'cle': cles()[1] if disponible() and r['abonnements'] else None})


# ================================================================== enregistrement
def enregistrer(app):
    import models as m
    from sqlalchemy.orm import Session
    if not getattr(m, '_egalyx_notif_push', False):
        event.listen(Session, 'after_flush', _apres_flush)
        event.listen(Session, 'after_commit', _apres_commit)
        event.listen(Session, 'after_soft_rollback', lambda s, _t: _apres_rollback(s))
        m._egalyx_notif_push = True
    app.register_blueprint(bp)
    app.jinja_env.globals['push_reglages'] = reglages
    app.jinja_env.globals['push_disponible'] = disponible
    return True
