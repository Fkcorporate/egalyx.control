"""Plans d'action et recommandations : cohérents avec les modules du client et les permissions de chacun ?"""
import sys, datetime as dt
import socle, objets
from socle import Muet, appel
with Muet():
    A, ids = socle.preparer()
    O = objets.peupler_objets(A, ids)['a']
import models as M
from models import db
from egalyx.modules_client import MODULES

res = []
def verif(nom, cond, detail=''):
    res.append(bool(cond)); print('OK   ' if cond else 'ÉCHEC', nom, detail)
with A.app.app_context():
    n2 = M.User(username='resp_n2', email='n2@recette.test', role='utilisateur', client_id=1, is_active=True,
                permissions=socle.perms('can_view_controle_interne_n2', 'can_manage_controle_interne_n2', 'can_view_recommandations'))
    vue = M.User(username='consult_plans', email='cp@recette.test', role='utilisateur', client_id=1, is_active=True,
                 permissions=socle.perms('can_view_action_plans'))
    from werkzeug.security import generate_password_hash
    n2.password_hash = vue.password_hash = generate_password_hash(socle.MDP)
    db.session.add_all([n2, vue]); db.session.flush()
    ids['resp_n2'], ids['consult_plans'] = n2.id, vue.id
    audit = socle.creer(M.Audit, reference='AUD-CO', titre='Audit achats', type_audit='interne', client_id=1,
                        responsable_id=ids['gestionnaire'], created_by=ids['gestionnaire'])
    ra = socle.creer(M.Recommandation, reference='REC-CO', description='Recommandation d\'audit', type_recommandation='corrective',
                     audit_id=audit.id, client_id=1, urgence=2, impact_operationnel=2, responsable_id=ids['lecteur'],
                     taux_avancement=100, demande_cloture_le=dt.datetime.utcnow(), demande_cloture_par_id=ids['lecteur'])
    rn = M.RecommandationC2N(planification_id=O['planification'], titre='Recommandation N2', client_id=1, statut='acceptee',
                             responsable_id=ids['lecteur'], progression=100, demande_cloture_le=dt.datetime.utcnow(),
                             demande_cloture_par_id=ids['lecteur'])
    db.session.add(rn); db.session.commit(); aid, raid, rnid = audit.id, ra.id, rn.id

def nav(role):
    return socle.navigateur(A, ids[role])
def code(role, url, methode='get', **kw):
    r = appel(nav(role), methode, url, **kw); socle.cause(A); return r
def ouvre(r):
    return r.status_code == 200
def texte(r):
    return r.data.decode('utf-8', 'ignore')
def modules(actifs):
    with A.app.app_context():
        c = db.session.get(M.Client, 1); c.modules_actifs = actifs; db.session.commit()
TOUS = {k: True for k in MODULES}

print('--- Gestionnaire du contrôle N2 seulement (sans droit d\'audit)')
verif('Ouvre les recommandations du N2', ouvre(code('resp_n2', '/c2n/recommandations')), str(code('resp_n2', '/c2n/recommandations').status_code))
verif('Ouvre les plans d\'action du N2', ouvre(code('resp_n2', '/c2n/plans-action')), str(code('resp_n2', '/c2n/plans-action').status_code))
r = code('resp_n2', '/recommandations/registre')
verif('Ouvre le registre', ouvre(r), str(r.status_code))
verif('… y voit toutes les recommandations (le registre est transversal)', 'Recommandation N2' in texte(r) and 'REC-CO' in texte(r))
code('resp_n2', f'/recommandations/audit/{raid}/cloture', 'post', data={'decision': 'valider'})
with A.app.app_context():
    verif('Ne peut pas clôturer une recommandation d\'audit', db.session.get(M.Recommandation, raid).statut != 'termine')
code('resp_n2', f'/recommandations/c2n/{rnid}/cloture', 'post', data={'decision': 'valider'})
with A.app.app_context():
    verif('Peut clôturer une recommandation N2', db.session.get(M.RecommandationC2N, rnid).statut == 'realisee')

print('--- Consultation des plans d\'action seulement')
verif('Ouvre la liste des plans d\'action', ouvre(code('consult_plans', '/plans-action/independants')))
with A.app.app_context():
    avant = M.PlanAction.query.count()
code('consult_plans', '/plans-action/independant/nouveau', 'post', data={'nom': 'Plan pirate', 'reference': 'PIR-1'})
with A.app.app_context():
    verif('Ne peut pas créer de plan d\'action', M.PlanAction.query.count() == avant)
code('consult_plans', f'/plan-action-independant/{O["plan"]}/terminer', 'post')
with A.app.app_context():
    verif('Ne peut pas terminer un plan d\'action', (db.session.get(M.PlanAction, O['plan']).statut or '') != 'termine')

print('--- Client sans module Audit')
modules(TOUS | {'audit': False})
r = code('admin_a', '/recommandations/registre')
verif('Registre : plus de recommandation d\'audit', ouvre(r) and 'REC-CO' not in texte(r))
verif('Fiche d\'une recommandation d\'audit inaccessible', code('admin_a', f'/recommandations/audit/{raid}').status_code in (302, 403, 404))
verif('Rapport et réponses d\'audit inaccessibles', code('admin_a', f'/audit-suivi/{aid}/reponses').status_code in (302, 403, 404))
r = code('lecteur', '/recommandations/miennes')
verif('« Mes recommandations » du responsable : sans la recommandation d\'audit', 'REC-CO' not in texte(r))
r = code('lecteur', '/ma-semaine')
verif('« Ma semaine » : sans la recommandation d\'audit', 'Recommandation d&#39;audit' not in texte(r) and "Recommandation d'audit" not in texte(r))

print('--- Client sans module Contrôle N2')
modules(TOUS | {'controle_n2': False})
verif('Recommandations N2 inaccessibles', code('gestionnaire', '/c2n/recommandations').status_code in (302, 403, 404))
r = code('gestionnaire', '/recommandations/registre')
verif('Registre : plus de recommandation N2', ouvre(r) and 'Recommandation N2' not in texte(r))
r = code('resp_n2', '/recommandations/registre')
verif('Le registre (module à part) reste ouvert, sans les recommandations N2', ouvre(r) and 'Recommandation N2' not in texte(r))

print('--- Client sans module Plans d\'action')
modules(TOUS | {'plans_action': False})
verif('Liste des plans d\'action inaccessible', code('gestionnaire', '/plans-action/independants').status_code in (302, 403, 404))
verif('Plans d\'action d\'audit inaccessibles', code('gestionnaire', '/audit/plans-action').status_code in (302, 403, 404))
r = code('gestionnaire', '/dashboard')
verif('Pas de carte « Plans d\'action » au tableau de bord', "PLANS D&#39;ACTION" not in texte(r) and "PLANS D'ACTION" not in texte(r))
modules(None)

print(f'\n{sum(res)}/{len(res)} vérifications réussies')
sys.exit(0 if all(res) else 1)
