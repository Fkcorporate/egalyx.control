"""Photo de profil (dépôt, affichage, cloisonnement, formats) et double authentification guidée pour l'organisation
(obligatoire pour tous, suivi, guide public, page d'activation)."""
import io
import sys

import socle
from socle import Muet, appel

with Muet():
    A, ids = socle.preparer()
import models as M
from models import db

res = []


def verif(nom, cond, detail=''):
    res.append(bool(cond))
    print('OK   ' if cond else 'ÉCHEC', nom, detail)


def go(role, m, url, **kw):
    r = appel(socle.navigateur(A, ids[role]), m, url, **kw)
    return r, r.data.decode('utf-8', 'ignore')


def image(fmt='JPEG', l=900, h=600):
    from PIL import Image
    b = io.BytesIO()
    Image.new('RGB', (l, h), (30, 120, 60)).save(b, fmt)
    return b.getvalue()


print('--- Photo de profil')
r, t = go('gestionnaire', 'get', '/profil')
verif('Profil : bouton « Ajouter une photo »', r.status_code == 200 and 'Ajouter une photo' in t, f'{r.status_code} {socle.cause(A)}')
r, _ = go('gestionnaire', 'post', '/compte/photo/', data={'photo': (io.BytesIO(image()), 'moi.jpg'), 'retour': '/profil'},
          content_type='multipart/form-data')
r, t = go('gestionnaire', 'get', '/profil')
verif('Photo enregistrée : affichée dans le profil et l\'en-tête', f'/compte/photo/{ids["gestionnaire"]}' in t and 'pp-entete' in t
      and 'Changer la photo' in t)
r, _ = go('gestionnaire', 'get', f'/compte/photo/{ids["gestionnaire"]}')
from PIL import Image
img = Image.open(io.BytesIO(r.data)) if r.status_code == 200 else None
verif('Photo recadrée en carré 256 × 256 (PNG)', img is not None and img.size == (256, 256), str(img.size if img else r.status_code))
r, _ = go('lecteur', 'get', f'/compte/photo/{ids["gestionnaire"]}')
verif('Collègue de la même organisation : voit la photo', r.status_code == 200, str(r.status_code))
r, _ = go('admin_b', 'get', f'/compte/photo/{ids["gestionnaire"]}')
verif('Autre organisation : photo introuvable', r.status_code == 404, str(r.status_code))
r = appel(A.app.test_client(), 'get', f'/compte/photo/{ids["gestionnaire"]}')
verif('Sans connexion : photo introuvable', r.status_code == 404, str(r.status_code))
svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
go('lecteur', 'post', '/compte/photo/', data={'photo': (io.BytesIO(svg), 'x.svg')}, content_type='multipart/form-data')
r, _ = go('lecteur', 'get', f'/compte/photo/{ids["lecteur"]}')
verif('SVG refusé', r.status_code == 404, str(r.status_code))
go('gestionnaire', 'post', '/compte/photo/', data={'retirer': '1', 'retour': '/profil'})
r, t = go('gestionnaire', 'get', '/profil')
verif('Photo retirée : initiales à la place', f'/compte/photo/{ids["gestionnaire"]}' not in t and 'Ajouter une photo' in t)

print('--- Double authentification : processus pour l\'organisation')
anonyme = A.app.test_client()
r = anonyme.get('/compte/securite/guide')
t = r.data.decode()
verif('Guide public, sans connexion, avec liens FreeOTP Android et iPhone', r.status_code == 200 and 'org.fedorahosted.freeotp' in t
      and 'apps.apple.com/app/freeotp' in t, str(r.status_code))
r, _ = go('lecteur', 'get', '/compte/securite/organisation')
verif('Utilisateur non admin : page de l\'organisation refusée', r.status_code in (302, 403), str(r.status_code))
r, t = go('admin_a', 'get', '/compte/securite/organisation')
verif('Admin du client : page affichée (règle, guide, liste)', r.status_code == 200 and 'Obligatoire pour tous' in t
      and '/compte/securite/guide' in t, f'{r.status_code} {socle.cause(A)}')
r, t = go('lecteur', 'get', '/dashboard')
verif('Avant : l\'utilisateur n\'est pas obligé d\'activer', r.status_code == 200, str(r.status_code))
go('admin_a', 'post', '/compte/securite/organisation', data={'2fa_tous': '1'})
c = socle.navigateur(A, ids['lecteur'])
r = appel(c, 'get', '/dashboard')
verif('Obligatoire pour tous : l\'utilisateur est envoyé vers l\'activation', r.status_code == 302
      and '/compte/securite/2fa/activer' in (r.headers.get('Location') or ''), f'{r.status_code} {r.headers.get("Location")}')
r = appel(c, 'get', '/compte/securite/2fa/activer')
t = r.data.decode()
verif('Page d\'activation : liens FreeOTP / Google / Microsoft et avertissement', r.status_code == 200 and 'org.fedorahosted.freeotp' in t
      and 'quelqu\'un d\'autre' in t and 'Votre organisation exige' in t, f'{r.status_code} {socle.cause(A)}')
