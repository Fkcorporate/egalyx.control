"""Cartographie : évaluation en 3 phases par campagne ; opérateurs avec ou sans valideur désigné."""
import sys
import socle, objets
from socle import Muet, appel
with Muet():
    A, ids = socle.preparer()
    O = objets.peupler_objets(A, ids)['a']
import models as M
from models import db
from werkzeug.security import generate_password_hash
res = []
def verif(nom, cond, detail=''):
    res.append(bool(cond)); print('OK   ' if cond else 'ÉCHEC', nom, detail)
with A.app.app_context():
    ev = M.User(username='evaluateur', email='ev@recette.test', role='utilisateur', client_id=1, is_active=True,
                permissions=socle.perms('can_manage_risks'))
    ev.password_hash = generate_password_hash(socle.MDP); db.session.add(ev)
    po = M.PermissionOperateur(user_id=ids['operateur'], client_id=1, peut_evaluer_risques=True, peut_voir_evaluations=True)
    db.session.add(po); db.session.flush()
    db.session.get(M.User, ids['operateur']).operateur_permissions_id = po.id
    M.CampagneEvaluation.query.filter_by(cartographie_id=O['carto']).delete(); db.session.commit(); ids['evaluateur'] = ev.id
def nav(r): return socle.navigateur(A, ids[r])
def go(r, m, url, **kw):
    x = appel(nav(r), m, url, **kw); return x, socle.cause(A)
def eval_(rid):
    with A.app.app_context():
        e = M.EvaluationRisque.query.filter_by(risque_id=rid).order_by(M.EvaluationRisque.id.desc()).first()
        if e: db.session.expunge(e)
        return e
rid = O['risque']

with A.app.app_context():
    avant = M.CampagneEvaluation.query.filter_by(cartographie_id=O['carto']).count()
r, e = go('evaluateur', 'get', f'/risque/{rid}/evaluation-triphase')
with A.app.app_context():
    apres = M.CampagneEvaluation.query.filter_by(cartographie_id=O['carto']).count()
verif('Ouvrir l\'évaluation sans campagne ne crée pas de campagne en douce', apres == avant, f'{avant} -> {apres}')
go('gestionnaire', 'post', f'/cartographie/{O["carto"]}/nouvelle-campagne', data={'nom': 'Campagne 2026'})
with A.app.app_context():
    c1id = M.CampagneEvaluation.query.filter_by(cartographie_id=O['carto'], statut='en_cours').first().id

print('--- Cadres : fonctionnement d\'avant')
go('evaluateur', 'post', f'/risque/{rid}/evaluation-triphase', data={'submit_phase1': '1', 'impact_pre': '4', 'probabilite_pre': '4',
   'niveau_maitrise_pre': '2', 'referent_pre_evaluation_id': str(ids['evaluateur'])})
verif('Phase 1', eval_(rid) and eval_(rid).campagne_id == c1id)
go('evaluateur', 'post', f'/risque/{rid}/evaluation-triphase', data={'submit_phase2': '1', 'statut_validation': 'valide', 'impact_val': '4',
   'probabilite_val': '3', 'niveau_maitrise_val': '3'})
verif('Phase 2 : comme avant (pas de contrôle supplémentaire)', eval_(rid).statut_validation == 'valide')
go('evaluateur', 'post', f'/risque/{rid}/evaluation-triphase', data={'submit_phase3': '1', 'impact_conf': '4', 'probabilite_conf': '3', 'niveau_maitrise_conf': '3'})
x = eval_(rid)
verif('Phase 3 : comme avant, score net calculé', x.evaluateur_final_id == ids['evaluateur'] and x.score_risque_net is not None, f'{x.score_risque_net}')

print('--- Opérateurs sans valideur désigné : comme avant')
rid2 = O['risque_propose']
with A.app.app_context():
    rp = db.session.get(M.Risque, rid2); rp.statut = 'actif'; db.session.commit()
