"""Recette : espace opérateur — chaque droit et le périmètre s'appliquent sur chaque page, adresse directe comprise ;
écrans d'administration des opérateurs ; mise à niveau des opérateurs existants."""
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
A.app.config['WTF_CSRF_ENABLED'] = False
import models as M
from models import db
from egalyx import ia, operateurs as OP

# ------------------------------------------------------------------ données
with A.app.app_context():
    cid = db.session.get(M.User, ids['admin_a']).client_id
    cid_b = db.session.get(M.User, ids['admin_b']).client_id
    d_ops = creer(M.Direction, nom='Direction des opérations', client_id=cid)
    d_fin = creer(M.Direction, nom='Direction financière', client_id=cid)
    s_bo = creer(M.Service, nom='Back-office', direction_id=d_ops.id, client_id=cid, is_active=True)
    c_ops = creer(M.Cartographie, nom='Carto opérations', client_id=cid, direction_id=d_ops.id, is_archived=False)
    c_fin = creer(M.Cartographie, nom='Carto finance', client_id=cid, direction_id=d_fin.id, is_archived=False)
    creer(M.CampagneEvaluation, cartographie_id=c_ops.id, nom='Campagne 2026 ops', statut='en_cours', client_id=cid)
    creer(M.CampagneEvaluation, cartographie_id=c_fin.id, nom='Campagne 2026 fin', statut='en_cours', client_id=cid)
    r_ops = creer(M.Risque, reference='R-OPS', intitule='Fraude au guichet', cartographie_id=c_ops.id, client_id=cid, type_risque='Fraude', is_archived=False)
    r_fin = creer(M.Risque, reference='R-FIN', intitule='Erreur de clôture', cartographie_id=c_fin.id, client_id=cid, type_risque='Comptable', is_archived=False)
    c_b = creer(M.Cartographie, nom='Carto B', client_id=cid_b, is_archived=False)
    r_b = creer(M.Risque, reference='R-B', intitule='Risque autre organisation', cartographie_id=c_b.id, client_id=cid_b, is_archived=False)
    op = db.session.get(M.User, ids['operateur'])
    op.prenom, op.nom = 'Ibrahim', 'Bamba'
    p = M.PermissionOperateur(user_id=op.id, client_id=cid, created_by=ids['admin_a'], peut_evaluer_risques=True,
                              peut_executer_campagnes=True, peut_creer_plans_action=True, peut_voir_evaluations=True,
                              peut_modifier_evaluations=True, peut_voir_campagnes=True, peut_voir_plans_action=True,
                              peut_valider_campagnes=False, peut_executer_plans_action=False, peut_voir_dispositifs=False,
                              directions_autorisees=[d_ops.id], services_autorises=[], types_risques_autorises=[])
    db.session.add(p); db.session.flush(); op.operateur_permissions_id = p.id
    camp_ops = creer(M.CampagneControle, reference='CC-OPS', nom='Contrôle caisse', client_id=cid, direction_id=d_ops.id, createur_id=ids['admin_a'])
    camp_fin = creer(M.CampagneControle, reference='CC-FIN', nom='Contrôle trésorerie', client_id=cid, direction_id=d_fin.id, createur_id=ids['admin_a'])
    camp_confiee = creer(M.CampagneControle, reference='CC-CONF', nom='Contrôle confié', client_id=cid, direction_id=d_fin.id,
                         createur_id=ids['admin_a'], evaluateur_id=op.id)
    plan = creer(M.PlanAction, nom='Renforcer la caisse', reference='PA-OPS-1', client_id=cid, responsable_id=op.id, risque_id=r_ops.id, is_archived=False)
    db.session.commit()
    I = {k: v.id for k, v in dict(d_ops=d_ops, d_fin=d_fin, s_bo=s_bo, r_ops=r_ops, r_fin=r_fin, r_b=r_b, camp_ops=camp_ops,
                                  camp_fin=camp_fin, camp_confiee=camp_confiee, plan=plan, p=p).items()}

