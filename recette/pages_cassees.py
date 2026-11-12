"""Recette : /ci, /debug/create-user-form, Gantt d'un plan d'action (avec et sans dates)."""
import datetime as dt
import socle
from socle import Muet
res = []


def verif(nom, cond, detail=''):
    res.append(bool(cond)); print('OK   ' if cond else 'ÉCHEC', nom, detail)


with Muet():
    A, ids = socle.preparer()
import objets
import models as M
from models import db
with Muet():
    try: objets.peupler_objets(A, ids)
    except TypeError: objets.peupler_objets(A)
c = A.app.test_client()
for u in ('/ci', '/cote-divoire'):
    r = c.get(u, base_url='https://www.egalyx.com')
    verif(f'{u} → accueil (301)', r.status_code == 301 and r.headers['Location'].endswith('/#contact'), str(r.status_code))
with A.app.app_context():
    uid = ids['gestionnaire']; cid = db.session.get(M.User, uid).client_id
    plans = [p.id for p in M.PlanAction.query.filter_by(client_id=cid).limit(2)]
    p2 = db.session.get(M.PlanAction, plans[-1]); auj = dt.date.today()
    p2.date_debut = p2.date_fin_prevue = auj   # plan d'un seul jour : division par zéro avant
    for s in p2.sous_actions[:1]:
        s.date_debut, s.date_fin_prevue = auj, auj
    db.session.commit()
cn = socle.navigateur(A, uid)
r = cn.get('/debug/create-user-form')
verif('/debug/create-user-form → 404', r.status_code == 404, str(r.status_code))
for pid in plans:
    r = cn.get(f'/plan-action/{pid}/gantt')
    verif(f'Gantt du plan {pid}', r.status_code == 200 and 'ganttTable' in r.get_data(as_text=True), f'{r.status_code} {socle.cause(A)}')
print(f'\n{sum(res)}/{len(res)}')