r, e = go('operateur', 'post', f'/operateur/risque/{rid2}/evaluer', data={'action': 'phase1', 'impact': '3', 'probabilite': '4', 'niveau_maitrise': '3'})
x = eval_(rid2)
verif('L\'opérateur pré-évalue', x and x.impact_pre == 3, f'{r.status_code} {e}')
go('operateur', 'post', f'/operateur/risque/{rid2}/evaluer', data={'action': 'phase2', 'impact_val': '3', 'probabilite_val': '4', 'niveau_maitrise_val': '3'})
verif('… et valide lui-même : en attente de confirmation de l\'administrateur', eval_(rid2).statut_validation == 'en_attente_admin')

print('--- Opérateurs avec un valideur désigné (Paramètres > Risques)')
r, e = go('admin_a', 'get', '/parametres/risques/')
t = r.data.decode('utf-8', 'ignore')
verif('Le réglage figure dans Paramètres > Risques', r.status_code == 200 and 'valideur_evaluations_operateurs_id' in t, f'{r.status_code} {e}')
with A.app.app_context():
    from egalyx.parametres_risque import objet_parametres
    p = objet_parametres(1)
    if p is None:
        p = M.ParametresRisque(client_id=1); db.session.add(p)
    p.valideur_evaluations_operateurs_id = ids['validateur']
    M.EvaluationRisque.query.filter_by(risque_id=rid2).delete(); db.session.commit()
    from egalyx.parametres_risque import vider_cache
    vider_cache(1)
    n_avant = M.Notification.query.filter_by(destinataire_id=ids['validateur'], type_notification='evaluation_a_valider').count()
go('operateur', 'post', f'/operateur/risque/{rid2}/evaluer', data={'action': 'phase1', 'impact': '3', 'probabilite': '4', 'niveau_maitrise': '3'})
with A.app.app_context():
    n_apres = M.Notification.query.filter_by(destinataire_id=ids['validateur'], type_notification='evaluation_a_valider').count()
verif('Pré-évaluation de l\'opérateur : le valideur désigné est prévenu', n_apres == n_avant + 1)
r, t = go('operateur', 'get', f'/operateur/risque/{rid2}/evaluer')
verif('L\'opérateur voit « transmise au valideur » au lieu du formulaire de validation',
      'valideur désigné' in r.data.decode('utf-8', 'ignore') and 'value="phase2"' not in r.data.decode('utf-8', 'ignore'), str(r.status_code))
go('operateur', 'post', f'/operateur/risque/{rid2}/evaluer', data={'action': 'phase2', 'impact_val': '3', 'probabilite_val': '4', 'niveau_maitrise_val': '3'})
verif('L\'opérateur ne peut plus valider lui-même', eval_(rid2).statut_validation == 'en_attente')
r, _ = go('validateur', 'get', '/ma-semaine')
verif('« Ma semaine » du valideur : l\'évaluation à valider', 'à valider' in r.data.decode('utf-8', 'ignore'))
go('validateur', 'post', f'/risque/{rid2}/evaluation-triphase', data={'submit_phase2': '1', 'statut_validation': 'valide', 'impact_val': '3',
   'probabilite_val': '3', 'niveau_maitrise_val': '3', 'commentaire_validation': 'Probabilité revue'})
x = eval_(rid2)
verif('Le valideur valide : part en confirmation de l\'administrateur (comme avant)', x.statut_validation == 'en_attente_admin' and x.validateur_id == ids['validateur'], x.statut_validation)
go('admin_a', 'post', f'/risque/{rid2}/evaluation-triphase', data={'submit_phase3': '1', 'impact_conf': '3', 'probabilite_conf': '3', 'niveau_maitrise_conf': '3'})
verif('L\'administrateur confirme', eval_(rid2).evaluateur_final_id == ids['admin_a'])

