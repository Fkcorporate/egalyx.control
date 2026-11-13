"""Recette SÉCURITÉ : les routes de réparation et de mise au point (/fix…, /debug…, /test-…) sont introuvables.

La liste n'est pas écrite à la main : toutes les routes de l'application dont l'adresse a cette forme sont essayées,
avec leur méthode (GET ou POST), en visiteur, en utilisateur, en administrateur d'organisation et en super admin.
Une route de ce type ajoutée plus tard est donc testée (et bloquée) automatiquement.
"""
import os
import re
os.environ['EGALYX_COLLECTE_AUTO'] = '0'
os.environ.pop('EGALYX_ROUTES_REPARATION', None)
import socle
from socle import Muet, appel
res = []


def verif(nom, cond, detail=''):
    res.append(bool(cond)); print('OK   ' if cond else 'ÉCHEC', nom, detail)


with Muet():
    A, ids = socle.preparer()
from egalyx.menage import OUTILS_SUPER_ADMIN, est_reparation

regles = sorted((r for r in A.app.url_map.iter_rules() if est_reparation(r.rule)), key=lambda r: r.rule)
verif('routes de réparation trouvées dans l’application', len(regles) >= 50, str(len(regles)))
profils = {'visiteur': A.app.test_client(), 'utilisateur': socle.navigateur(A, ids['lecteur']),
           'administrateur': socle.navigateur(A, ids['admin_a']), 'super admin': socle.navigateur(A, ids['superadmin'])}
ouvertes = {p: [] for p in profils}
for r in regles:
    url = re.sub(r'<(?:int:)?[a-z_]+>', '1', r.rule)
    methode = 'GET' if 'GET' in r.methods else 'POST'
    for p, c in profils.items():
        code = appel(c, methode, url).status_code
        permis = p == 'super admin' and r.endpoint in OUTILS_SUPER_ADMIN
        if code != 404 and not permis:
            ouvertes[p].append(f'{methode} {r.rule} -> {code}')
for p in profils:
    verif(f'{p} : aucune route de réparation accessible', not ouvertes[p], '; '.join(ouvertes[p][:5]))

with Muet():
    c = profils['super admin']
    r = appel(c, 'GET', '/fix_all_audits_client')
verif('/fix_all_audits_client (modifiait les audits de toutes les organisations) : introuvable même en super admin', r.status_code == 404)
for p in ('visiteur', 'utilisateur', 'administrateur'):
    r = appel(profils[p], 'GET', '/super-admin/debug-filter')
    verif(f'outil super admin (debug-filter) : introuvable pour {p}', r.status_code == 404, str(r.status_code))
r = appel(profils['super admin'], 'GET', '/super-admin/debug-filter')
verif('outil super admin utilisé par un bouton : toujours ouvert au super admin', r.status_code != 404, str(r.status_code))

print('--- Pas de faux positif : les fonctions normales qui ressemblent restent ouvertes')
for nom in ('pca_stress_test_modal', 'set_progression_fixe_plan'):
    verif(f'{nom} n’est pas pris pour une route de réparation',
          not any(est_reparation(r.rule) for r in A.app.url_map.iter_rules() if r.endpoint == nom))
verif('/notifications/push/tester (bouton « tester ») non bloqué', not est_reparation('/notifications/push/tester'))

print('--- Réouverture d’urgence')
os.environ['EGALYX_ROUTES_REPARATION'] = '1'
r = appel(profils['super admin'], 'GET', '/debug-routes')
os.environ.pop('EGALYX_ROUTES_REPARATION', None)
verif('EGALYX_ROUTES_REPARATION=1 : le super admin retrouve l’accès le temps d’une intervention', r.status_code != 404, str(r.status_code))
r = appel(profils['super admin'], 'GET', '/debug-routes')
verif('… et c’est de nouveau fermé sans la variable', r.status_code == 404)

print(f'\n{sum(res)}/{len(res)} vérifications réussies')
