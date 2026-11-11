"""Qualité : droits, validation du plan, non-conformités et actions, revues de direction, « Ma semaine »."""
import sys
import datetime as dt
import socle, objets
from socle import Muet, appel
with Muet():
    A, ids = socle.preparer()
    O = objets.peupler_objets(A, ids)
import models as M
from models import db
from werkzeug.security import generate_password_hash
res = []


def verif(nom, cond, detail=''):
    res.append(bool(cond)); print('OK   ' if cond else 'ÉCHEC', nom, detail)


def utilisateur(nom, *perms):
    with A.app.app_context():
        u = M.User(username=nom, email=f'{nom}@recette.test', role='utilisateur', client_id=1, is_active=True,
                   permissions=socle.perms(*perms))
        u.password_hash = generate_password_hash(socle.MDP); db.session.add(u); db.session.commit(); ids[nom] = u.id


utilisateur('q_gest', 'can_manage_quality_plans')
utilisateur('q_auditeur', 'can_manage_quality_audits')
utilisateur('q_lecteur', 'can_view_quality')
utilisateur('audit_seul', 'can_manage_audit')


def go(role, m, url, **kw):
    r = appel(socle.navigateur(A, ids[role]), m, url, **kw)
    return r, r.data.decode('utf-8', 'ignore'), socle.cause(A)


with A.app.app_context():
    p = M.PlanQualiteFonction(reference='PQ-ACH', titre='Plan qualité achats', client_id=1, created_by=ids['q_gest'],
                              date_debut=dt.date(2026, 1, 1), date_fin=dt.date(2026, 12, 31), annee_exercice=2026,
                              periode_revue='semestrielle', statut='brouillon')
    db.session.add(p); db.session.flush()
    au = M.AuditQualite(reference='AQ-1', plan_qualite_id=p.id, titre='Audit fournisseurs', client_id=1,
                        created_by=ids['q_auditeur'], auditeur_principal_id=ids['lecteur'], statut='planifie',
                        date_prevue=dt.date.today() + dt.timedelta(days=5))
    db.session.add(au); db.session.commit()
    pid, aid = p.id, au.id


def plan():
    with A.app.app_context():
        x = db.session.get(M.PlanQualiteFonction, pid); db.session.expunge(x); return x


print('--- Droits')
for role, attendu in (('q_gest', 200), ('q_auditeur', 200), ('q_lecteur', 200), ('lecteur', 302), ('operateur', 302),
                      ('audit_seul', 302)):
    r, _, e = go(role, 'get', f'/qualite/plan/{pid}')
    verif(f'Fiche du plan pour {role} : {attendu}', r.status_code == attendu, f'{r.status_code} {e}')
r, _, _ = go('q_lecteur', 'get', '/qualite/plan/nouveau')
verif('« Voir la qualité » ne crée pas de plan', r.status_code == 302)
r, _, _ = go('q_gest', 'get', f'/qualite/audit/{aid}/modifier')
verif('« Plans qualité » ne modifie pas un audit qualité', r.status_code == 302)
r, _, e = go('q_auditeur', 'get', f'/qualite/audit/{aid}/modifier')
verif('« Audits qualité » modifie un audit qualité', r.status_code == 200, f'{r.status_code} {e}')
for url in (f'/qualite/audit/{aid}', f'/qualite/audit/{aid}/repondre'):
    r, _, e = go('lecteur', 'get', url)
    verif(f'L\'auditeur principal (sans droit qualité) : {url.rsplit("/", 1)[-1]}', r.status_code == 200, f'{r.status_code} {e}')
r, _, _ = go('operateur', 'get', f'/qualite/audit/{aid}/modifier')
verif('Un opérateur ne modifie plus un audit qualité (avant : ouvert)', r.status_code == 302)
r, t, e = go('q_gest', 'get', f'/qualite/plan/{pid}/rapport-complet')
verif('Rapport complet du plan (avant : erreur)', r.status_code == 200, f'{r.status_code} {e}')

