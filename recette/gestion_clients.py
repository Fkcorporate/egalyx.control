"""Gestion des clients par le super admin : suppression définitive, réinitialisation, export, permissions.
Les clés étrangères sont vérifiées par SQLite (comme PostgreSQL) : une suppression dans le mauvais ordre échoue."""
import io
import json
import sys
import zipfile

import socle
import objets
from socle import Muet, appel
from sqlalchemy import event, inspect as sa_inspect, text

with Muet():
    A, ids = socle.preparer()
    O = objets.peupler_objets(A, ids)
import models as M
from models import db

res = []


def verif(nom, cond, detail=''):
    res.append(bool(cond))
    print('OK   ' if cond else 'ÉCHEC', nom, detail)


def go(role, m, url, **kw):
    r = appel(socle.navigateur(A, ids[role]), m, url, **kw)
    return r, r.data.decode('utf-8', 'ignore')


def comptes(client_id):
    """Nombre de lignes par table portant client_id = client_id."""
    with A.app.app_context():
        insp = sa_inspect(db.engine)
        n = {}
        for t in insp.get_table_names():
            if 'client_id' in {c['name'] for c in insp.get_columns(t)}:
                v = db.session.execute(text(f'SELECT COUNT(*) FROM "{t}" WHERE client_id = :c'), {'c': client_id}).scalar()
                if v:
                    n[t] = v
        return n


with A.app.app_context():
    @event.listens_for(db.engine, 'connect')
    def _fk(dbapi_con, _rec):
        dbapi_con.execute('PRAGMA foreign_keys=ON')
    db.engine.dispose()
    # client B : un peu plus de données liées (sous-éléments sans client_id)
    cb = db.session.get(M.Client, 2)
    nom_b = cb.nom

print('--- Pages')
r, t = go('superadmin', 'get', '/super-admin/clients')
verif('Liste des clients : « Supprimer définitivement » proposé', r.status_code == 200 and 'supprimerClientDefinitivement' in t, str(r.status_code))
r, t = go('superadmin', 'get', '/super-admin/client/2')
verif('Fiche client : bouton de suppression branché', r.status_code == 200 and 'supprimerClientDefinitivement(2' in t, str(r.status_code))
r, t = go('superadmin', 'get', '/api/client/2/apercu-suppression')
d = json.loads(t) if r.status_code == 200 else {}
verif('Aperçu de ce qui sera supprimé', d.get('success') and d.get('total', 0) > 5 and 'user' in d.get('tables', {}), str(d.get('total')))

print('--- Permissions (boutons de la fiche)')
r, t = go('superadmin', 'get', f'/api/user/{ids["admin_b"]}/permissions')
verif('Voir les permissions d\'un utilisateur', r.status_code == 200 and json.loads(t).get('success'), str(r.status_code))
r, t = go('superadmin', 'post', f'/api/user/{ids["admin_b"]}/sync-permissions')
verif('Synchroniser un utilisateur', r.status_code == 200 and json.loads(t).get('success'), t[:120])
r, t = go('superadmin', 'post', '/api/client/2/sync-permissions')
verif('Synchroniser tout le client', r.status_code == 200 and json.loads(t).get('success'), t[:120])

print('--- Export')
r, _ = go('superadmin', 'get', '/api/client/2/export-data')
ok_zip = False
if r.status_code == 200:
    z = zipfile.ZipFile(io.BytesIO(r.data))
    users = json.loads(z.read('user.json')) if 'user.json' in z.namelist() else []
    ok_zip = 'clients.json' in z.namelist() and users and all('password_hash' not in u for u in users)
verif('Export zip du client (sans mots de passe)', ok_zip, str(r.status_code))

print('--- Garde-fous')
avant_a, avant_b = comptes(1), comptes(2)
r, _ = go('admin_a', 'post', '/api/client/2/terminate', json={'confirmation': nom_b})
verif('Un admin client ne peut pas supprimer un client', comptes(2) == avant_b, str(r.status_code))
r, _ = go('admin_b', 'post', '/api/client/2/terminate', json={'confirmation': nom_b})
verif('Ni le sien', comptes(2) == avant_b, str(r.status_code))
r, t = go('superadmin', 'post', '/api/client/2/terminate', json={'confirmation': 'mauvais nom'})
verif('Nom mal retapé : rien n\'est supprimé', r.status_code == 400 and comptes(2) == avant_b, str(r.status_code))
r, _ = go('superadmin', 'get', '/super-admin/client/2/suspendre')
with A.app.app_context():
    verif('Suspendre fonctionne', db.session.get(M.Client, 2).is_active is False, str(r.status_code))
r, _ = go('superadmin', 'get', '/super-admin/client/2/reactiver')
with A.app.app_context():
    verif('Réactiver fonctionne', db.session.get(M.Client, 2).is_active is True, str(r.status_code))

print('--- Suppression définitive')
r, t = go('superadmin', 'post', '/api/client/2/terminate', json={'confirmation': nom_b})
rep = json.loads(t) if t.strip().startswith('{') else {}
verif('Suppression acceptée (clés étrangères vérifiées)', r.status_code == 200 and rep.get('success'), t[:300])
with A.app.app_context():
    db.session.expire_all()
    verif('Le client a disparu', db.session.get(M.Client, 2) is None)
    verif('Ses utilisateurs aussi', db.session.get(M.User, ids['admin_b']) is None)
    reste = comptes(2)
    verif('Aucune ligne restante pour ce client, dans aucune table', not reste, str(reste))
    orphelins = db.session.execute(text('PRAGMA foreign_key_check')).fetchall()
    verif('Aucun lien cassé dans la base', not orphelins, str(orphelins[:5]))
with A.app.app_context():
    verif('La suppression est tracée au journal de la plateforme',
          M.SystemLog.query.filter(M.SystemLog.message.like('Client supprimé%')).count() == 1)
verif('L\'autre client est intact', comptes(1) == avant_a,
      str({k: (avant_a.get(k), v) for k, v in comptes(1).items() if avant_a.get(k) != v}))
r, t = go('superadmin', 'get', '/super-admin/clients')
verif('La liste des clients s\'affiche toujours', r.status_code == 200 and nom_b not in t, str(r.status_code))

print('--- Réinitialisation (client A)')
with A.app.app_context():
    nom_a = db.session.get(M.Client, 1).nom
    nb_users = M.User.query.filter_by(client_id=1).count()
    nb_dir = M.Direction.query.filter_by(client_id=1).count()
r, t = go('superadmin', 'post', '/api/client/1/reset-data', json={'confirmation': nom_a})
verif('Réinitialisation acceptée', r.status_code == 200 and json.loads(t).get('success'), t[:300])
with A.app.app_context():
    db.session.expire_all()
    verif('Client, utilisateurs et directions conservés',
          db.session.get(M.Client, 1) is not None and M.User.query.filter_by(client_id=1).count() == nb_users
          and M.Direction.query.filter_by(client_id=1).count() == nb_dir)
    verif('Risques, audits et cartographies effacés',
          M.Risque.query.filter_by(client_id=1).count() == 0 and M.Audit.query.filter_by(client_id=1).count() == 0
          and M.Cartographie.query.filter_by(client_id=1).count() == 0)
r, t = go('admin_a', 'get', '/dashboard')
verif('L\'admin du client réinitialisé se connecte toujours', r.status_code == 200, str(r.status_code))

print(f'\n{sum(res)}/{len(res)} vérifications réussies')
sys.exit(0 if all(res) else 1)
