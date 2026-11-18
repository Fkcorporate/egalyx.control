"""Recette : progression des plans d'action (elle tient après actualisation) et suites d'un plan terminé.

Chaque action passe par l'adresse et le format qu'utilise réellement la page (mêmes appels que son JavaScript),
puis la page est rechargée et la base relue.
"""
import datetime as dt
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
ges = socle.navigateur(A, ids['gestionnaire'])
lec = socle.navigateur(A, ids['lecteur'])

with A.app.app_context():
    cid = db.session.get(M.User, ids['admin_a']).client_id
    au = creer(M.Audit, titre='Audit trésorerie', reference='AUD-TRS', client_id=cid, created_by=ids['admin_a'], statut='en_cours')
    db.session.flush()
    co = creer(M.Constatation, reference='CST-TRS-1', description='Rapprochements tardifs', type_constatation='non_conformite', audit_id=au.id, client_id=cid, statut='en_action', created_by=ids['admin_a'])
    db.session.flush()
    re_ = creer(M.Recommandation, reference='REC-TRS-1', description='Rapprocher chaque jour', audit_id=au.id, constatation_id=co.id,
                client_id=cid, statut='a_traiter', taux_avancement=0, responsable_id=ids['admin_a'], urgence=3, impact_operationnel=3)
    db.session.flush()
    pa = creer(M.PlanAction, reference='PA-TRS-1', nom='Rapprochement quotidien', audit_id=au.id, recommandation_id=re_.id,
               client_id=cid, created_by=ids['admin_a'], responsable_id=ids['admin_a'], statut='en_attente', pourcentage_realisation=0)
    db.session.flush()
    s1 = creer(M.SousAction, description='Outil de rapprochement', plan_action_id=pa.id, client_id=cid, statut='a_faire', pourcentage_realisation=0)
    s2 = creer(M.SousAction, description='Procédure écrite', plan_action_id=pa.id, client_id=cid, statut='a_faire', pourcentage_realisation=0)
    ca = creer(M.Cartographie, nom='Carto Trésorerie', client_id=cid, created_by=ids['admin_a'])
    db.session.flush()
    rk = creer(M.Risque, reference='R-TRS', intitule='Erreur de trésorerie', cartographie_id=ca.id, client_id=cid, created_by=ids['admin_a'])
    db.session.flush()
    pr = creer(M.PlanAction, reference='PA-RSQ-1', nom='Double validation', risque_id=rk.id, client_id=cid,
               created_by=ids['admin_a'], statut='en_attente', pourcentage_realisation=0)
    db.session.flush()
    r1 = creer(M.SousAction, description='Paramétrer', plan_action_id=pr.id, client_id=cid, statut='a_faire', pourcentage_realisation=0)
    r2 = creer(M.SousAction, description='Former', plan_action_id=pr.id, client_id=cid, statut='a_faire', pourcentage_realisation=0)
    pi = creer(M.PlanAction, reference='PA-IND-1', nom='Plan sans sous-action', client_id=cid, created_by=ids['admin_a'],
               statut='en_attente', pourcentage_realisation=0)
    vieux = creer(M.PlanAction, reference='PA-ANCIEN', nom='Ancien plan clos', client_id=cid, created_by=ids['admin_a'],
                  statut='termine', pourcentage_realisation=0)
    db.session.commit()
    I = dict(RK=rk.id, PA=pa.id, S1=s1.id, S2=s2.id, RE=re_.id, CO=co.id, PR=pr.id, R1=r1.id, R2=r2.id, PI=pi.id, VX=vieux.id, AU=au.id)


def lire(modele, i):
    with A.app.app_context():
        db.session.expire_all()
        o = db.session.get(modele, i)
        return {c.name: getattr(o, c.key if hasattr(o, c.key) else c.name, None) for c in o.__table__.columns} if o else None


def lire_sa(i):
    with A.app.app_context():
        o = db.session.get(M.SousAction, i)
        return o.pourcentage_realisation, o.statut


def ajax(c, url, **form):
    return c.post(url, data=form, headers={'X-Requested-With': 'fetch'})


print("--- Plan d'audit : progression des sous-actions (page d'audit)")
r = ajax(adm, f"/sous-action/{I['S1']}/maj-progression", progression=50)
verif('progression 50 % enregistrée', r.status_code == 200 and lire_sa(I['S1']) == (50, 'en_cours'), f'{r.status_code} {lire_sa(I["S1"])}')
h = adm.get(f"/plan-action/{I['PA']}").data.decode()
verif('après actualisation : la sous-action affiche 50 %', re.search(r'value="50"\s+data-id="%d"' % I['S1'], h) is not None)
p = lire(M.PlanAction, I['PA'])
verif('plan : 25 % (moyenne des sous-actions), en cours', p['pourcentage_realisation'] == 25 and p['statut'] == 'en_cours', f"{p['pourcentage_realisation']} {p['statut']}")
rc = lire(M.Recommandation, I['RE'])
verif('recommandation : avancement 25 %, en cours', rc['taux_avancement'] == 25 and rc['statut'] == 'en_cours', f"{rc['taux_avancement']} {rc['statut']}")
r = ajax(adm, f"/sous-action/{I['S1']}/modifier-statut", statut='termine')
verif('statut « terminé » choisi dans la liste -> 100 %', r.status_code in (200, 302) and lire_sa(I['S1']) == (100, 'termine'), str(lire_sa(I['S1'])))
r = ajax(adm, f"/sous-action/{I['S2']}/maj-progression", progression=100)
p = lire(M.PlanAction, I['PA'])
verif('dernière sous-action à 100 % -> plan terminé (100 %, date de fin)', p['statut'] == 'termine' and p['pourcentage_realisation'] == 100 and p['date_fin_reelle'] is not None, f"{p['statut']} {p['pourcentage_realisation']}")