print('--- Valideur opérateur, réglé côté admin / gestionnaire')
with A.app.app_context():
    op2 = M.User(username='operateur_valideur', email='opv@recette.test', role='utilisateur', client_id=1, is_active=True,
                 is_operateur=True, permissions=socle.perms())
    op2.password_hash = generate_password_hash(socle.MDP); db.session.add(op2); db.session.flush()
    po2 = M.PermissionOperateur(user_id=op2.id, client_id=1, peut_evaluer_risques=True, peut_voir_evaluations=True)
    db.session.add(po2); db.session.flush(); op2.operateur_permissions_id = po2.id
    M.EvaluationRisque.query.filter_by(risque_id=rid2).delete(); db.session.commit(); ids['op_valideur'] = op2.id
from egalyx.parametres_risque import vider_cache
def valideur_id():
    with A.app.app_context():
        vider_cache(1); db.session.expire_all()
        from egalyx.parametres_risque import valideur_operateurs
        v = valideur_operateurs(1); return v.id if v else None
for role in ('admin_a', 'gestionnaire'):
    r, e = go(role, 'get', '/parametres/risques/valideur-operateurs')
    verif(f'La page du réglage s\'ouvre pour {role}', r.status_code == 200 and 'operateur_valideur' in r.data.decode('utf-8', 'ignore'), f'{r.status_code} {e}')
r, _ = go('admin_a', 'get', '/admin/operateurs')
verif('Le réglage figure sur la page admin des opérateurs', 'valideur_evaluations_operateurs_id' in r.data.decode('utf-8', 'ignore'), str(r.status_code))
go('lecteur', 'post', '/parametres/risques/valideur-operateurs', data={'valideur_evaluations_operateurs_id': str(ids['lecteur'])})
verif('Un lecteur ne peut pas désigner le valideur', valideur_id() == ids['validateur'])
go('operateur', 'post', '/parametres/risques/valideur-operateurs', data={'valideur_evaluations_operateurs_id': str(ids['operateur'])})
verif('Un opérateur ne peut pas se désigner valideur', valideur_id() == ids['validateur'])
go('gestionnaire', 'post', '/parametres/risques/valideur-operateurs', data={'valideur_evaluations_operateurs_id': str(ids['op_valideur']), 'suite': '/parametres/risques/valideur-operateurs'})
verif('Le gestionnaire désigne un opérateur comme valideur', valideur_id() == ids['op_valideur'])
go('operateur', 'post', f'/operateur/risque/{rid2}/evaluer', data={'action': 'phase1', 'impact': '4', 'probabilite': '4', 'niveau_maitrise': '2'})
r, e = go('op_valideur', 'get', '/operateur/evaluations-a-valider')
t = r.data.decode('utf-8', 'ignore')
verif('Le valideur opérateur voit l\'évaluation à valider dans son espace', r.status_code == 200 and 'operateur' in t and 'Ouvrir' in t, f'{r.status_code} {e}')
r, _ = go('operateur', 'get', '/operateur/evaluations-a-valider')
verif('Un autre opérateur n\'a pas cette page', r.status_code == 302)
r, _ = go('op_valideur', 'get', f'/operateur/risque/{rid2}/evaluer')
t = r.data.decode('utf-8', 'ignore')
verif('Le valideur a le formulaire de validation et le renvoi', 'value="phase2"' in t and 'value="a_revoir"' in t)
go('op_valideur', 'post', f'/operateur/risque/{rid2}/evaluer', data={'action': 'a_revoir', 'commentaire_validation': ''})
verif('Renvoi sans commentaire refusé', eval_(rid2).statut_validation == 'en_attente')
go('op_valideur', 'post', f'/operateur/risque/{rid2}/evaluer', data={'action': 'a_revoir', 'commentaire_validation': 'Probabilité trop haute'})
with A.app.app_context():
    nr = M.Notification.query.filter_by(destinataire_id=ids['operateur'], type_notification='evaluation_a_revoir').count()
