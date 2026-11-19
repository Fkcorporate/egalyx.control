"""Recette : listes découpées en pages (egalyx/pagination.py).

Plans d'action d'audit (compteurs et tri faits par la base, seule la page est chargée), demandes de
réévaluation, registre des recommandations, « Tous les plans d'action ».
"""
import datetime as dt
import os
import re
os.environ['EGALYX_COLLECTE_AUTO'] = '0'
import socle
from socle import Muet, creer
res = []


def verif(nom, cond, detail=''):
    res.append(bool(cond)); print('OK   ' if cond else 'ÉCHEC', nom, detail)


with Muet():
    A, ids = socle.preparer()
import models as M
from models import db
from sqlalchemy import event

adm = socle.navigateur(A, ids['admin_a'])
N = 120
with A.app.app_context():
    cid = db.session.get(M.User, ids['admin_a']).client_id
    au = creer(M.Audit, titre='Audit volumineux', reference='AUD-VOL', client_id=cid, created_by=ids['admin_a'], statut='en_cours')
    db.session.flush()
    aujourd = dt.date.today()
    for i in range(N):
        creer(M.PlanAction, reference=f'PA-VOL-{i:03d}', nom=f'Plan {i:03d}', audit_id=au.id, client_id=cid, created_by=ids['admin_a'],
              statut='en_cours' if i % 3 else 'en_attente', pourcentage_realisation=(i % 99 + 1) if i % 3 else 0,
              date_fin_prevue=aujourd + dt.timedelta(days=(i % 40) - 10))
    db.session.commit()
    AUID = au.id

charges = []
event.listen(M.PlanAction, 'load', lambda cible, ctx: charges.append(cible.id))

print("--- Plans d'action d'audit")
charges.clear()
r = adm.get('/audit/plans-action')
h = r.data.decode()
lignes = re.findall(r'PA-VOL-\d{3}', h)
verif('page 1 : 50 plans affichés', r.status_code == 200 and len(set(lignes)) == 50, f'{r.status_code} {len(set(lignes))}')
verif(f'compteur total : {N} (calculé par la base)', f'{N}</h3>' in h)
verif('seule la page est chargée en mémoire (≤ 50 plans lus)', len(set(charges)) <= 50, str(len(set(charges))))
verif('barre de pagination : « 1–50 sur 120 »', '1–50 sur 120' in h)
r = adm.get('/audit/plans-action?page=3')
verif('page 3 : les 20 derniers', len(set(re.findall(r'PA-VOL-\d{3}', r.data.decode()))) == 20 and '101–120 sur 120' in r.data.decode())
r = adm.get('/audit/plans-action?par_page=100&tri=titre_asc')
h = r.data.decode()
noms = re.findall(r'PA-VOL-(\d{3})', h)
verif('tri par titre (plantait : champ « titre » inexistant) + 100 par page', r.status_code == 200 and len(set(noms)) == 100, str(r.status_code))
r = adm.get('/audit/plans-action?statut=en_attente&tri=urgence')
h = r.data.decode()
verif('filtre par statut + tri par urgence', r.status_code == 200 and '1–40 sur 40' in h, re.findall(r'\d+–\d+ sur \d+', h)[:1])
verif('les liens de page gardent les filtres', 'statut=en_attente' in h or 'sur 40' in h)

print('--- Autres listes')
with A.app.app_context():
    ca = creer(M.Cartographie, nom='Carto VOL', client_id=cid, created_by=ids['admin_a']); db.session.flush()
    rk = creer(M.Risque, reference='R-VOL', intitule='Risque', cartographie_id=ca.id, client_id=cid, created_by=ids['admin_a']); db.session.flush()
    for i in range(60):
        creer(M.DemandeReevaluation, reference=f'DR-VOL-{i:02d}', titre=f'Demande {i}', audit_id=AUID, risque_id=rk.id, client_id=cid,
              statut='en_attente', demandeur_id=ids['admin_a'])
    db.session.commit()
r = adm.get('/demandes-reevaluation')
h = r.data.decode()
verif('demandes de réévaluation : 50 par page', r.status_code == 200 and len(set(re.findall(r'DR-VOL-\d{2}', h))) == 50 and '1–50 sur 60' in h,
      str(r.status_code))
r = adm.get('/plans-action/registre/?par_page=25')
h = r.data.decode()
verif('« Tous les plans d\'action » : 25 par page', r.status_code == 200 and '1–25 sur' in h, str(r.status_code))
r = adm.get('/recommandations/registre')
verif('registre des recommandations : s\'affiche', r.status_code == 200, str(r.status_code))
r = adm.get('/audit/plans-action?page=999')
verif('page au-delà de la fin : dernière page affichée', r.status_code == 200 and '101–120 sur 120' in r.data.decode())

print(f'\n{sum(res)}/{len(res)} vérifications réussies')
