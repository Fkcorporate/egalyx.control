"""Dispositifs de maîtrise et plans d'action des risques : droits (permissions réelles), vérifications qui pèsent
sur l'efficacité et le niveau de maîtrise suggéré, échéances selon la fréquence, « Ma semaine », plan sans risque.
Compléments incidents : coûts dans les exports, e-mails des alertes."""
import sys
import time
from datetime import date, datetime, timedelta

import socle
import objets
from socle import Muet, appel, creer
from werkzeug.security import generate_password_hash

with Muet():
    A, ids = socle.preparer()
    O = objets.peupler_objets(A, ids)
import models as M
from models import db

res = []


def verif(nom, cond, detail=''):
    res.append(bool(cond))
    print('OK   ' if cond else 'ÉCHEC', nom, detail)


def go(role, m, url, **kw):
    r = appel(socle.navigateur(A, ids[role]), m, url, **kw)
    return r, r.data.decode('utf-8', 'ignore')


def obj(modele, i):
    with A.app.app_context():
        db.session.expire_all()
        return db.session.get(modele, i)


with A.app.app_context():
    u = M.User(username='resp_dmr', email='resp.dmr@egalyx-recette.fr', role='utilisateur', client_id=1, is_active=True,
               permissions={k: False for k in socle.perms()})
    u.password_hash = generate_password_hash(socle.MDP); db.session.add(u); db.session.flush(); ids['resp_dmr'] = u.id
    rid = O['a']['risque']
    d = M.DispositifMaitrise(reference='DMR-R1', nom='Double signature des virements', client_id=1, risque_id=rid,
                             type_dispositif='Préventif', nature='Manuel', frequence='Annuel', statut='actif',
                             efficacite_reelle=4, couverture=4, created_by=ids['gestionnaire'], responsable_id=ids['resp_dmr'])
    p = M.PlanAction(reference='PA-R1', nom='Renforcer les contrôles', client_id=1, risque_id=rid, statut='en_cours',
                     created_by=ids['gestionnaire'], responsable_id=ids['resp_dmr'])
    p_sans = M.PlanAction(reference='PA-AUD', nom='Plan issu d\'un audit', client_id=1, statut='en_cours',
                          created_by=ids['gestionnaire'])
    camp = M.CampagneEvaluation.query.filter_by(client_id=1).first()
    e = M.EvaluationRisque(risque_id=rid, client_id=1, campagne_id=camp.id if camp else None, niveau_maitrise_pre=4,
                           date_pre_evaluation=datetime.utcnow())
    db.session.add_all([d, p, p_sans, e]); db.session.commit()
    did, pid, psid, eid = d.id, p.id, p_sans.id, e.id

print('--- Droits (avant : permissions inexistantes, seul le créateur pouvait modifier)')
r, _ = go('admin_a', 'post', f'/dispositif/{did}/changer-statut', data={'statut': 'inactif', 'justification': 'Test'})
verif('L\'admin (non créateur) change le statut d\'un dispositif', obj(M.DispositifMaitrise, did).statut == 'inactif', str(r.status_code))
go('admin_a', 'post', f'/dispositif/{did}/changer-statut', data={'statut': 'actif', 'justification': 'Retour'})
r, t = go('admin_a', 'get', f'/plan-action-risque/{pid}/modifier')
verif('L\'admin (non créateur) ouvre la modification d\'un plan', r.status_code == 200, f'{r.status_code} {socle.cause(A)}')
for role in ('lecteur', 'operateur'):
    r1, _ = go(role, 'get', f'/dispositif/{did}')
    r2, _ = go(role, 'get', f'/plan-action-risque/{pid}')
    r3, _ = go(role, 'get', f'/api/dispositif/{did}/statistiques')
    verif(f'{role} sans droit : ni dispositif, ni plan, ni statistiques',
          r1.status_code in (302, 403) and r2.status_code in (302, 403) and r3.status_code in (302, 403),
          f'{r1.status_code} {r2.status_code} {r3.status_code}')
