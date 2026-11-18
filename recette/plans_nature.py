"""Recette : plans d'action d'audit, de risque et indépendants restent chacun dans leur module.

Avant : un plan d'audit pouvait s'ouvrir sur « Plan d'action risque » (fil d'Ariane des cartographies, retour vers
les plans des risques), notamment depuis l'espace de travail d'une sous-action ou depuis « Tous les plans d'action » ;
la page « Plans d'action » du menu Audit listait aussi les plans des risques.
"""
import os
import re
os.environ['EGALYX_COLLECTE_AUTO'] = '0'
import socle
from socle import Muet, appel, creer
res = []


def verif(nom, cond, detail=''):
    res.append(bool(cond)); print('OK   ' if cond else 'ÉCHEC', nom, detail)


with Muet():
    A, ids = socle.preparer()
import models as M
from models import db

adm = socle.navigateur(A, ids['admin_a'])
with A.app.app_context():
    cid = db.session.get(M.User, ids['admin_a']).client_id
    au = creer(M.Audit, titre='Audit des achats', reference='AUD-ACH', client_id=cid, created_by=ids['admin_a'], statut='en_cours')
    ca = creer(M.Cartographie, nom='Carto Achats', client_id=cid, created_by=ids['admin_a'])
    rk = creer(M.Risque, reference='R-ACH-1', intitule='Fraude fournisseur', cartographie_id=ca.id, client_id=cid, created_by=ids['admin_a'])
    db.session.flush()
    pa = creer(M.PlanAction, reference='PA-AUDIT-1', nom='Plan issu de l audit', audit_id=au.id, client_id=cid, created_by=ids['admin_a'])
    pr = creer(M.PlanAction, reference='PA-RISQUE-1', nom='Plan du risque', risque_id=rk.id, client_id=cid, created_by=ids['admin_a'])
    pi = creer(M.PlanAction, reference='PA-INDEP-1', nom='Plan independant', client_id=cid, created_by=ids['admin_a'])
    db.session.flush()
    sa = creer(M.SousAction, titre='Sous-action audit', plan_action_id=pa.id, client_id=cid, created_by=ids['admin_a']) \
        if 'titre' in M.SousAction.__table__.columns else creer(M.SousAction, plan_action_id=pa.id, client_id=cid)
    db.session.commit()
    PA, PR, PI, SA, AU = pa.id, pr.id, pi.id, sa.id, au.id


def cible(r):
    return r.headers.get('Location', '') if r.status_code in (301, 302) else ''


print('--- Chaque fiche s\'ouvre dans son module, quelle que soit l\'adresse utilisée')
r = appel(adm, 'GET', f'/plan-action-risque/{PA}')
verif('plan d\'audit ouvert par l\'adresse des risques -> fiche d\'audit', cible(r).endswith(f'/plan-action/{PA}'), cible(r))
r = appel(adm, 'GET', f'/plan-action/{PR}')
verif('plan de risque ouvert par l\'adresse d\'audit -> fiche du risque', cible(r).endswith(f'/plan-action-risque/{PR}'), cible(r))
r = appel(adm, 'GET', f'/plan-action-risque/{PI}')
verif('plan indépendant ouvert par l\'adresse des risques -> fiche indépendante', cible(r).endswith(f'/plan-action-independant/{PI}'), cible(r))
r = appel(adm, 'GET', f'/plan-action/{PA}')
verif('fiche d\'audit : s\'affiche normalement', r.status_code == 200, str(r.status_code))
h = r.data.decode()
verif('fiche d\'audit : Retour -> plans d\'action d\'audit', re.search(r'href="/audit/plans-action\?type=audit"[^>]*>\s*<i class="fas fa-arrow-left"', h) is not None)
r = appel(adm, 'GET', f'/plan-action-risque/{PR}')
verif('fiche du risque : s\'affiche normalement', r.status_code == 200, str(r.status_code))

