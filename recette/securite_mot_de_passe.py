"""Recette SÉCURITÉ : un mauvais mot de passe ne doit jamais ouvrir de session (faille corrigée le 12/11/2026)."""
import socle
from socle import Muet, appel
res = []


def verif(nom, cond, detail=''):
    res.append(bool(cond))
    print('OK   ' if cond else 'ÉCHEC', nom, detail)


with Muet():
    A, ids = socle.preparer()
import models as M
from models import db
with A.app.app_context():
    noms = {k: db.session.get(M.User, ids[k]).username for k in ('admin_a', 'gestionnaire', 'superadmin')}
    u = db.session.get(M.User, ids['lecteur'])
    r = u.check_password('faux')
    verif('check_password : mauvais mot de passe = faux dans un « if »', not r)
    ok, msg = u.check_password('faux')
    verif('… et se lit toujours comme (succès, message)', ok is False and isinstance(msg, str))
    verif('check_password : bon mot de passe = vrai', bool(u.check_password(socle.MDP)))
    db.session.rollback()
for role, nom in noms.items():
    c = A.app.test_client()
    r = c.post('/auth/login_fullscreen', base_url='https://www.egalyx.com', data={'username': nom, 'password': 'nimportequoi'})
    with c.session_transaction(base_url='https://www.egalyx.com') as s:
        connecte = '_user_id' in s
    verif(f'Connexion {role} avec un MAUVAIS mot de passe : refusée', not connecte and r.status_code == 200, f'{r.status_code} {r.headers.get("Location")}')
    c = A.app.test_client()
    r = c.post('/auth/login_fullscreen', base_url='https://www.egalyx.com', data={'username': nom, 'password': socle.MDP})
    with c.session_transaction(base_url='https://www.egalyx.com') as s:
        connecte = '_user_id' in s
    verif(f'Connexion {role} avec le bon mot de passe : acceptée', connecte and r.status_code in (302, 303), str(r.status_code))
c = A.app.test_client()
r = c.post('/login', base_url='https://www.egalyx.com', data={'username': noms['gestionnaire'], 'password': 'x'}, follow_redirects=False)
with c.session_transaction(base_url='https://www.egalyx.com') as s:
    verif('Ancienne adresse /login : mauvais mot de passe refusé', '_user_id' not in s, str(r.status_code))
print(f'\n{sum(res)}/{len(res)} vérifications réussies')