ia.ecrire_reglage(OP.MISE_A_NIVEAU, None)
opc = socle.navigateur(A, ids['operateur'])


def droits(**kw):
    with A.app.app_context():
        q = db.session.get(M.PermissionOperateur, I['p'])
        for k, v in kw.items():
            setattr(q, k, v)
        db.session.commit()


def refuse(r):
    loc = r.headers.get('Location') or ''
    return (r.status_code in (302, 303) and loc.endswith('/operateur/dashboard')) or r.status_code == 403


print('--- Mise à niveau des opérateurs existants (personne ne perd d’accès)')
appel(opc, 'GET', '/operateur/dashboard')
with A.app.app_context():
    q = db.session.get(M.PermissionOperateur, I['p'])
    verif('les droits jusqu’ici non appliqués sont accordés aux opérateurs existants',
          q.peut_valider_campagnes and q.peut_executer_plans_action and q.peut_voir_dispositifs, '')
verif('mise à niveau faite une seule fois (repère enregistré)', bool(ia.reglages().get(OP.MISE_A_NIVEAU)))
droits(peut_valider_campagnes=False)
appel(opc, 'GET', '/operateur/dashboard')
with A.app.app_context():
    verif('… et pas refaite ensuite (un droit retiré reste retiré)', db.session.get(M.PermissionOperateur, I['p']).peut_valider_campagnes is False)
droits(peut_valider_campagnes=True)

print('--- Périmètre : l’adresse directe ne contourne plus rien')
r = appel(opc, 'GET', f'/operateur/risque/{I["r_ops"]}/evaluer')
verif('risque de sa direction : évaluation ouverte', r.status_code == 200, str(r.status_code))
r = appel(opc, 'GET', f'/operateur/risque/{I["r_fin"]}/evaluer')
verif('risque d’une autre direction (adresse tapée) : refusé', refuse(r), f'{r.status_code} {r.headers.get("Location")}')
r = appel(opc, 'GET', f'/operateur/risque/{I["r_fin"]}/detail')
verif('… fiche du risque aussi refusée', refuse(r), str(r.status_code))
r = appel(opc, 'GET', f'/operateur/risque/{I["r_b"]}/detail')
verif('risque d’une autre organisation : refusé', refuse(r) or r.status_code == 404, str(r.status_code))
with opc.session_transaction() as s:
    msgs = [m for _c, m in s.get('_flashes', [])]
droits(directions_autorisees=[], types_risques_autorises=['Fraude'])
r1 = appel(opc, 'GET', f'/operateur/risque/{I["r_ops"]}/detail'); r2 = appel(opc, 'GET', f'/operateur/risque/{I["r_fin"]}/detail')
verif('catégories : seule la catégorie autorisée s’ouvre', r1.status_code == 200 and refuse(r2), f'{r1.status_code} {r2.status_code}')
droits(directions_autorisees=[], types_risques_autorises=[])
r = appel(opc, 'GET', f'/operateur/risque/{I["r_fin"]}/detail')
verif('rien de coché = toute l’organisation', r.status_code == 200, str(r.status_code))
droits(directions_autorisees=[I['d_ops']])
with A.app.app_context():
    pr = M.ParametresRisque.query.filter_by(client_id=cid).first() if hasattr(M, 'ParametresRisque') else None
    c = db.session.get(M.Cartographie, db.session.get(M.Risque, I['r_fin']).cartographie_id)
    c.valideur_operateurs_id = ids['operateur']; db.session.commit(); c_fin_id = c.id
r = appel(opc, 'GET', f'/operateur/risque/{I["r_fin"]}/evaluer')
verif('valideur désigné : ouvre l’évaluation à valider, même hors de son périmètre', r.status_code == 200, str(r.status_code))
with A.app.app_context():
    db.session.get(M.Cartographie, c_fin_id).valideur_operateurs_id = None; db.session.commit()

