"""Le tableau de bord suit-il les modules du client et les permissions de chaque utilisateur ?"""
import sys
import socle
from socle import Muet, appel
with Muet():
    A, ids = socle.preparer()
import models as M
from models import db
CARTES = {'risques': 'TOTAL RISQUES', 'kri': 'KRI ACTIFS', 'logigrammes': 'LOGIGRAMMES', 'veille': 'VEILLES ACTIVES',
          'incidents': 'INCIDENTS ACTIFS', 'tickets': 'TICKETS SUPPORT', 'campagnes': 'CAMPAGNES', 'audit': 'AUDITS',
          'plans_action': "PLANS D&#39;ACTION", 'controle_n2': 'CONTRÔLES N2', 'pca': 'PLANS DE CONTINUITÉ'}
def cartes(role):
    r = appel(socle.navigateur(A, ids[role]), 'get', '/dashboard')
    t = r.data.decode('utf-8', 'ignore')
    return r.status_code, sorted(k for k, v in CARTES.items() if v in t)
res = []
def verif(nom, cond, detail):
    res.append(cond); print('OK   ' if cond else 'ÉCHEC', nom, '→', detail)
def regler(user, **p):
    with A.app.app_context():
        u = db.session.get(M.User, ids[user]); u.permissions = socle.perms(*[k for k, v in p.items() if v]); db.session.commit()
def modules(client_id, actifs):
    with A.app.app_context():
        c = db.session.get(M.Client, client_id); c.modules_actifs = actifs; db.session.commit()

regler('lecteur', can_manage_kri=True)
code, c = cartes('lecteur'); verif('Utilisateur avec la seule permission KRI : seule la carte KRI', c == ['kri'], f'{code} {c}')
regler('lecteur', can_manage_kri=True, can_manage_campaigns=True)
code, c = cartes('lecteur'); verif('On lui ajoute « gérer les campagnes » : la carte apparaît', 'campagnes' in c and 'kri' in c, c)
regler('lecteur')
code, c = cartes('lecteur'); verif('On lui retire tout : aucune carte de module', c == [], c)
regler('gestionnaire', can_manage_risks=True, can_manage_audit=True)
code, c = cartes('gestionnaire'); verif('Gestionnaire réglé sur risques + audit', set(c) == {'risques', 'audit'}, c)
from egalyx.modules_client import MODULES
tous = {k: True for k in MODULES}
modules(1, tous | {'kri': False, 'audit': False})
code, c = cartes('admin_a'); verif('Client sans module KRI ni Audit : l\'admin client ne les voit pas', 'kri' not in c and 'audit' not in c, c)
code, c = cartes('gestionnaire'); verif('… ni le gestionnaire (même avec la permission audit)', 'audit' not in c, c)
modules(1, None)
code, c = cartes('admin_a'); verif('Client sans restriction : l\'admin client voit tous les modules', len(c) >= 7, c)
regler('lecteur', can_view_campaigns=True, can_view_action_plans=True, can_view_controle_interne_n2=True)
code, c = cartes('lecteur'); verif('Permissions de consultation : campagnes, plans d\'action, contrôle N2', set(c) == {'campagnes', 'plans_action', 'controle_n2'}, c)
# Formule d'abonnement sans campagnes ni KRI, aucun choix explicite du super admin
with A.app.app_context():
    f = M.FormuleAbonnement(nom='Essentiel', code='ESS-REC')
    f.modules = dict(M.FormuleAbonnement.modules.default.arg) | {'campagnes_controle': False, 'suivi_kri': False}
    db.session.add(f); db.session.flush()
    cl = db.session.get(M.Client, 1); cl.formule_id = f.id; cl.modules_actifs = None; db.session.commit()
regler('gestionnaire', can_manage_campaigns=True, can_manage_kri=True, can_manage_risks=True)
code, c = cartes('admin_a'); verif('Formule sans campagnes ni KRI : l\'admin client ne les voit plus', 'campagnes' not in c and 'kri' not in c and 'risques' in c, c)
code, c = cartes('gestionnaire'); verif('… ni le gestionnaire qui a pourtant les permissions', c == ['risques'], c)
modules(1, {k: True for k in MODULES})
regler('gestionnaire', can_manage_campaigns=True, can_manage_kri=True, can_manage_risks=True)   # à redonner : refusées tant que le module manquait
code, c = cartes('gestionnaire'); verif('Le super admin active tout pour ce client : le choix explicite l\'emporte sur la formule', set(c) == {'risques', 'campagnes', 'kri'}, c)
print(f'{sum(res)}/{len(res)}'); sys.exit(0 if all(res) else 1)