print('--- Validation du plan')
FORM = {'reference': 'PQ-ACH', 'titre': 'Plan qualité achats', 'type_fonction': 'direction', 'pole_id': '0', 'direction_id': '0',
        'service_id': '0', 'date_debut': '2026-01-01', 'date_fin': '2026-12-31', 'annee_exercice': '2026',
        'frequence_controles': 'mensuel', 'niveau_maturite': '3', 'responsable_conformite_id': str(ids['q_gest']),
        'responsable_revue_id': '0', 'objectifs_qualite-0-objectif': 'Évaluer 100 % des fournisseurs critiques',
        'indicateurs_cles-0-nom': 'Fournisseurs évalués', 'indicateurs_cles-0-cible': '100', 'statut': 'actif', 'est_valide': 'y'}
r, t, e = go('q_gest', 'post', f'/qualite/plan/{pid}/modifier', data=FORM)
x = plan()
verif('Enregistrer avec « Plan validé » coché ne plante plus', r.status_code == 302 and not e, f'{r.status_code} {e}')
verif('… et ne valide pas le plan, qui ne devient pas « actif »', not x.est_valide and x.statut == 'brouillon', f'{x.est_valide} {x.statut}')
verif('Le reste est bien enregistré (responsable, objectifs)', x.responsable_conformite_id == ids['q_gest'] and x.objectifs_qualite)
go('q_gest', 'post', f'/qualite-suivi/plan/{pid}/valideur', data={'valideur_id': str(ids['validateur'])})
verif('Valideur désigné', plan().valideur_id == ids['validateur'])
with A.app.app_context():
    n0 = M.Notification.query.filter_by(destinataire_id=ids['validateur'], type_notification='qualite_a_valider').count()
go('q_gest', 'post', f'/qualite-suivi/plan/{pid}/soumettre')
with A.app.app_context():
    n1 = M.Notification.query.filter_by(destinataire_id=ids['validateur'], type_notification='qualite_a_valider').count()
verif('Soumis : le valideur est prévenu', plan().soumis_le is not None and n1 == n0 + 1)
r, t, _ = go('validateur', 'get', '/ma-semaine')
verif('« Ma semaine » du valideur : plan qualité à valider', 'Plan qualité à valider' in t)
r, t, _ = go('validateur', 'get', f'/qualite/plan/{pid}')
verif('Le valideur (sans droit qualité) ouvre la fiche et voit « Valider »', r.status_code == 200 and 'Valider le plan' in t, str(r.status_code))
go('q_gest', 'post', f'/qualite-suivi/plan/{pid}/valider')
verif('Un autre que le valideur ne valide pas', not plan().est_valide)
go('validateur', 'post', f'/qualite-suivi/plan/{pid}/valider')
x = plan()
verif('Validé par le valideur : actif, prochaine revue fixée', x.est_valide and x.statut == 'actif' and x.valide_par_id == ids['validateur']
      and x.date_prochaine_revue is not None, f'{x.statut} {x.date_prochaine_revue}')
go('q_gest', 'post', f'/qualite/plan/{pid}/modifier', data=dict(FORM, titre='Plan qualité achats 2026'))
x = plan()
verif('Modifier un plan validé retire la validation', x.titre == 'Plan qualité achats 2026' and not x.est_valide, f'{x.titre} {x.est_valide}')
go('q_gest', 'post', f'/qualite-suivi/plan/{pid}/soumettre'); go('validateur', 'post', f'/qualite-suivi/plan/{pid}/valider')
verif('Revalidé', plan().est_valide)

print('--- Non-conformités et actions')
r, _, e = go('q_gest', 'post', f'/qualite/plan/{pid}/non-conformite/nouveau',
             data={'titre': 'Fournisseur non évalué', 'description': 'Le fournisseur X n\'a pas été évalué', 'gravite': 'majeure',
                   'responsable_id': str(ids['lecteur']), 'action_corrective': 'Évaluer le fournisseur X'})
with A.app.app_context():
    nc = M.NonConformite.query.filter_by(plan_qualite_id=pid).first(); ncid = nc.id if nc else None