print('--- Suites : recommandation et constatation')
rc = lire(M.Recommandation, I['RE'])
verif('recommandation NON clôturée d\'office', rc['statut'] != 'termine', rc['statut'])
verif('… clôture DEMANDÉE (à valider par un gestionnaire)', rc['demande_cloture_le'] is not None and rc['taux_avancement'] == 100, str(rc['demande_cloture_le']))
with A.app.app_context():
    suivis = M.SuiviRecommandation.query.filter_by(source='audit', recommandation_id=I['RE'], action='demande_cloture').all()
    notes = M.Notification.query.filter_by(entite_type='recommandation', entite_id=I['RE'], destinataire_id=ids['gestionnaire']).all()
verif('… tracée dans l\'historique de la recommandation', len(suivis) == 1 and 'PA-TRS-1' in (suivis[0].commentaire or ''))
verif('… gestionnaire prévenu', len(notes) >= 1, str(len(notes)))
h = adm.get(f"/recommandations/audit/{I['RE']}").data.decode()
verif('registre : la recommandation apparaît « Clôture à valider »', 'Clôture à valider' in h)
ajax(adm, f"/sous-action/{I['S2']}/maj-progression", progression=75)
p = lire(M.PlanAction, I['PA']); rc = lire(M.Recommandation, I['RE'])
verif('sous-action redescendue à 75 % -> plan rouvert', p['statut'] == 'en_cours' and p['pourcentage_realisation'] == 88 and p['date_fin_reelle'] is None, f"{p['statut']} {p['pourcentage_realisation']}")
verif('… demande de clôture retirée', rc['demande_cloture_le'] is None and rc['statut'] != 'termine')
ajax(adm, f"/sous-action/{I['S2']}/maj-progression", progression=100)
r = ges.post(f"/recommandations/audit/{I['RE']}/cloture", data={'decision': 'valider', 'commentaire': 'Preuves vues'})
rc = lire(M.Recommandation, I['RE']); co = lire(M.Constatation, I['CO'])
verif('gestionnaire valide la clôture -> recommandation clôturée', rc['statut'] == 'termine', f"{r.status_code} {rc['statut']}")
verif('… sa constatation passe « close »', co['statut'] == 'clos', co['statut'])
with A.app.app_context():
    reco = db.session.get(M.Recommandation, I['RE']); reco.statut = 'en_cours'; db.session.commit()
verif('recommandation rouverte -> constatation de nouveau « en action »', lire(M.Constatation, I['CO'])['statut'] == 'en_action')

print('--- Plan de risque (page du risque)')
for sid in (I['R1'], I['R2']):
    r = adm.post(f"/sous-action-risque/{sid}/changer-progression", json={'progression': 100})
p = lire(M.PlanAction, I['PR'])
verif('toutes les sous-actions à 100 % -> plan terminé (avant : restait « en attente »)', p['statut'] == 'termine' and p['pourcentage_realisation'] == 100, f"{p['statut']} {p['pourcentage_realisation']}")
r = adm.post(f"/plan-action-risque/{I['PR']}/set-progression-fixe", json={'progression': 50})
h = adm.get(f"/plan-action-risque/{I['PR']}").data.decode()
p = lire(M.PlanAction, I['PR'])
verif('progression du plan réglée à 50 % : tient après actualisation', p['pourcentage_realisation'] == 50 and 'id="progressionGlobale">50%' in h, f"{p['pourcentage_realisation']}")
verif('… plan rouvert (en cours)', p['statut'] == 'en_cours', p['statut'])
r = adm.post(f"/sous-action-risque/{I['R1']}/changer-progression", json={'progression': 0})
p = lire(M.PlanAction, I['PR'])
verif('une sous-action à 0 % -> plan à 25 % (moyenne), tient après actualisation', p['pourcentage_realisation'] == 25, str(p['pourcentage_realisation']))