print('--- Évaluer les risques')
droits(peut_evaluer_risques=False)
r = appel(opc, 'GET', f'/operateur/risque/{I["r_ops"]}/evaluer')
verif('case décochée : la page d’évaluation est refusée, même par l’adresse', refuse(r), str(r.status_code))
with opc.session_transaction() as s:
    msgs = [m for _c, m in s.get('_flashes', [])]
verif('… avec un message clair', any('évaluer les risques' in m for m in msgs), str(msgs[-1:]))
r = appel(opc, 'POST', f'/operateur/risque/{I["r_ops"]}/evaluer', data={'action': 'phase1', 'impact': 3, 'probabilite': 3, 'niveau_maitrise': 3})
with A.app.app_context():
    n = M.EvaluationRisque.query.filter_by(risque_id=I['r_ops']).count()
verif('… et l’envoi du formulaire n’enregistre rien', refuse(r) and n == 0, f'{r.status_code} {n}')
r = appel(opc, 'GET', f'/operateur/risque/{I["r_ops"]}/detail')
verif('la consultation de la fiche reste possible', r.status_code == 200)
droits(peut_evaluer_risques=True)

print('--- Dispositifs de maîtrise')
with A.app.app_context():
    creer(M.DispositifMaitrise, nom='Double contrôle de caisse', risque_id=I['r_ops'], client_id=cid); db.session.commit()
h = appel(opc, 'GET', f'/operateur/risque/{I["r_ops"]}/detail').data.decode()
verif('« voir les dispositifs » coché : section affichée', 'Double contrôle de caisse' in h)
droits(peut_voir_dispositifs=False)
h = appel(opc, 'GET', f'/operateur/risque/{I["r_ops"]}/detail').data.decode()
verif('décoché : section masquée', 'Double contrôle de caisse' not in h)
droits(peut_voir_dispositifs=True)

print('--- Campagnes de contrôle')
r = appel(opc, 'GET', f'/operateur/campagne/{I["camp_ops"]}/detail')
verif('campagne de sa direction : visible', r.status_code == 200, str(r.status_code))
r = appel(opc, 'GET', f'/operateur/campagne/{I["camp_fin"]}/detail')
verif('campagne d’une autre direction : refusée', refuse(r) or r.status_code == 302, str(r.status_code))
r = appel(opc, 'GET', f'/operateur/campagne/{I["camp_fin"]}/executer')
verif('… exécution par adresse directe : refusée', refuse(r), f'{r.status_code} {r.headers.get("Location")}')
r = appel(opc, 'GET', f'/operateur/campagne/{I["camp_confiee"]}/detail')
verif('campagne confiée (hors de sa direction) : visible', r.status_code == 200, str(r.status_code))
droits(peut_voir_campagnes=False, peut_executer_campagnes=False, peut_valider_campagnes=False)
for u in ('/operateur/campagnes', f'/operateur/campagne/{I["camp_ops"]}/detail', f'/operateur/campagne/{I["camp_ops"]}/statistiques'):
    r = appel(opc, 'GET', u)
    verif(f'« voir les campagnes » décoché : {u} refusé', refuse(r), str(r.status_code))