verif('Renvoi à revoir : l\'opérateur est prévenu', eval_(rid2).statut_validation == 'a_revoir' and nr == 1)
go('operateur', 'post', f'/operateur/risque/{rid2}/evaluer', data={'action': 'a_revoir', 'commentaire_validation': 'x'})
verif('Un opérateur non valideur ne peut pas renvoyer à revoir', eval_(rid2).commentaire_validation == 'Probabilité trop haute')
go('operateur', 'post', f'/operateur/risque/{rid2}/evaluer', data={'action': 'phase1', 'impact': '4', 'probabilite': '3', 'niveau_maitrise': '2'})
verif('L\'opérateur corrige : retour « à valider »', eval_(rid2).statut_validation == 'en_attente')
go('operateur', 'post', f'/operateur/risque/{rid2}/evaluer', data={'action': 'phase2'})
verif('L\'opérateur ne valide toujours pas lui-même', eval_(rid2).statut_validation == 'en_attente')
go('op_valideur', 'post', f'/operateur/risque/{rid2}/evaluer', data={'action': 'phase2', 'impact_val': '0', 'probabilite_val': '0', 'niveau_maitrise_val': '0'})
x = eval_(rid2)
with A.app.app_context():
    nv = M.Notification.query.filter_by(destinataire_id=ids['operateur'], type_notification='evaluation_validee').count()
verif('Le valideur opérateur valide : en attente de l\'administrateur, opérateur prévenu',
      x.statut_validation == 'en_attente_admin' and x.validateur_id == ids['op_valideur'] and nv == 1, x.statut_validation)
go('admin_a', 'post', f'/risque/{rid2}/evaluation-triphase', data={'submit_phase3': '1', 'impact_conf': '4', 'probabilite_conf': '3', 'niveau_maitrise_conf': '2'})
verif('L\'administrateur confirme comme avant', eval_(rid2).evaluateur_final_id == ids['admin_a'])
go('admin_a', 'post', '/parametres/risques/valideur-operateurs', data={'valideur_evaluations_operateurs_id': ''})
verif('L\'admin retire le valideur : retour au fonctionnement standard', valideur_id() is None)

print('--- Un valideur par cartographie')
from socle import creer
with A.app.app_context():
    d0 = db.session.get(M.Cartographie, O['carto']).direction_id
    cb = creer(M.Cartographie, nom='Carto Finance', client_id=1, direction_id=d0, created_by=ids['gestionnaire'])
    rb = creer(M.Risque, reference='R-FIN', intitule='Risque finance', cartographie_id=cb.id, client_id=1, created_by=ids['gestionnaire'])
    creer(M.CampagneEvaluation, cartographie_id=cb.id, nom='Campagne finance', statut='en_cours', client_id=1)
    db.session.commit(); cbid, rbid = cb.id, rb.id
    M.EvaluationRisque.query.filter_by(risque_id=rid2).delete(); db.session.commit()
r, e = go('admin_a', 'get', '/parametres/risques/valideur-operateurs')
t = r.data.decode('utf-8', 'ignore')
verif('La page des valideurs liste chaque cartographie', f'name="carto_{cbid}"' in t and f'name="carto_{O["carto"]}"' in t, f'{r.status_code} {e}')
r, e = go('gestionnaire', 'get', f'/cartographie/{cbid}')
verif('Le réglage figure aussi sur la page de la cartographie', f'name="carto_{cbid}"' in r.data.decode('utf-8', 'ignore'), f'{r.status_code} {e}')
go('gestionnaire', 'post', '/parametres/risques/valideur-operateurs', data={f'carto_{cbid}': str(ids['op_valideur'])})
with A.app.app_context():
    verif('Valideur enregistré pour la cartographie Finance seulement',
          db.session.get(M.Cartographie, cbid).valideur_operateurs_id == ids['op_valideur'] and valideur_id() is None)
