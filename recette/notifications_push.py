"""Recette : notifications sur téléphone / ordinateur (Web Push) et pastille sur l'icône.
Le chiffrement est vérifié en déchiffrant chaque message avec l'implémentation de référence (http_ece) quand elle est
disponible (/tmp/ref), sinon avec un déchiffrement RFC 8291 indépendant écrit ici."""
import base64
import json
import os
import struct
import sys
import time
os.environ['EGALYX_COLLECTE_AUTO'] = '0'
import socle
from socle import Muet, appel, creer
res = []


def verif(nom, cond, detail=''):
    res.append(bool(cond)); print('OK   ' if cond else 'ÉCHEC', nom, detail)


with Muet():
    A, ids = socle.preparer()
import models as M
from models import db
from egalyx import notifications_push as np
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature

try:
    sys.path.insert(0, '/tmp/ref/encrypted-content-encoding/python')
    import http_ece
except ImportError:
    http_ece = None


def dechiffrer(corps, ua_privee, auth):
    if http_ece is not None:
        return http_ece.decrypt(corps, private_key=ua_privee, auth_secret=auth, version='aes128gcm')
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    sel, rs, idlen = corps[:16], struct.unpack('!L', corps[16:20])[0], corps[20]
    pub_srv = corps[21:21 + idlen]
    ua_pub = ua_privee.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    secret = ua_privee.exchange(ec.ECDH(), ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), pub_srv))
    ikm = np._hkdf(auth, secret, b'WebPush: info\x00' + ua_pub + pub_srv, 32)
    clair = AESGCM(np._hkdf(sel, ikm, b'Content-Encoding: aes128gcm\x00', 16)).decrypt(
        np._hkdf(sel, ikm, b'Content-Encoding: nonce\x00', 12), corps[21 + idlen:], None)
    return clair.rstrip(b'\x00')[:-1]


class Appareil:
    """Un navigateur abonné (clés comme celles que génère Chrome / Safari)."""
    def __init__(self, nom):
        self.privee = ec.generate_private_key(ec.SECP256R1())
        self.auth = os.urandom(16)
        pub = self.privee.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
        self.json = {'endpoint': f'https://push.exemple.test/{nom}', 'keys': {'p256dh': np.b64u(pub), 'auth': np.b64u(self.auth)}}


recus, codes = [], {}


class Rep:
    def __init__(self, code): self.status_code = code


def faux_post(url, data=None, headers=None, timeout=None):
    recus.append((url, data, headers))
    return Rep(codes.get(url, 201))


import requests
requests.post = faux_post


def attendre(n, delai=4.0):
    t = time.time()
    while len(recus) < n and time.time() - t < delai:
        time.sleep(0.05)


def message(url, appareil):
    for u, data, h in reversed(recus):
        if u == url:
            return json.loads(dechiffrer(data, appareil.privee, appareil.auth)), h
    return None, None


def go(role, m, url, **kw):
    r = appel(socle.navigateur(A, ids[role]), m, url, **kw)
    return r, r.data.decode('utf-8', 'ignore'), socle.cause(A)


def notifier(uid, titre='Incident déclaré', message_='Panne du serveur de paiement', type_='incident'):
    with A.app.app_context():
        n = M.Notification(type_notification=type_, titre=titre, message=message_, destinataire_id=uid, client_id=1)
        db.session.add(n); db.session.commit(); return n.id


print('--- Clés du serveur')
with A.app.app_context():
    priv, pub = np.cles()
    verif('clé publique VAPID (point P-256 non compressé, 65 octets)', len(np.deb64u(pub)) == 65 and np.deb64u(pub)[0] == 4)
    np._CLES.clear()
    verif('clé conservée (même clé après relecture)', np.cles()[1] == pub)
r, _, _ = go('admin_a', 'get', '/notifications/push/cle')
verif('adresse /cle : clé publique', r.status_code == 200 and r.get_json()['cle'] == pub)

print('--- Page « Mes notifications »')
r, t, e = go('admin_a', 'get', '/notifications/preferences')
verif('section « Sur vos appareils » affichée', r.status_code == 200 and 'Sur vos appareils' in t and 'Activer sur cet appareil' in t
      and "Pastille sur l'icône" in t and 'Contenu discret' in t, f'{r.status_code} {e}')
r, t, _ = go('admin_a', 'get', '/dashboard')
verif('pastille : script chargé sur les pages', 'egPushAbonner' in t)
r, t, _ = go('admin_a', 'get', '/sw.js')
verif("service worker : réception, clic, pastille", "addEventListener('push'" in t and 'notificationclick' in t and 'setAppBadge' in t
      and 'egalyx-v3' in t)

print('--- Abonnement')
tel, ordi = Appareil('telephone-admin'), Appareil('ordi-admin')
c = socle.navigateur(A, ids['admin_a'])
r = c.post('/notifications/push/abonner', json=tel.json, headers={'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4) Safari/604.1'})
verif('abonnement enregistré (iPhone · Safari)', r.status_code == 200 and r.get_json()['appareil'] == 'iPhone · Safari', str(r.get_json()))
r = c.post('/notifications/push/abonner', json=ordi.json, headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) Chrome/131.0'})
verif('2e appareil (Mac · Chrome)', r.get_json().get('nb') == 2)
c.post('/notifications/push/abonner', json=ordi.json)
with A.app.app_context():
    verif('pas de doublon si on réactive le même appareil', len(np.reglages(db.session.get(M.User, ids['admin_a']))['abonnements']) == 2)
r = c.post('/notifications/push/abonner', json={'endpoint': 'http://pas-https.test/x', 'keys': tel.json['keys']})
verif('adresse non https refusée', r.status_code == 400)
r = c.post('/notifications/push/abonner', json={'endpoint': 'https://x.test/y', 'keys': {'p256dh': 'abc', 'auth': 'def'}})
verif('clés invalides refusées', r.status_code == 400)