h = appel(opc, 'GET', '/operateur/dashboard').data.decode()
verif('… et le menu « Campagnes » disparaît', 'title="Campagnes"' not in h)
droits(peut_voir_campagnes=True)
r = appel(opc, 'GET', '/operateur/campagne/creer')
verif('« créer et réaliser » décoché : création refusée', refuse(r), str(r.status_code))
r = appel(opc, 'POST', f'/operateur/campagne/{I["camp_ops"]}/demarrer')
verif('… démarrage refusé', refuse(r), str(r.status_code))
r = appel(opc, 'POST', f'/operateur/campagne/{I["camp_ops"]}/ajouter-anomalie', data={'titre': 'x'}, headers={'X-Requested-With': 'XMLHttpRequest'})
verif('… ajout d’anomalie refusé (réponse 403 pour la page)', r.status_code == 403, str(r.status_code))
r = appel(opc, 'POST', f'/operateur/campagne/{I["camp_confiee"]}/valider', data={'action': 'approuve'})
verif('« valider » décoché : validation refusée', refuse(r), str(r.status_code))
r = appel(opc, 'POST', f'/operateur/campagne/{I["camp_confiee"]}/rejeter', data={'raison': 'x'})
verif('… rejet refusé', refuse(r), str(r.status_code))
droits(peut_executer_campagnes=True, peut_valider_campagnes=True)
r = appel(opc, 'GET', '/operateur/campagne/creer')
verif('cases recochées : création de campagne de nouveau possible', r.status_code == 200, str(r.status_code))
gest = socle.navigateur(A, ids['gestionnaire'])
r = appel(gest, 'POST', f'/operateur/campagne/{I["camp_fin"]}/rejeter', data={'raison': 'x'})
verif('un gestionnaire (pas opérateur) n’est pas concerné par ces cases', r.status_code != 403 and '/operateur/dashboard' not in (r.headers.get('Location') or ''), str(r.status_code))

print('--- Plans d’action')
h = appel(opc, 'GET', '/operateur/plans-action').data.decode()
verif('ses plans sont listés', 'Renforcer la caisse' in h)
droits(directions_autorisees=[])
h = appel(opc, 'GET', '/operateur/plans-action').data.decode()
verif('sans restriction de direction : ses plans restent listés (la liste était vide avant)', 'Renforcer la caisse' in h)
droits(directions_autorisees=[I['d_ops']])
droits(peut_executer_plans_action=False)
r = appel(opc, 'POST', f'/operateur/plan-action/{I["plan"]}/commenter', data={'contenu': 'Avancement ok'})
with A.app.app_context():
    n = M.CommentairePlanAction.query.filter_by(plan_action_id=I['plan']).count()
verif('« faire avancer » décoché : commentaire refusé, rien enregistré', refuse(r) and n == 0, f'{r.status_code} {n}')
r = appel(opc, 'POST', f'/operateur/plan-action/{I["plan"]}/ajouter-sous-action', data={'titre': 'x'})
verif('… sous-action refusée', refuse(r), str(r.status_code))
r = appel(opc, 'POST', f'/operateur/plan-action/{I["plan"]}/suivre', data={'progression': '50'})
verif('… mise à jour de l’avancement refusée', refuse(r), str(r.status_code))
r = appel(opc, 'GET', f'/operateur/plan-action/{I["plan"]}/suivre')
verif('… mais le plan reste consultable', r.status_code == 200, str(r.status_code))
droits(peut_executer_plans_action=True)
r = appel(opc, 'POST', f'/operateur/plan-action/{I["plan"]}/commenter', data={'contenu': 'Avancement ok'})
with A.app.app_context():
    n = M.CommentairePlanAction.query.filter_by(plan_action_id=I['plan']).count()
verif('recoché : commentaire enregistré', n == 1, f'{r.status_code} {n}')
droits(peut_voir_plans_action=False, peut_executer_plans_action=False)
r = appel(opc, 'GET', '/operateur/plans-action')
verif('« voir ses plans » décoché : liste refusée', refuse(r), str(r.status_code))
h = appel(opc, 'GET', '/operateur/dashboard').data.decode()
verif('… et le menu « Mes plans » disparaît', 'title="Mes plans"' not in h)
droits(peut_voir_plans_action=True, peut_executer_plans_action=True)