print('--- Espace de travail (commun) : en-tête du bon module')
r = adm.get(f'/sous-action/{SA}/espace-travail', follow_redirects=True)
h = r.data.decode()
verif('sous-action d\'un plan d\'audit -> espace de travail du plan', r.status_code == 200 and 'PA-AUDIT-1' in h, str(r.status_code))
fil = h[h.find('aria-label="breadcrumb"'):h.find('<div class="page-title">')]
verif('… fil d\'Ariane d\'audit, sans « Cartographies »', 'Plans d&#39;action d&#39;audit' in fil or "Plans d'action d'audit" in fil, re.sub(r'\s+', ' ', re.sub('<[^>]+>', ' ', fil))[:160])
verif('… pas de lien vers les cartographies', 'Cartographies' not in fil and '/cartographie' not in fil)
verif('… Retour -> fiche d\'audit', f'href="/plan-action/{PA}" class="fk-btn"' in h)
h = appel(adm, 'GET', f'/plan-action/{PR}/espace-travail').data.decode()
fil = h[h.find('aria-label="breadcrumb"'):h.find('<div class="page-title">')]
verif('plan de risque : fil d\'Ariane des cartographies et du risque', 'Cartographies' in fil and 'R-ACH-1' in fil)
verif('… Retour -> fiche du risque', f'href="/plan-action-risque/{PR}" class="fk-btn"' in h)
r = appel(adm, 'GET', f'/plan-action/{PI}/espace-travail')
verif('plan indépendant -> son propre espace de travail', cible(r).endswith(f'/plan-action-independant/{PI}/espace-travail'), cible(r))

print('--- Menu Audit > Plans d\'action : uniquement l\'audit')
h = appel(adm, 'GET', '/audit/plans-action').data.decode()
verif('titre « Plans d\'action d\'audit »', "Plans d&#39;action d&#39;audit" in h or "Plans d'action d'audit" in h)
verif('le plan d\'audit est listé', 'PA-AUDIT-1' in h)
verif('le plan du risque n\'y est plus', 'PA-RISQUE-1' not in h)
verif('plus d\'onglet « Risque » ni de bouton « Voir Risques »', '?type=risque' not in h and 'Voir Risques' not in h)
h2 = appel(adm, 'GET', '/audit/plans-action?type=independant').data.decode()
verif('onglet Indépendants conservé', 'PA-INDEP-1' in h2 and 'PA-RISQUE-1' not in h2)
r = appel(adm, 'GET', '/audit/plans-action?type=risque')
verif('ancienne adresse ?type=risque -> « Tous les plans d\'action » (risques)', '/plans-action/registre' in cible(r) and 'source=risques' in cible(r), cible(r))

print('--- « Tous les plans d\'action » : chaque plan ouvre la fiche de son module')
h = appel(adm, 'GET', '/plans-action/registre/').data.decode()
lignes = {m.group(2): m.group(1) for m in re.finditer(r'<a href="([^"]+)"><strong>([^<]+)</strong>', h)}
verif('plan d\'audit -> fiche d\'audit', lignes.get('PA-AUDIT-1', '').endswith(f'/plan-action/{PA}'), lignes.get('PA-AUDIT-1'))
verif('plan du risque -> fiche du risque', lignes.get('PA-RISQUE-1', '').endswith(f'/plan-action-risque/{PR}'), lignes.get('PA-RISQUE-1'))
verif('plan indépendant -> fiche indépendante', lignes.get('PA-INDEP-1', '').endswith(f'/plan-action-independant/{PI}'), lignes.get('PA-INDEP-1'))
h = appel(adm, 'GET', '/plans-action/registre/?source=audit').data.decode()
verif('filtre « Audit » : seulement les plans d\'audit', 'PA-AUDIT-1' in h and 'PA-RISQUE-1' not in h and 'PA-INDEP-1' not in h)

print('--- Sécurité')
autre = socle.navigateur(A, ids['admin_b'])
r = appel(autre, 'GET', f'/plan-action-risque/{PA}')
verif('autre organisation : pas d\'aiguillage (la page refuse elle-même)', f'/plan-action/{PA}' not in cible(r) and r.status_code != 200, f'{r.status_code} {cible(r)}')
r = appel(adm, 'POST', f'/plan-action/{PR}/modifier-statut', data={'statut': 'en_cours'})
verif('les envois de formulaire ne sont jamais déviés', not cible(r).endswith(f'/plan-action-risque/{PR}'), cible(r))

print(f'\n{sum(res)}/{len(res)} vérifications réussies')