go('operateur', 'post', f'/operateur/risque/{rid2}/evaluer', data={'action': 'phase1', 'impact': '3', 'probabilite': '3', 'niveau_maitrise': '3'})
go('operateur', 'post', f'/operateur/risque/{rid2}/evaluer', data={'action': 'phase2'})
verif('Cartographie sans valideur : l\'opérateur valide lui-même (comme avant)', eval_(rid2).statut_validation == 'en_attente_admin')
with A.app.app_context():
    n0 = M.Notification.query.filter_by(destinataire_id=ids['op_valideur'], type_notification='evaluation_a_valider').count()
go('operateur', 'post', f'/operateur/risque/{rbid}/evaluer', data={'action': 'phase1', 'impact': '4', 'probabilite': '4', 'niveau_maitrise': '2'})
with A.app.app_context():
    n1 = M.Notification.query.filter_by(destinataire_id=ids['op_valideur'], type_notification='evaluation_a_valider').count()
verif('Cartographie Finance : son valideur est prévenu', n1 == n0 + 1)
go('operateur', 'post', f'/operateur/risque/{rbid}/evaluer', data={'action': 'phase2'})
verif('… et l\'opérateur ne valide pas lui-même', eval_(rbid).statut_validation == 'en_attente')
r, _ = go('op_valideur', 'get', '/operateur/evaluations-a-valider')
t = r.data.decode('utf-8', 'ignore')
verif('Le valideur Finance ne voit que les évaluations de sa cartographie', 'R-FIN' in t and 'RP-a' not in t, str(r.status_code))
go('op_valideur', 'post', f'/operateur/risque/{rbid}/evaluer', data={'action': 'phase2'})
verif('Le valideur Finance valide', eval_(rbid).statut_validation == 'en_attente_admin' and eval_(rbid).validateur_id == ids['op_valideur'])
go('op_valideur', 'post', f'/operateur/risque/{rid2}/evaluer', data={'action': 'a_revoir', 'commentaire_validation': 'x'})
verif('Il ne peut rien renvoyer sur une autre cartographie', eval_(rid2).statut_validation == 'en_attente_admin')
go('admin_a', 'post', '/parametres/risques/valideur-operateurs', data={'valideur_evaluations_operateurs_id': str(ids['validateur']), f'carto_{cbid}': str(ids['op_valideur'])})
with A.app.app_context():
    from egalyx.parametres_risque import valideur_operateurs as _vo
    vider_cache(1)
    verif('Valideur de l\'organisation par défaut, celui de la cartographie prioritaire',
          _vo(1, O['carto']).id == ids['validateur'] and _vo(1, cbid).id == ids['op_valideur'])
go('admin_a', 'post', '/parametres/risques/valideur-operateurs', data={'valideur_evaluations_operateurs_id': '', f'carto_{cbid}': ''})
with A.app.app_context():
    vider_cache(1)
    verif('Tout retirer : retour au fonctionnement standard partout', _vo(1, O['carto']) is None and _vo(1, cbid) is None)

print('--- Campagnes')
go('gestionnaire', 'post', f'/cartographie/{O["carto"]}/nouvelle-campagne', data={'nom': 'Campagne 2027'})
with A.app.app_context():
    c1 = db.session.get(M.CampagneEvaluation, c1id)
    c2 = M.CampagneEvaluation.query.filter_by(cartographie_id=O['carto'], statut='en_cours').first()
    verif('Nouvelle campagne : l\'ancienne est clôturée, la nouvelle est active', c1.statut == 'terminee' and c2 and c2.id != c1id)
    verif('L\'historique de 2026 est conservé', M.EvaluationRisque.query.filter_by(risque_id=rid, campagne_id=c1id).count() == 1)
r, _ = go('admin_b', 'get', f'/risque/{rid}/evaluation-triphase')
verif('L\'autre organisation n\'ouvre pas l\'évaluation', r.status_code in (302, 403, 404), str(r.status_code))
print(f'\n{sum(res)}/{len(res)} vérifications réussies')
sys.exit(0 if all(res) else 1)