print('--- Administration des opérateurs')
adm = socle.navigateur(A, ids['admin_a'])
h = appel(adm, 'GET', '/admin/operateurs').data.decode()
verif('liste : nom complet de l’opérateur', 'Ibrahim Bamba' in h)
verif('liste : périmètre en clair (plus « #3 »)', 'Direction des opérations' in h and f'>#{I["d_ops"]}<' not in h)
verif('liste : droits affichés', 'Évaluer les risques' in h and 'Faire avancer ses plans' in h)
verif('ajout : un sélecteur unique (plus une fenêtre par utilisateur)', 'id="opaChoix"' in h and 'promoteModal' not in h)
verif('valideurs des évaluations : section conservée', 'Validation des évaluations faites par les opérateurs' in h)
h = appel(adm, 'GET', f'/admin/operateur/{ids["operateur"]}/permissions').data.decode()
verif('droits : les 7 droits proposés', all(f'name="{d}"' in h for d in OP.TOUS_DROITS), str([d for d in OP.TOUS_DROITS if f'name="{d}"' not in h]))
verif('droits : directions et services en cases à cocher (plus de Ctrl + clic)', 'name="directions" value="%d"' % I['d_ops'] in h and 'Ctrl+clic' not in h and '<select' not in h.split('opdForm', 1)[1].split('</form>', 1)[0])
verif('droits : catégories de risques proposées', 'name="types_risques" value="Fraude"' in h)
form = {'user_id': ids['operateur'], 'peut_evaluer_risques': 'on', 'peut_executer_campagnes': 'on', 'directions': [str(I['d_fin'])],
        'services': [], 'types_risques': ['Comptable']}
r = appel(adm, 'POST', f'/admin/operateur/{ids["operateur"]}/permissions', data=form)
with A.app.app_context():
    q = db.session.get(M.PermissionOperateur, I['p'])
    verif('enregistrement : droits et périmètre', r.status_code in (302, 303) and q.directions_autorisees == [I['d_fin']]
          and q.types_risques_autorises == ['Comptable'] and q.peut_evaluer_risques and not q.peut_valider_campagnes, str(r.status_code))
    verif('« réaliser des campagnes » coché : « voir les campagnes » coché d’office', q.peut_voir_campagnes)
lect = ids['lecteur']
r = appel(adm, 'GET', f'/admin/operateur/nouveau?user_id={lect}')
verif('ajouter un opérateur : page des droits pré-remplie', r.status_code == 200 and 'Faire de' in r.data.decode())
r = appel(adm, 'POST', '/admin/operateur/nouveau', data={'user_id': lect, 'peut_voir_plans_action': 'on', 'peut_executer_plans_action': 'on'})
with A.app.app_context():
    u = db.session.get(M.User, lect); q = OP.droits_de(u)
    verif('ajout enregistré : opérateur avec ses droits', u.is_operateur and q is not None and q.peut_executer_plans_action and not q.peut_evaluer_risques, str(r.status_code))
r = appel(adm, 'POST', f'/admin/operateur/{lect}/retrograder')
with A.app.app_context():
    u = db.session.get(M.User, lect)
    verif('retirer le rôle : compte conservé, plus opérateur', u is not None and not u.is_operateur and u.is_active)
r = appel(adm, 'GET', f'/admin/operateur/nouveau?user_id={ids["admin_a"]}')
verif('un administrateur ne peut pas devenir opérateur', r.status_code in (302, 303))
r = appel(socle.navigateur(A, ids['admin_b']), 'GET', f'/admin/operateur/{ids["operateur"]}/permissions')
verif('autre organisation : opérateur introuvable', r.status_code == 404, str(r.status_code))
r = appel(socle.navigateur(A, ids['gestionnaire']), 'GET', '/admin/operateurs')
verif('réservé aux administrateurs', r.status_code in (302, 303), str(r.status_code))
r = appel(socle.navigateur(A, ids['gestionnaire']), 'POST', '/admin/operateur/promouvoir', data={'user_id': lect})
with A.app.app_context():
    verif('… y compris l’ancienne adresse de promotion', not db.session.get(M.User, lect).is_operateur)

print(f'\n{sum(res)}/{len(res)} vérifications réussies')
