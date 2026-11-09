"""Le super admin désactive puis réactive des modules : les menus reviennent, les droits ne sont pas perdus."""
import sys
import socle, objets
from socle import Muet, appel
with Muet():
    A, ids = socle.preparer()
    objets.peupler_objets(A, ids)
import models as M
from models import db
from egalyx.modules_client import MODULES
res = []
def verif(nom, cond, detail=''):
    res.append(bool(cond)); print('OK   ' if cond else 'ÉCHEC', nom, detail)
def page(role, url, m='get', **kw):
    r = appel(socle.navigateur(A, ids[role]), m, url, **kw); return r, r.data.decode('utf-8', 'ignore')
def perms(role):
    with A.app.app_context():
        db.session.expire_all(); return dict(db.session.get(M.User, ids[role]).permissions or {})

LOGI = '/liste_logigrammes'
r, _ = page('superadmin', '/super-admin/client/1/modules', 'post', data={'modules': ['cartographie', 'audit']})
avant_g = perms('gestionnaire')
verif('Gestionnaire : droit KRI conservé en base pendant que KRI est désactivé', avant_g.get('can_manage_kri') is True, str(avant_g.get('can_manage_kri')))
r, t = page('admin_a', '/dashboard')
verif('KRI désactivé : absent du menu', 'liste_kri' not in t and '/kri"' not in t)
# l'admin enregistre les permissions du gestionnaire pendant que KRI est désactivé
r, t = page('admin_a', f'/client-admin/utilisateur/{ids["gestionnaire"]}/permissions')
verif('Page des permissions accessible', r.status_code == 200, str(r.status_code))
page('admin_a', f'/client-admin/utilisateur/{ids["gestionnaire"]}/permissions', 'post',
     data={'can_manage_risks': 'y', 'can_view_dashboard': 'y', 'can_manage_kri': 'y'})
verif('Module désactivé : sa permission ne peut pas être changée depuis la page', perms('gestionnaire').get('can_manage_kri') is True)
with A.app.app_context():
    u = db.session.get(M.User, ids['admin_a']); p = dict(u.permissions)
    for k in ('can_manage_kri', 'can_manage_incidents', 'can_manage_logigram', 'can_manage_bcp', 'can_manage_campaigns'):
        p[k] = False
    u.permissions = p; db.session.commit()
r, _ = page('superadmin', '/super-admin/client/1/modules', 'post', data={'modules': list(MODULES)})
p = perms('admin_a')
verif('Réactivation de tous les modules : l\'admin reçoit les droits des modules ajoutés',
      all(p.get(k) for k in ('can_manage_kri', 'can_manage_incidents', 'can_manage_logigram', 'can_manage_bcp', 'can_manage_campaigns')),
      str({k: p.get(k) for k in ('can_manage_kri', 'can_manage_incidents', 'can_manage_logigram')}))
r, t = page('admin_a', '/dashboard')
for lien, nom in (('/kri', 'KRI'), ('/incidents', 'Incidents'), (LOGI, 'Logigrammes')):
    verif(f'Menu de l\'admin : {nom} présent', f'href="{lien}' in t or f"href='{lien}" in t)
verif('Plus de « Valideur des opérateurs » dans le menu', 'Valideur des opérateurs' not in t)
r, t = page('admin_a', '/cartographie')
verif('Le bouton « Valideurs des opérateurs » est dans les cartographies', 'Valideurs des opérateurs' in t, str(r.status_code))
verif('Le gestionnaire retrouve KRI (droit conservé)', perms('gestionnaire').get('can_manage_kri') is True)
with A.app.app_context():
    cl = db.session.get(M.Client, 1); cl.modules_actifs = None; db.session.commit()
print(f'\n{sum(res)}/{len(res)} vérifications réussies')
sys.exit(0 if all(res) else 1)