verif('Non-conformité créée', ncid is not None, f'{r.status_code} {e}')
r, _, _ = go('lecteur', 'get', f'/qualite/non-conformite/{ncid}/modifier')
verif('Son responsable (sans droit qualité) peut la mettre à jour', r.status_code == 200, str(r.status_code))
r, t, _ = go('lecteur', 'get', '/ma-semaine')
verif('« Ma semaine » du responsable : la non-conformité', 'Fournisseur non évalué' in t)
NC = {'titre': 'Fournisseur non évalué', 'description': 'x', 'gravite': 'majeure', 'responsable_id': str(ids['lecteur'])}
go('q_gest', 'post', f'/qualite/non-conformite/{ncid}/modifier', data=dict(NC, statut='close'))
with A.app.app_context():
    verif('Clôture refusée sans vérification d\'efficacité', db.session.get(M.NonConformite, ncid).statut != 'close')
go('lecteur', 'post', f'/qualite-suivi/non-conformite/{ncid}/action', data={'intitule': 'Évaluer le fournisseur X', 'echeance': '2026-12-15'})
with A.app.app_context():
    a = M.ActionAmeliorationQualite.query.filter_by(non_conformite_id=ncid).first()
    verif('Le responsable crée l\'action : rattachée, NC en traitement', a is not None and a.responsable_id == ids['lecteur']
          and db.session.get(M.NonConformite, ncid).statut == 'en_traitement')
    acid = a.id
r, t, _ = go('lecteur', 'get', '/ma-semaine')
verif('« Ma semaine » : l\'action qualité confiée', 'Évaluer le fournisseur X' in t)
r, _, _ = go('lecteur', 'get', f'/qualite/action/{acid}/modifier')
verif('Le responsable ouvre son action', r.status_code == 200, str(r.status_code))
with A.app.app_context():
    a = db.session.get(M.ActionAmeliorationQualite, acid); a.statut = 'terminee'; a.pourcentage_realisation = 100; db.session.commit()
r, t, _ = go('q_gest', 'get', f'/qualite/plan/{pid}')
verif('La fiche demande de vérifier l\'efficacité quand les actions sont terminées', 'efficacité puis clôturez' in t)
go('q_gest', 'post', f'/qualite/non-conformite/{ncid}/modifier',
   data=dict(NC, statut='close', verification_efficacite='Évaluation faite, contrôle à 3 mois OK', efficace='true'))
with A.app.app_context():
    n = db.session.get(M.NonConformite, ncid)
    verif('Clôture acceptée après vérification « efficace », vérificateur tracé', n.statut == 'close' and n.verifie_par_id == ids['q_gest']
          and n.date_cloture is not None, f'{n.statut} {n.verifie_par_id}')

print('--- Revue de direction')
with A.app.test_request_context():
    r_ = M.ReunionQualite(plan_qualite_id=pid, titre='Revue S1', type_reunion='revue_direction', statut='planifiee',
                          date_reunion=dt.datetime(2026, 6, 30, 10), client_id=1)
    db.session.add(r_); db.session.commit(); rid = r_.id
    r_ = db.session.get(M.ReunionQualite, rid); r_.statut = 'tenue'; db.session.commit()
x = plan()
verif('Revue tenue : dernière revue mise à jour, suivante 6 mois après (semestrielle)',
      x.date_derniere_revue == dt.date(2026, 6, 30) and x.date_prochaine_revue == dt.date(2026, 12, 30), f'{x.date_derniere_revue} {x.date_prochaine_revue}')

print('--- Migration des droits existants')
with A.app.app_context():
    from egalyx.ia import ecrire_reglage
    ecrire_reglage('migration_permissions_qualite', False)
    from egalyx.qualite import _migrer_permissions
    _migrer_permissions(A.app)
    db.session.expire_all()
    u = db.session.get(M.User, ids['audit_seul'])
    verif('Qui gérait la qualité via « Gérer les audits » garde l\'accès (Gérer la qualité)', u.has_permission('can_manage_quality'))

print('--- Étanchéité')
for url in (f'/qualite/plan/{pid}', f'/qualite/audit/{aid}', f'/qualite/non-conformite/{ncid}'):
    r, _, _ = go('admin_b', 'get', url)
    verif(f'Autre organisation : {url} fermé', r.status_code in (302, 403, 404), str(r.status_code))
go('admin_b', 'post', f'/qualite-suivi/plan/{pid}/renvoyer', data={'motif': 'x'})
verif('Autre organisation : aucune action sur le plan', plan().motif_renvoi is None)
print(f'\n{sum(res)}/{len(res)} vérifications réussies')
sys.exit(0 if all(res) else 1)