print('--- Plan sans sous-action')
r = adm.post(f"/plan-action-independant/{I['PI']}/set-progression-fixe", json={'progression': 75})
adm.get(f"/plan-action-independant/{I['PI']}")
p = lire(M.PlanAction, I['PI'])
verif('75 % : tient après actualisation', p['pourcentage_realisation'] == 75 and p['statut'] == 'en_cours', f"{r.status_code} {p['pourcentage_realisation']} {p['statut']}")
r = adm.post(f"/plan-action-independant/{I['PI']}/set-progression-fixe", json={'progression': 100})
p = lire(M.PlanAction, I['PI'])
verif('100 % -> terminé', p['statut'] == 'termine' and p['date_fin_reelle'] is not None, p['statut'])

print('--- Contrôle interne N2 : plans d\'action N2 -> recommandation N2')
with A.app.app_context():
    d1 = creer(M.DispositifMaitrise, reference='DM-N2', nom='Contrôle caisse', risque_id=I['RK'], client_id=cid, statut='actif',
               efficacite_reelle=3, frequence='Mensuel', created_by=ids['admin_a'])
    db.session.flush()
    ref = creer(M.ReferentielControle, client_id=cid, code_controle='CTRL-N2', nom='Revue caisse', dispositifs_ids=[d1.id],
                risques_ids=[I['RK']], frequence='mensuel')
    db.session.flush()
    pl = creer(M.PlanificationControle, reference='PL-N2', annee=2026, date_prevue=dt.date.today(), referentiel_id=ref.id,
               client_id=cid, controleur_id=ids['gestionnaire'], validateur_requis_id=ids['validateur'], statut='en_cours',
               created_by=ids['admin_a'])
    db.session.flush()
    rn = creer(M.RecommandationC2N, planification_id=pl.id, titre='Compter la caisse chaque soir', client_id=cid,
               statut='proposee', progression=0, responsable_id=ids['admin_a'])
    db.session.flush()
    n1 = creer(M.PlanActionC2N, reference='PAN2-1', action_corrective='Fiche de comptage', recommandation_id=rn.id,
               date_echeance=dt.date.today() + dt.timedelta(days=30), client_id=cid, statut='a_faire', taux_avancement=0)
    n2 = creer(M.PlanActionC2N, reference='PAN2-2', action_corrective='Former les caissiers', recommandation_id=rn.id,
               date_echeance=dt.date.today() + dt.timedelta(days=30), client_id=cid, statut='a_faire', taux_avancement=0)
    db.session.commit()
    RN, N1, N2 = rn.id, n1.id, n2.id
r = adm.post(f'/c2n/plan-action/{N1}/terminer')
rn = lire(M.RecommandationC2N, RN)
verif('un plan N2 terminé (bouton « Terminer ») -> recommandation N2 à 50 %, en cours', rn['progression'] == 50 and rn['statut'] == 'en_cours' and not rn['demande_cloture_le'], f"{r.status_code} {rn['progression']} {rn['statut']}")
r = adm.post(f'/c2n/plan-action/{N2}/terminer')
rn = lire(M.RecommandationC2N, RN)
verif('tous les plans N2 terminés -> clôture DEMANDÉE (pas « réalisée » d\'office)', rn['demande_cloture_le'] is not None and rn['statut'] != 'realisee' and rn['progression'] == 100, f"{rn['statut']} {rn['progression']}")

print('--- Garde-fous')
with A.app.app_context():
    v = db.session.get(M.PlanAction, I['VX']); v.description = 'Texte corrigé'; db.session.commit()
verif('ancien plan « terminé » : une simple modification de texte ne le rouvre pas', lire(M.PlanAction, I['VX'])['statut'] == 'termine')
avant = lire_sa(I['S1'])
with A.app.app_context():
    from socle import perms
    o = M.User(username='observateur', email='observateur@recette.test', role='utilisateur', client_id=cid, is_active=True)
    o.password_hash = 'x'
    o.permissions = perms('can_view_audit', 'can_view_action_plans', 'can_view_audit_program')
    db.session.add(o); db.session.commit(); OBS = o.id
obs = socle.navigateur(A, OBS)
for nom, c in (('lecteur (sans accès au module)', lec), ('observateur (lecture seule)', obs)):
    r = ajax(c, f"/sous-action/{I['S1']}/modifier-statut", statut='a_faire')
    verif(f'{nom} : changement de statut refusé', r.status_code in (302, 403) and lire_sa(I['S1']) == avant, str(r.status_code))
    r = ajax(c, f"/sous-action/{I['S1']}/supprimer")
    verif(f'{nom} : suppression refusée', r.status_code in (302, 403) and lire_sa(I['S1']) == avant, str(r.status_code))
verif('changement de statut / suppression : droit de modifier le plan exigé',
      all(getattr(A.app.view_functions[e], '_egalyx_droit_plan', False) for e in ('modifier_statut_sous_action', 'supprimer_sous_action')))
autre = socle.navigateur(A, ids['admin_b'])
r = ajax(autre, f"/sous-action/{I['S1']}/maj-progression", progression=0)
verif('autre organisation : refusé', r.status_code in (403, 404) and lire_sa(I['S1']) == avant, str(r.status_code))

print(f'\n{sum(res)}/{len(res)} vérifications réussies')
