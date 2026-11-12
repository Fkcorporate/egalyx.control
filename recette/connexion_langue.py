"""Connexion en anglais avec double authentification : on revient sur la bonne page, jamais sur un fichier
de traduction (ni sur un autre site)."""
import sys

import socle
import objets
from socle import Muet, appel

with Muet():
    A, ids = socle.preparer()
    objets.peupler_objets(A, ids)
import models as M
from models import db

res = []


def verif(nom, cond, detail=''):
    res.append(bool(cond))
    print('OK   ' if cond else 'ÉCHEC', nom, detail)


with A.app.app_context():
    u = db.session.get(M.User, ids['gestionnaire'])
    u.totp_actif = True
    db.session.commit()

c = socle.navigateur(A, ids['gestionnaire'])            # mot de passe accepté, code pas encore saisi
c.set_cookie('egalyx_langue', 'en') if hasattr(c, 'set_cookie') else None
appel(c, 'get', '/langue/en')
PAGE = {'Sec-Fetch-Dest': 'document', 'Accept': 'text/html'}
r = appel(c, 'get', '/kri', headers=PAGE)
verif('Page demandée avant le code : renvoi vers la saisie du code', r.status_code == 302 and 'verification' in (r.headers.get('Location') or ''), str(r.status_code))
r = appel(c, 'get', '/securite/verification' if False else r.headers.get('Location'), headers=PAGE)
t = r.data.decode('utf-8', 'ignore')
verif('La page du code s\'affiche', r.status_code == 200, str(r.status_code))
r = appel(c, 'get', '/langue/dictionnaire-en.js?v=1', headers={'Sec-Fetch-Dest': 'script', 'Accept': '*/*'})
verif('Le dictionnaire anglais se charge sur la page du code', r.status_code == 200 and b'EGALYX_DICO' in r.data, str(r.status_code))
r = appel(c, 'get', '/static/inexistant.png', headers={'Sec-Fetch-Dest': 'image', 'Accept': 'image/*'})
with c.session_transaction() as s:
    suite = s.get('2fa_suite')
verif('Après le code, destination = la page demandée (pas le dictionnaire)', suite == '/kri', str(suite))
r = appel(c, 'get', '/autre-script.js', headers={'Sec-Fetch-Dest': 'script', 'Accept': '*/*'})
with c.session_transaction() as s:
    suite = s.get('2fa_suite')
verif('Un script chargé avant le code ne remplace pas la destination', suite == '/kri' and r.status_code in (401, 404), f'{r.status_code} {suite}')

for nom_cas, h in (('service worker (Sec-Fetch-Dest vide)', {'Sec-Fetch-Dest': 'empty', 'Sec-Fetch-Mode': 'same-origin',
                                                        'Accept': 'text/html,application/xhtml+xml,*/*;q=0.8'}),
                   ('navigation sans Sec-Fetch-Dest', {'Sec-Fetch-Mode': 'navigate', 'Accept': 'text/html'})):
    r = appel(c, 'get', '/', headers=h)
    verif(f'Page « / » avant le code via {nom_cas} : renvoi vers le code (jamais une page blanche 401)',
          r.status_code == 302 and 'verification' in (r.headers.get('Location') or ''), str(r.status_code))
r = appel(c, 'get', '/x.json', headers={'Sec-Fetch-Dest': 'empty', 'Accept': 'application/json'})
verif('Appel en arrière-plan avant le code : 401, sans redirection', r.status_code == 401, str(r.status_code))
with c.session_transaction() as s:
    s['2fa_suite'] = '/kri'

from egalyx.double_auth import destination_valable
verif('Destinations refusées : fichiers, API, autre site',
      not any(destination_valable(x) for x in ('/langue/dictionnaire-en.js?v=a8', '/static/app.css', '/api/x',
                                               'https://egalyx.com.pirate.net/', '//pirate.net/x', None)))
verif('Destinations acceptées : pages internes', all(destination_valable(x) for x in ('/kri', '/dashboard?x=1', '/audits')))

print('--- Connexion par mot de passe : paramètre next')
with A.app.app_context():
    u = db.session.get(M.User, ids['lecteur']); nom = u.username
for suite, attendu in (('/langue/dictionnaire-en.js?v=1', 'dictionnaire'), ('https://pirate.example/', 'pirate')):
    c2 = A.app.test_client()
    r = appel(c2, 'post', f'/auth/login_fullscreen?next={suite}', data={'username': nom, 'password': socle.MDP, 'remember_me': 'y'})
    loc = r.headers.get('Location') or ''
    verif(f'Connexion réussie, next={suite[:30]} ignoré', r.status_code == 302 and attendu not in loc
          and 'login' not in loc, f'{r.status_code} {loc}')
c3 = A.app.test_client()
r = appel(c3, 'post', '/auth/login_fullscreen?next=/audits', data={'username': nom, 'password': socle.MDP})
verif('next vers une page interne : respecté', (r.headers.get('Location') or '').endswith('/audits'), r.headers.get('Location'))

print(f'\n{sum(res)}/{len(res)} vérifications réussies')
sys.exit(0 if all(res) else 1)
