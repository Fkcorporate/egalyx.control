"""Tableau de bord stratégique : vigilance quand aucun KRI n'est suivi, aucun incident déclaré, plan sans responsable."""
import sys, datetime as dt
import socle, objets
from socle import Muet, appel
with Muet():
    A, ids = socle.preparer()
    O = objets.peupler_objets(A, ids)['a']
import models as M
from models import db
res = []
def verif(nom, cond, detail=''):
    res.append(bool(cond)); print('OK   ' if cond else 'ÉCHEC', nom, detail)
with A.app.app_context():
    p = db.session.get(M.PlanAction, O['plan']); p.statut = 'en_cours'; p.responsable_id = None
    p.date_fin_prevue = dt.date.today() - dt.timedelta(days=20); db.session.commit()
c = socle.navigateur(A, ids['admin_a'])
r = appel(c, 'get', '/dashboard-strategique'); err = socle.cause(A)
t = r.data.decode('utf-8', 'ignore')
verif('La page s\'ouvre', r.status_code == 200, f'{r.status_code} {err}')
verif('Aucun KRI : « Aucun KRI suivi » (et non « 0 en alerte »)', 'Aucun KRI suivi dans ce périmètre' in t)
verif('Aucun incident sur 12 mois : signalé', 'Aucun incident déclaré depuis 12 mois' in t)
verif('Plan en retard sans responsable : signalé', 'sans responsable' in t and 'Sans responsable' in t)
verif('Explication du score net décimal', '9,6' in t)
with A.app.app_context():
    p = db.session.get(M.PlanAction, O['plan']); p.responsable_id = ids['gestionnaire']
    disp = socle.creer(M.DispositifMaitrise, **{k: v for k, v in dict(nom='Contrôle', client_id=1, risque_id=O['risque']).items() if hasattr(M.DispositifMaitrise, k)})
    socle.creer(M.Incident, **{k: v for k, v in dict(titre='Panne', client_id=1, risque_id=O['risque'], dispositif_id=disp.id,
                                date_occurrence=dt.datetime.utcnow() - dt.timedelta(days=200),
                                reference='INC-1', created_by=ids['gestionnaire']).items() if hasattr(M.Incident, k)})
    db.session.commit()
t = appel(c, 'get', '/dashboard-strategique').data.decode('utf-8', 'ignore'); socle.cause(A)
verif('Avec un responsable : plus d\'alerte', 'Sans responsable' not in t)
verif('Un incident déclaré il y a 200 jours : plus d\'alerte « aucune déclaration »', 'Aucun incident déclaré depuis 12 mois' not in t)
print(f'{sum(res)}/{len(res)}'); sys.exit(0 if all(res) else 1)
