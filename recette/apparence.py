"""PAQUET OPTIONNEL « nouvelle apparence » : apparence classique / nouvelle choisie par le super-admin pour chaque client."""
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


with A.app.app_context():
    cid_a = db.session.get(M.User, ids['admin_a']).client_id
r, t = go('gestionnaire', 'get', '/dashboard')
verif('Par défaut : apparence classique', r.status_code == 200 and 'egalyx-apparence-nouvelle' not in t)
verif('Utilisateur : pas d\'entrée « Apparence » dans le menu', '/compte/apparence/' not in t)
r, t = go('admin_a', 'get', '/dashboard')
verif('Admin client : pas d\'entrée « Apparence »', '/compte/apparence/' not in t)
for role in ('gestionnaire', 'admin_a'):
    r, _ = go(role, 'get', '/compte/apparence/')
    verif(f'{role} : page Apparence inaccessible', r.status_code == 404, str(r.status_code))
    r, _ = go(role, 'post', '/compte/apparence/', data={'client_id': cid_a, 'apparence': 'nouvelle'})
    verif(f'{role} : ne peut pas changer l\'apparence', r.status_code == 404, str(r.status_code))
r, t = go('superadmin', 'get', '/dashboard')
verif('Super-admin : entrée « Apparence » dans le menu', '/compte/apparence/' in t)
r, t = go('superadmin', 'get', '/compte/apparence/')
verif('Super-admin : liste des clients avec leur apparence', r.status_code == 200 and 'Apparence des clients' in t and 'Nouvelle' in t,
      f'{r.status_code} {socle.cause(A)}')
go('superadmin', 'post', '/compte/apparence/', data={'client_id': cid_a, 'apparence': 'nouvelle'})
for role in ('lecteur', 'gestionnaire', 'admin_a'):
    r, t = go(role, 'get', '/dashboard')
    verif(f'Client A « nouvelle » : appliquée pour {role}', 'egalyx-apparence-nouvelle' in t)
r, t = go('admin_b', 'get', '/dashboard')
verif('Client B non réglé : classique', 'egalyx-apparence-nouvelle' not in t)
for url in ('/incidents', '/c2n/planification', '/notifications/preferences'):
    r, _ = go('admin_a', 'get', url)
    verif(f'Page {url} avec la nouvelle apparence', r.status_code == 200, f'{r.status_code} {socle.cause(A)}')
go('superadmin', 'post', '/compte/apparence/', data={'client_id': cid_a, 'apparence': 'classique'})
r, t = go('admin_a', 'get', '/dashboard')
verif('Retour à « classique » par le super-admin : tout est rétabli', 'egalyx-apparence-nouvelle' not in t)
r, _ = go('superadmin', 'get', '/super-admin/clients')
verif('Page clients du super-admin', r.status_code == 200, f'{r.status_code} {socle.cause(A)}')
print(f'\n{sum(res)}/{len(res)} vérifications réussies')
sys.exit(0 if all(res) else 1)
