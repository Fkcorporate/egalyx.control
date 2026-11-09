"""KRI : le module activé par le super admin s'ouvre même si la formule ne le contient pas ;
désactivé, il reste bloqué. Pages : un script injecté ne doit pas casser les scripts de la page."""
import sys, re
import socle, objets
from socle import Muet, appel
with Muet():
    A, ids = socle.preparer()
    objets_a = objets.peupler_objets(A, ids)['a']
import models as M
from models import db
res = []
def verif(nom, cond, detail=''):
    res.append(bool(cond)); print('OK   ' if cond else 'ÉCHEC', nom, detail)
def page(role, url):
    c = socle.navigateur(A, ids[role]); r = appel(c, 'get', url)
    return r, r.data.decode('utf-8', 'ignore')

with A.app.app_context():
    f = M.FormuleAbonnement(nom='Essentiel recette', code='ESS-RECETTE', modules={'cartographie': True, 'audit_interne': True})
    db.session.add(f); db.session.flush()
    cl = db.session.get(M.Client, 1); cl.formule_id = f.id
    cl.modules_actifs = None; db.session.commit()

r, t = page('admin_a', '/kri')
verif('Formule sans KRI et aucun choix du super admin : KRI fermé', r.status_code != 200 or 'formule' in t.lower(), str(r.status_code))
with A.app.app_context():
    cl = db.session.get(M.Client, 1)
    from egalyx.modules_client import MODULES
    cl.modules_actifs = {m: True for m in MODULES}; M.marquer_json_modifie(cl, 'modules_actifs'); db.session.commit()
for _ in range(2):   # 2e passage : après la correction automatique des permissions (toutes les 5 min)
    with A.app.test_request_context():
        pass
    c = socle.navigateur(A, ids['admin_a'])
    with c.session_transaction() as s_:
        s_['last_permission_check'] = 0; s_['last_admin_check'] = 0
    r = appel(c, 'get', '/kri'); t = r.data.decode('utf-8', 'ignore')
with A.app.app_context():
    verif('La permission KRI de l\'admin n\'est plus retirée par la correction « selon la formule »',
          db.session.get(M.User, ids['admin_a']).permissions.get('can_manage_kri') is True)
verif('Le super admin active KRI pour le client : la page KRI s\'ouvre (plus de message « formule »)',
      r.status_code == 200 and "n'est pas inclus dans votre formule" not in t and 'formule_restricted' not in t, f'{r.status_code} {socle.cause(A)}')
with A.app.app_context():
    cl = db.session.get(M.Client, 1)
    cl.modules_actifs = {m: (m != 'kri') for m in MODULES}; M.marquer_json_modifie(cl, 'modules_actifs'); db.session.commit()
r, t = page('admin_a', '/kri')
verif('KRI désactivé pour le client : toujours fermé', r.status_code in (302, 403, 404) or 'formule' in t.lower(), str(r.status_code))
with A.app.app_context():
    cl = db.session.get(M.Client, 1); cl.modules_actifs = None; cl.formule_id = None; db.session.commit()

print('--- Réparation des administrateurs déjà touchés')
with A.app.app_context():
    u = db.session.get(M.User, ids['admin_a']); p = dict(u.permissions); p['can_manage_kri'] = False; u.permissions = p
    db.session.commit()
    from egalyx.ia import ecrire_reglage
    ecrire_reglage('reparation_permissions_admins_modules_v2', False)
    from egalyx.modules_client import _reparer_permissions_admins
    _reparer_permissions_admins(A.app)
    db.session.expire_all()
    verif('Au démarrage, l\'admin retrouve la permission KRI retirée à tort', db.session.get(M.User, ids['admin_a']).permissions.get('can_manage_kri') is True)
with A.app.app_context():
    cl = db.session.get(M.Client, 1); cl.modules_actifs = None; cl.formule_id = None; db.session.commit()

print('--- KRI dont les seuils sont déjà incohérents en base')
from sqlalchemy import text
import datetime as dt
with A.app.app_context():
    k = M.KRI(nom='KRI ancien', client_id=1, risque_id=objets_a['risque'], seuil_alerte=50, seuil_critique=80,
              sens_evaluation_seuil='superieur', frequence_mesure='mensuel', type_indicateur='kri')
    db.session.add(k); db.session.commit(); kid = k.id
    db.session.execute(text('UPDATE kri SET seuil_alerte = 80, seuil_critique = 50 WHERE id = :i'), {'i': kid}); db.session.commit()
r, t = page('gestionnaire', '/kri')
verif('La page KRI s\'ouvre malgré un KRI incohérent', r.status_code == 200, f'{r.status_code} {socle.cause(A)}')
verif('… et ce KRI porte « Seuils à corriger »', 'Seuils à corriger' in t)
r, t = page('gestionnaire', f'/kri/{kid}/detail')
verif('Fiche du KRI : ouverte, avec l\'explication', r.status_code == 200 and "doit être en dessous du seuil critique" in t, f'{r.status_code} {socle.cause(A)}')
from egalyx.kri_suivi import SeuilsIncoherents
with A.app.app_context():
    k = db.session.get(M.KRI, kid); k.nom = 'KRI ancien renommé'
    db.session.add(M.MesureKRI(kri_id=kid, valeur=60, date_mesure=dt.datetime.utcnow(), client_id=1))
    try:
        db.session.commit(); ok = True
    except SeuilsIncoherents:
        db.session.rollback(); ok = False
verif('Modifier autre chose ou saisir une mesure reste possible', ok)
with A.app.app_context():
    k = db.session.get(M.KRI, kid); k.seuil_alerte = 90
    try:
        db.session.commit(); refuse = False
    except SeuilsIncoherents:
        db.session.rollback(); refuse = True
    verif('Changer les seuils pour d\'autres seuils incohérents reste refusé', refuse)
    k = db.session.get(M.KRI, kid); k.seuil_alerte, k.seuil_critique = 50, 80; db.session.commit()
r, t = page('gestionnaire', '/kri')
verif('Une fois corrigé, le badge disparaît', 'Seuils à corriger' not in t)

print('--- Scripts des pages intacts')
for role, url in (('admin_a', '/dashboard-audit-global-complet'), ('admin_a', '/dashboard'), ('gestionnaire', '/kri')):
    r, t = page(role, url)
    if r.status_code != 200:
        print('     (', url, r.status_code, ')'); continue
    # aucun <script> injecté à l'intérieur d'un autre script
    morceaux = re.findall(r'<script\b[^>]*>(.*?)</script>', t, re.S)
    casse = [m for m in morceaux if '`' in m and m.count('`') % 2 == 1]
    verif(f'{url} : aucun script coupé en deux', not casse, f'{len(casse)} script(s) coupé(s)')
print(f'\n{sum(res)}/{len(res)} vérifications réussies')
sys.exit(0 if all(res) else 1)
