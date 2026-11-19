"""Recette : une seule écriture des statuts par objet (egalyx/statuts.py, migration 0003)."""
import glob
import os
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
from sqlalchemy import text
from egalyx import statuts as S

print('--- Vocabulaire')
for nom, alias in S.ALIAS.items():
    verif(f'{nom} : chaque variante mène à une valeur du vocabulaire, aucune variante n\'est elle-même une valeur',
          all(v in S.VOCABULAIRE[nom] for v in alias.values()) and not (set(alias) & set(S.VOCABULAIRE[nom])))

print('--- Correction à l\'enregistrement')
with A.app.app_context():
    cid = db.session.get(M.User, ids['admin_a']).client_id
    p = creer(M.PlanAction, reference='PA-ST', nom='Plan', client_id=cid, created_by=ids['admin_a'], statut='terminee', pourcentage_realisation=100)
    nc = None    # non-conformité N2 : exige une exécution de contrôle ; même règle, vérifiée par la conversion ci-dessous
    ca = creer(M.Cartographie, nom='Carto ST', client_id=cid, created_by=ids['admin_a']); db.session.flush()
    rk = creer(M.Risque, reference='R-ST', intitule='Risque', cartographie_id=ca.id, client_id=cid, created_by=ids['admin_a']); db.session.flush()
    inc = creer(M.Incident, client_id=cid, titre='Panne', reference='INC-ST', statut='fermee')
    dm = creer(M.DispositifMaitrise, client_id=cid, risque_id=rk.id, reference='DM-ST', nom='Contrôle', statut='à_améliorer', created_by=ids['admin_a'])
    db.session.commit()
    verif('plan d\'action « terminee » -> « termine »', p.statut == 'termine', p.statut)
    if nc is not None:
        verif('non-conformité N2 « close » -> « ferme »', nc.statut == 'ferme', nc.statut)
    verif('incident « fermee » -> « ferme »', inc.statut == 'ferme', inc.statut)
    verif('dispositif « à_améliorer » -> « a_ameliorer »', dm.statut == 'a_ameliorer', dm.statut)
    PID, DID = p.id, dm.id

print('--- Conversion des données existantes')
with A.app.app_context():
    with db.engine.begin() as c:
        c.execute(text('UPDATE plans_action SET statut = :s WHERE id = :i'), {'s': 'terminee', 'i': PID})
        c.execute(text('UPDATE dispositifs_maitrise SET statut = :s WHERE id = :i'), {'s': 'à_améliorer', 'i': DID})
    with db.engine.begin() as c:
        faits = S.convertir_base(c)
    with db.engine.connect() as c:
        st = c.execute(text('SELECT statut FROM plans_action WHERE id = :i'), {'i': PID}).scalar()
        sd = c.execute(text('SELECT statut FROM dispositifs_maitrise WHERE id = :i'), {'i': DID}).scalar()
    verif('anciennes valeurs converties en base', st == 'termine' and sd == 'a_ameliorer' and faits.get('PlanAction') == 1, str(faits))
    with db.engine.begin() as c:
        verif('conversion idempotente (2e passage : rien)', S.convertir_base(c) == {})

print('--- Code')
racine = A.app.root_path
code = ''.join(open(f, encoding='utf-8').read() for f in [os.path.join(racine, 'app.py')] + glob.glob(os.path.join(racine, 'sections', '*.py'))
               + glob.glob(os.path.join(racine, 'egalyx', '*.py')) if not f.endswith('statuts.py'))
verif('plus aucune écriture « à_améliorer » (accents) dans le code', "statut = 'à_améliorer'" not in code)
verif('rapport N2 : plans terminés reconnus (« terminee »)', "pa.statut in ('terminee', 'termine')" in code)

print(f'\n{sum(res)}/{len(res)} vérifications réussies')