r, _ = go('admin_b', 'get', f'/dispositif/{did}')
verif('Autre organisation : introuvable', r.status_code in (302, 403, 404), str(r.status_code))
r, _ = go('resp_dmr', 'get', f'/dispositif/{did}')
verif('Le responsable du dispositif (sans permission) le consulte', r.status_code == 200, f'{r.status_code} {socle.cause(A)}')
go('resp_dmr', 'post', f'/dispositif/{did}/changer-statut', data={'statut': 'inactif', 'justification': 'x'})
verif('… mais n\'en change pas le statut', obj(M.DispositifMaitrise, did).statut == 'actif')
r, _ = go('resp_dmr', 'get', f'/plan-action-risque/{pid}')
verif('Le responsable du plan le consulte', r.status_code == 200, f'{r.status_code} {socle.cause(A)}')
r, _ = go('admin_a', 'get', '/controle/programmes')
verif('Programmes de contrôle : ouverts avec les droits du contrôle N2 (permission fantôme avant)', r.status_code == 200,
      f'{r.status_code} {socle.cause(A)}')

print('--- Vérifications')
r, _ = go('resp_dmr', 'post', f'/dispositif/{did}/verification/ajouter', data={
    'date_verification': date.today().isoformat(), 'type_verification': 'Test', 'resultat': 'Non conforme',
    'commentaire': 'Virement de 12 M signé une seule fois'})
x = obj(M.DispositifMaitrise, did)
verif('Le responsable enregistre une vérification', x.date_derniere_verification == date.today(), f'{r.status_code} {socle.cause(A)}')
verif('« Non conforme » baisse l\'efficacité (4 → 2)', x.efficacite_reelle == 2, str(x.efficacite_reelle))
verif('Prochaine vérification dans 30 jours après un échec', x.prochaine_verification == date.today() + timedelta(days=30),
      str(x.prochaine_verification))
with A.app.app_context():
    h = M.DispositifHistoriqueEfficacite.query.filter_by(dispositif_id=did, cause='verification').count()
verif('Baisse inscrite à l\'historique d\'efficacité', h == 1)
ev = obj(M.EvaluationRisque, eid)
verif('Niveau de maîtrise suggéré recalculé (2,8) : écart signalé avec la maîtrise saisie (4)',
      ev.niveau_maitrise_dmr == 2.8 and ev.ecart_maitrise and ev.ecart_maitrise > 0.5 and ev.get_coherence_statut() != 'success',
      f'{ev.niveau_maitrise_dmr} {ev.ecart_maitrise}')
r, _ = go('gestionnaire', 'post', f'/dispositif/{did}/verification/ajouter', data={
    'date_verification': date.today().isoformat(), 'type_verification': 'Test', 'resultat': 'Conforme', 'commentaire': 'OK'})
x = obj(M.DispositifMaitrise, did)
verif('« Conforme » sur un contrôle annuel : prochaine vérification dans un an',
      x.prochaine_verification == date.today() + timedelta(days=365) and x.efficacite_reelle == 2, str(x.prochaine_verification))
go('lecteur', 'post', f'/dispositif/{did}/verification/ajouter', data={
    'date_verification': date.today().isoformat(), 'type_verification': 'Test', 'resultat': 'Non conforme'})
verif('Un lecteur n\'enregistre pas de vérification', obj(M.DispositifMaitrise, did).efficacite_reelle == 2)

print('--- Ma semaine')
with A.app.app_context():
    x = db.session.get(M.DispositifMaitrise, did); x.prochaine_verification = date.today() + timedelta(days=3); db.session.commit()
r, t = go('resp_dmr', 'get', '/ma-semaine')
verif('Le responsable voit le dispositif à vérifier', 'Dispositif à vérifier' in t and 'Double signature' in t, str(r.status_code))