print('--- Envoi à la création d\'une notification')
recus.clear()
nid = notifier(ids['admin_a'])
attendre(2)
m1, h1 = message(tel.json['endpoint'], tel)
m2, _ = message(ordi.json['endpoint'], ordi)
verif('envoyée aux 2 appareils', len(recus) == 2, str(len(recus)))
verif('déchiffrée par l\'appareil (implémentation de référence http_ece)' if http_ece else 'déchiffrée par l\'appareil',
      m1 and m1['titre'] == 'Incident déclaré' and m1['corps'] == 'Panne du serveur de paiement' and m2 == m1, str(m1))
verif('lien vers la notification', m1 and m1['url'] == f'/notifications/notification/{nid}/lire')
verif('pastille : nombre de non lues joint', m1 and m1['pastille'] is True and m1['non_lues'] >= 1, str(m1 and m1['non_lues']))
verif('en-têtes Web Push conformes', h1 and h1['Content-Encoding'] == 'aes128gcm' and h1['TTL'] and h1['Authorization'].startswith('vapid t='))
t = h1['Authorization'].split('t=')[1].split(',')[0]; k = h1['Authorization'].split('k=')[1]
e64, c64, s64 = t.split('.'); sig = np.deb64u(s64)
try:
    ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), np.deb64u(k)).verify(
        encode_dss_signature(int.from_bytes(sig[:32], 'big'), int.from_bytes(sig[32:], 'big')), f'{e64}.{c64}'.encode(),
        ec.ECDSA(hashes.SHA256()))
    signe = True
except Exception:
    signe = False
revend = json.loads(np.deb64u(c64))
verif('signature VAPID valide, audience = service de l\'appareil', signe and revend['aud'] == 'https://push.exemple.test' and k == pub, str(revend))

print('--- Réglages de l\'utilisateur')
c.post('/notifications/push/reglages', data={'pastille': '1', 'discret': '1', **{f'push_{x}': '1' for x in ('incident', 'a_valider', 'echeance', 'signalement', 'kri', 'incident_alerte')}})
recus.clear(); notifier(ids['admin_a'], 'Incident critique : fraude', 'Détails confidentiels'); attendre(2)
m1, _ = message(tel.json['endpoint'], tel)
verif('« contenu discret » : rien de confidentiel sur l\'écran verrouillé', m1 and m1['titre'] == 'Egalyx' and 'confidentiel' not in json.dumps(m1), str(m1))
recus.clear(); notifier(ids['admin_a'], 'Information', 'x', type_='info'); time.sleep(1.0)
verif('type d\'événement décoché (« Autres ») : aucun envoi', len(recus) == 0, str(len(recus)))
c.post('/notifications/push/reglages', data={'push_incident': '1'})
recus.clear(); notifier(ids['admin_a']); attendre(2)
m1, _ = message(tel.json['endpoint'], tel)
verif('pastille désactivée : l\'icône n\'affiche pas de nombre', m1 and m1['pastille'] is False and m1['non_lues'] is None, str(m1))
r = c.get('/notifications/push/compteur')
verif('compteur : 0 quand la pastille est désactivée', r.get_json()['non_lues'] == 0 and r.get_json()['pastille'] is False)
c.post('/notifications/push/reglages', data={'pastille': '1', **{f'push_{x}': '1' for x in ('incident', 'autres')}})
r = c.get('/notifications/push/compteur')
with A.app.app_context():
    attendu = M.Notification.query.filter_by(destinataire_id=ids['admin_a'], est_lue=False).count()
verif('compteur : nombre réel de non lues', r.get_json()['non_lues'] == attendu and attendu > 0, f"{r.get_json()} / {attendu}")

print('--- Cloisonnement et nettoyage')
recus.clear(); notifier(ids['gestionnaire']); time.sleep(1.0)
verif('notification d\'un autre utilisateur : rien sur mes appareils', len(recus) == 0)
codes[tel.json['endpoint']] = 410
recus.clear(); notifier(ids['admin_a']); attendre(2); time.sleep(0.5)
with A.app.app_context():
    restants = [a['endpoint'] for a in np.reglages(db.session.get(M.User, ids['admin_a']))['abonnements']]
verif('appareil désinstallé (410) : retiré automatiquement', tel.json['endpoint'] not in restants and ordi.json['endpoint'] in restants, str(restants))
r = c.post('/notifications/push/tester', json={})
d = r.get_json()
verif('« Envoyer un test » : envoyé à l\'appareil restant', r.status_code == 200 and d['envoyes'] == 1, str(d))
r = c.post('/notifications/push/desabonner', json={'endpoint': ordi.json['endpoint']})
with A.app.app_context():
    verif('« Désactiver ici » : appareil retiré', not np.reglages(db.session.get(M.User, ids['admin_a']))['abonnements'])
r = c.post('/notifications/push/tester', json={})
verif('test sans appareil : message clair', r.status_code == 400 and 'Activer' in r.get_json()['error'])
os.environ['EGALYX_PUSH'] = '0'
c.post('/notifications/push/abonner', json=Appareil('x').json)
recus.clear(); notifier(ids['admin_a']); time.sleep(1.0)
verif('EGALYX_PUSH=0 : aucun envoi', len(recus) == 0)
os.environ['EGALYX_PUSH'] = '1'
r, _, _ = go('admin_a', 'get', '/notifications/push/compteur')
verif('adresses réservées aux utilisateurs connectés', appel(A.app.test_client(), 'get', '/notifications/push/compteur').status_code in (302, 401))

print(f'\n{sum(res)}/{len(res)} vérifications réussies')
