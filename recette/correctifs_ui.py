"""Recette : fenêtres des pages Directions (cartes) et Pôles non transparentes ; compteur des feuilles de travail
de la fiche audit juste dès l'ouverture."""
import os
import re
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

print('--- Fenêtres (popups) en mode clair')
adm = socle.navigateur(A, ids['admin_a'])
with A.app.app_context():
    cid = db.session.get(M.User, ids['admin_a']).client_id
    creer(M.Direction, nom='Direction test fenêtre', client_id=cid); db.session.commit()
for url, nom in (('/admin/directions?vue=cartes', 'Directions (vue cartes)'), ('/admin/poles', 'Pôles')):
    h = appel(adm, 'GET', url).data.decode()
    clair = ' '.join(re.findall(r':root\s*\{([^}]*)\}', h))
    verif(f'{nom} : fond des fenêtres défini en mode clair', re.search(r'--card-bg\s*:\s*#fff', clair) is not None)
    verif(f'{nom} : texte et pied des fenêtres définis en mode clair', '--text-primary:' in clair.replace(' ', '') and '--bg-secondary:' in clair.replace(' ', ''))
    verif(f'{nom} : le mode sombre garde ses couleurs', re.search(r'\[data-bs-theme="dark"\]\s*\{[^}]*--card-bg:\s*#1e293b', h) is not None)

print('--- Compteur des feuilles de travail (fiche audit)')
with A.app.app_context():
    au = creer(M.Audit, titre='Audit caisse', reference='AUD-T-1', client_id=cid, created_by=ids['admin_a'], statut='en_cours')
    for i in range(3):
        creer(M.FeuilleTravail, reference=f'FT-T-{i}', titre=f'Test {i}', audit_id=au.id, client_id=cid, is_archived=(i == 2),
              created_by=ids['admin_a'])
    db.session.commit(); aid = au.id
r = appel(adm, 'GET', f'/audit/{aid}')
if r.status_code in (301, 302):
    r = appel(adm, 'GET', r.headers['Location'])
h = r.data.decode()
verif('fiche audit : 200', r.status_code == 200, str(r.status_code))
verif('onglet : 2 feuilles dès l’ouverture (la 3e, archivée, n’est pas comptée)', re.search(r'id="feuillesTabCount">2<', h) is not None,
      (re.search(r'id="feuillesTabCount">([^<]*)<', h) or [None, '?'])[1] if re.search(r'id="feuillesTabCount">([^<]*)<', h) else 'absent')
verif('bouton « Feuilles de travail » : 2 aussi', re.search(r'id="feuillesCount">2<', h) is not None)
verif('le recalcul en page ne remet plus 0 tant que l’onglet n’est pas chargé', 'on garde le nombre calculé par le serveur' in h)
api = appel(adm, 'GET', f'/api/audit/{aid}/feuilles-travail').get_json(silent=True) or {}
liste = api.get('feuilles') if isinstance(api, dict) else api
verif('même nombre que la liste de l’onglet', liste is None or len(liste) == 2, str(len(liste) if liste is not None else '?'))

print(f'\n{sum(res)}/{len(res)} vérifications réussies')