r, _ = go('admin_b', 'get', '/dashboard')
verif('Autre organisation : non concernée', r.status_code == 200, str(r.status_code))
with A.app.app_context():
    cid_a = db.session.get(M.User, ids['admin_a']).client_id
r = appel(socle.navigateur(A, ids['admin_a']), 'get', '/dashboard')
verif('L\'admin sans double authentification est guidé lui aussi', r.status_code == 302
      and '/2fa/activer' in (r.headers.get('Location') or ''), str(r.status_code))
r, t = go('superadmin', 'get', f'/compte/securite/organisation?client_id={cid_a}')
verif('Suivi : utilisateurs « À activer »', 'À activer' in t)
r, t = go('superadmin', 'get', f'/compte/securite/organisation?client_id={cid_a}')
verif('Super admin : page de l\'organisation d\'un client', r.status_code == 200 and 'Obligatoire pour tous' in t, str(r.status_code))
r, t = go('superadmin', 'get', f'/super-admin/client/{cid_a}')
verif('Fiche client : bouton « Double authentification »', f'/compte/securite/organisation?client_id={cid_a}' in t)
r, _ = go('superadmin', 'get', '/dashboard')
verif('Super admin : jamais bloqué par la règle d\'un client', r.status_code == 200, str(r.status_code))
go('superadmin', 'post', f'/compte/securite/organisation?client_id={cid_a}', data={})
r = appel(socle.navigateur(A, ids['lecteur']), 'get', '/dashboard')
verif('Règle retirée : l\'utilisateur accède de nouveau', r.status_code == 200, str(r.status_code))

print('--- E-mail de bienvenue automatique')
import time
from egalyx import courriel
envoyes = []
courriel.est_configure = lambda: True
courriel.envoyer = lambda dest, sujet, texte, **k: envoyes.append((dest[0], sujet, texte, k.get('html') or '')) or True
from werkzeug.security import generate_password_hash


def nouvel_utilisateur(nom, client_id, role='utilisateur', admin=False):
    with A.app.app_context():
        u = M.User(username=nom, email=f'{nom}@egalyx-recette.fr', role=role, client_id=client_id, is_active=True,
                   is_client_admin=admin, password_hash=generate_password_hash('Xx1!xxxxxx'))
        db.session.add(u)
        db.session.commit()
    time.sleep(0.5)


nouvel_utilisateur('nouvelle.recrue', cid_a)
m = [e for e in envoyes if e[0] == 'nouvelle.recrue@egalyx-recette.fr']
verif('Nouvel utilisateur : e-mail de bienvenue (adresse, identifiant, sans mot de passe)', len(m) == 1
      and 'Identifiant : nouvelle.recrue' in m[0][2] and 'Xx1!' not in m[0][2] and 'Adresse :' in m[0][2], str(envoyes))
verif('Utilisateur simple, règle non active : pas de section double authentification', m and 'Double authentification' not in m[0][2])
envoyes.clear()
import os
_avant = os.environ.get('EGALYX_2FA_OBLIGATOIRE_ADMINS')
os.environ['EGALYX_2FA_OBLIGATOIRE_ADMINS'] = '1'          # réglage de production
nouvel_utilisateur('nouvel.admin', cid_a, role='admin', admin=True)
if _avant is None:
    os.environ.pop('EGALYX_2FA_OBLIGATOIRE_ADMINS')
else:
    os.environ['EGALYX_2FA_OBLIGATOIRE_ADMINS'] = _avant
m = [e for e in envoyes if e[0] == 'nouvel.admin@egalyx-recette.fr']
verif('Administrateur : guide de double authentification inclus (texte et HTML)', m and '/compte/securite/guide' in m[0][2]
      and 'FreeOTP' in m[0][3], str(m)[:300])
go('superadmin', 'post', f'/compte/securite/organisation?client_id={cid_a}', data={'2fa_tous': '1'})
envoyes.clear()
nouvel_utilisateur('autre.recrue', cid_a)
m = [e for e in envoyes if e[0] == 'autre.recrue@egalyx-recette.fr']
verif('Organisation « obligatoire pour tous » : guide inclus pour chacun', m and '/compte/securite/guide' in m[0][2], str(m)[:200])
go('superadmin', 'post', f'/compte/securite/organisation?client_id={cid_a}', data={})
envoyes.clear()
with A.app.app_context():
    cl = M.Client(nom='Client Neuf', reference='NEUF-1', is_active=True)
    db.session.add(cl)
    db.session.flush()
    db.session.add(M.User(username='admin.neuf', email='admin.neuf@egalyx-recette.fr', role='admin', client_id=cl.id,
                          is_active=True, is_client_admin=True, password_hash=generate_password_hash('Xx1!xxxxxx')))
    db.session.commit()
time.sleep(0.5)
verif('Compte créé avec le client : pas de doublon (déjà dans l\'e-mail de création du client)',
      not any(e[0] == 'admin.neuf@egalyx-recette.fr' for e in envoyes), str(envoyes))
with A.app.app_context():
    from egalyx.bienvenue import texte_2fa_html
    verif('E-mail de création du client : section double authentification et guide', '/compte/securite/guide' in texte_2fa_html())

print(f'\n{sum(res)}/{len(res)} vérifications réussies')
sys.exit(0 if all(res) else 1)