print('--- Plans')
r, t = go('gestionnaire', 'get', f'/plan-action-risque/{psid}')
verif('La page d\'un plan sans risque s\'affiche (plantait)', r.status_code == 200 and 'Aucun risque rattaché' in t,
      f'{r.status_code} {socle.cause(A)}')
r, _ = go('resp_dmr', 'post', f'/plan-action-risque/{pid}/changer-statut-rapide', json={'statut': 'en_cours'})
verif('Le responsable du plan met à jour son statut', r.status_code in (200, 302), str(r.status_code))
go('lecteur', 'post', f'/plan-action-risque/{pid}/changer-statut-rapide', json={'statut': 'annule'})
verif('Un lecteur ne change pas le statut', obj(M.PlanAction, pid).statut != 'annule')
r, t = go('admin_a', 'get', f'/risque/{rid}')
verif('Fiche risque : plus de mention « ISO 31010 »', 'ISO 31010' not in t, str(r.status_code))

r, t = go('gestionnaire', 'get', '/dispositifs/benchmark')
verif('Comparatif des dispositifs : s\'ouvre (méthode manquante avant)', r.status_code == 200 and 'Préventif' in t,
      f'{r.status_code} {socle.cause(A)}')
r, _ = go('lecteur', 'get', '/dispositifs/benchmark')
verif('… pas pour un lecteur sans droit', r.status_code in (302, 403), str(r.status_code))
with A.app.app_context():
    pl = db.session.get(M.PlanAction, pid)
    pl.date_debut, pl.date_fin_prevue = date.today(), date.today() + timedelta(days=20)
    db.session.add(M.SousAction(plan_action_id=pid, reference='PA-R1-1', description='Rédiger la procédure',
                                statut='a_faire', client_id=1, date_debut=date.today(),
                                date_fin_prevue=date.today() + timedelta(days=10)))
    db.session.commit()
r, _ = go('gestionnaire', 'get', f'/plan-action/{pid}/gantt')
verif('Gantt d\'un plan aux dates réelles', r.status_code == 200, f'{r.status_code} {socle.cause(A)}')

print('--- Incidents : exports et e-mails')
with A.app.app_context():
    i = M.Incident(reference='INC-X1', titre='Panne', client_id=1, statut='ouvert', gravite='elevee',
                   created_by=ids['gestionnaire'], responsable_resolution_id=ids['gestionnaire'], sla_heures=24,
                   cout_estime=2500000, impact_financier_reel=1800000, temps_arret=150,
                   created_at=datetime.utcnow() - timedelta(days=3), date_detection=datetime.utcnow() - timedelta(days=3))
    db.session.add(i); db.session.commit()
r, t = go('gestionnaire', 'get', '/incidents/export/csv')
verif('Export CSV : coût estimé, coût réel, temps d\'arrêt', r.status_code == 200 and 'Coût estimé' in t and '2500000' in t
      and '1800000' in t and '150' in t, f'{r.status_code} {socle.cause(A)}')
r, _ = go('gestionnaire', 'get', '/incidents/export/excel')
verif('Export Excel produit', r.status_code == 200 and r.data[:2] == b'PK', f'{r.status_code} {socle.cause(A)}')
from egalyx import courriel
envoyes = []
courriel.est_configure = lambda: True
courriel.envoyer = lambda dest, sujet, texte, **k: envoyes.append((dest[0], sujet)) or True
with A.app.app_context():
    from egalyx.incidents import verifier_delais
    verifier_delais()
time.sleep(1)
with A.app.app_context():
    mail_g = db.session.get(M.User, ids['gestionnaire']).email
verif('Délai dépassé : e-mail envoyé aux personnes concernées', any(d == mail_g and 'Délai dépassé' in s for d, s in envoyes),
      str(envoyes[:3]))

print(f'\n{sum(res)}/{len(res)} vérifications réussies')
sys.exit(0 if all(res) else 1)
