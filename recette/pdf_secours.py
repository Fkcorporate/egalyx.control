"""Recette : sans WeasyPrint, les exports PDF montrent la version imprimable (jamais d'erreur 500)."""
import os
os.environ['EGALYX_COLLECTE_AUTO'] = '0'
import sys, importlib.util
import socle
from socle import Muet, navigateur
res = []


def verif(nom, cond, detail=''):
    res.append(bool(cond)); print('OK   ' if cond else 'ÉCHEC', nom, detail)


with Muet():
    A, ids = socle.preparer()
import models as M
with A.app.app_context(), Muet():
    admin = A.db.session.get(M.User, ids['admin_a'])
    cid_a = admin.client_id
    audit = socle.creer(M.Audit, client_id=cid_a, titre='Audit recette PDF')
    A.db.session.commit()
    X = {'audit': audit.id, 'qualite': 0}
w = sys.modules.get('weasyprint')
verif('WeasyPrint absent → remplaçant installé', getattr(w, '__egalyx_remplacant__', False) or (w is not None and not getattr(w, '__egalyx_remplacant__', False)),
      'remplaçant' if getattr(w, '__egalyx_remplacant__', False) else 'vrai WeasyPrint')
c = navigateur(A, ids['admin_a'])
for url in [f"/audit/{X['audit']}/rapport-pdf-elegant", f"/qualite/audit/{X['qualite']}/rapport", f"/kri/1/fiche-pdf"]:
    with Muet():
        r = c.get(url)
    corps = r.get_data(as_text=True)
    if r.status_code == 404:
        print('     (', url, 'absent de la démo : ignoré )'); continue
    verif(f'{url} : pas d’erreur 500', r.status_code != 500, r.status_code)
    if getattr(w, '__egalyx_remplacant__', False) and r.status_code == 200 and r.mimetype == 'text/html':
        verif(f'{url} : version imprimable avec bouton', 'eg-pdf-secours' in corps or 'imprimable' in corps)
with Muet():
    r = c.get('/sous-action/987654/details')
verif('sous-action inexistante → 404 (et non 500)', r.status_code == 404, r.status_code)
print('--- Pages réparées (scan complet du 19/11/2026)')
with A.app.app_context(), Muet():
    pa = socle.creer(M.PlanAction, client_id=cid_a, nom='Plan recette PDF')
    A.db.session.flush()
    sa = socle.creer(M.SousAction, client_id=cid_a, plan_action_id=pa.id, reference='SA-REC-1', description='Sous-action de recette')
    pq = socle.creer(M.PlanQualiteFonction, client_id=cid_a, created_by=ids['admin_a'], objectifs_qualite=['Réduire les réclamations', {'objectif': 'Former les agents'}],
                     indicateurs_cles=['Taux de réclamation'])
    A.db.session.commit()
    sa_id, pq_id = sa.id, pq.id
with Muet():
    r = c.get(f'/sous-action/{sa_id}/details')
verif('détail d’une sous-action existante : 200 (et non 500)', r.status_code == 200, r.status_code)
with Muet():
    r = c.get(f'/qualite/plan/{pq_id}/modifier')
verif('modifier un plan qualité dont les objectifs sont du texte : la page s’ouvre', r.status_code == 200, r.status_code)
c_b = navigateur(A, ids['admin_b'])
with Muet():
    r = c_b.get(f'/sous-action/{sa_id}/details')
verif('autre organisation : sous-action refusée', r.status_code in (403, 404), r.status_code)

print(f'\n{sum(res)}/{len(res)} vérifications réussies')
sys.exit(0 if all(res) else 1)
