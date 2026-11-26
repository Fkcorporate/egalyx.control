"""Recette : univers d'audit, qualité de la fonction d'audit (normes IIA 2024), charte d'audit."""
import datetime as dt
import os
import re
os.environ['EGALYX_COLLECTE_AUTO'] = '0'
import socle
from socle import Muet, appel
with Muet():
    A, ids = socle.preparer()
import models as M
from models import db

res = []


def verif(nom, cond, detail=''):
    res.append(bool(cond)); print('OK   ' if cond else 'ÉCHEC', nom, detail)


C = {r: socle.navigateur(A, ids[r]) for r in ('admin_a', 'gestionnaire', 'validateur', 'lecteur', 'admin_b')}


def req(role, methode, url, **kw):
    r = appel(C[role], methode, url, **kw)
    with C[role].session_transaction() as s:
        fl = [m for _, m in (s.get('_flashes') or [])]
        s.pop('_flashes', None)
    return r, fl


AUJ = dt.date.today()
with A.app.app_context():
    d = socle.creer(M.Direction, nom='Direction financière', **({'client_id': 1} if 'client_id' in M.Direction.__table__.columns else {}))
    p1 = socle.creer(M.ProcessusActivite, nom='Octroi de crédit', client_id=1, direction_id=d.id)
    p2 = socle.creer(M.ProcessusActivite, nom='Paie', client_id=1)
    db.session.commit()
    P1, P2, D = p1.id, p2.id, d.id
    # un audit du processus « Octroi de crédit », rapport définitif il y a 14 mois
    a = socle.creer(M.Audit, reference='AUD-UNI', titre='Audit crédit', type_audit='interne', client_id=1, statut='termine',
                    processus_id=P1, etat_rapport='definitif', date_fin_reelle=AUJ - dt.timedelta(days=440),
                    rapport_definitif_le=dt.datetime.combine(AUJ - dt.timedelta(days=425), dt.time(10)),
                    responsable_id=ids['gestionnaire'], equipe_audit_ids=str([ids['gestionnaire']]))
    db.session.commit()
    AID = a.id

print('--- Droits')
for role, attendu in (('gestionnaire', 200), ('admin_a', 200), ('lecteur', 403)):
    for page in ('univers', 'qualite', 'charte'):
        r, _ = req(role, 'get', f'/fonction-audit/{page}')
        verif(f'{role} : /{page} → {attendu}', r.status_code == attendu, r.status_code)
r, _ = req('admin_a', 'get', '/dashboard')
verif('menu Audit interne : univers, qualité, charte', all(x in r.data for x in (b'/fonction-audit/univers', b'/fonction-audit/qualite', b'/fonction-audit/charte')))

print('--- Univers d\'audit')
req('gestionnaire', 'post', '/fonction-audit/univers', data={'action': 'importer', 'source': ['processus', 'direction']})
with A.app.app_context():
    es = M.EntiteAuditable.query.filter_by(client_id=1).all()
    noms = {e.nom for e in es}
verif('import : processus et direction ajoutés', {'Octroi de crédit', 'Paie', 'Direction financière'} <= noms, noms)
req('gestionnaire', 'post', '/fonction-audit/univers', data={'action': 'importer', 'source': ['processus', 'direction']})
with A.app.app_context():
    verif('import relancé : pas de doublon', M.EntiteAuditable.query.filter_by(client_id=1).count() == len(es))
    e_credit = M.EntiteAuditable.query.filter_by(client_id=1, processus_id=P1).first().id
    e_paie = M.EntiteAuditable.query.filter_by(client_id=1, processus_id=P2).first().id
r, fl = req('gestionnaire', 'post', '/fonction-audit/univers', data={'action': 'ajouter', 'nom': 'Système core banking', 'type_entite': 'systeme',
                                                                    'niveau_risque': 'eleve', 'dernier_audit_manuel': (AUJ + dt.timedelta(days=3)).isoformat()})
with A.app.app_context():
    verif('date du dernier audit dans le futur : refusée', M.EntiteAuditable.query.filter_by(nom='Système core banking').count() == 0, fl)
req('gestionnaire', 'post', '/fonction-audit/univers', data={'action': 'ajouter', 'nom': 'Système core banking', 'type_entite': 'systeme',
                                                            'niveau_risque': 'eleve', 'dernier_audit_manuel': (AUJ - dt.timedelta(days=800)).isoformat()})
r, _ = req('gestionnaire', 'get', '/fonction-audit/univers')
h = r.data.decode()
verif('audit rattaché par le processus : dernier audit et référence', 'AUD-UNI' in h)
# risque moyen = cycle 2 ans : rapport il y a 14 mois -> à prévoir dans les 12 mois
verif('cycle selon le risque (moyen 2 ans) : « À prévoir dans les 12 mois »', 'À prévoir dans les 12 mois' in h)
verif('jamais audité : signalé', 'Jamais audité' in h)
verif('risque élevé (1 an), audité il y a 800 j : en retard', re.search(r'À auditer \(échéance dépassée de \d+ j\)', h) is not None)
req('gestionnaire', 'post', '/fonction-audit/univers', data={'action': 'modifier', 'entite_id': str(e_credit), 'nom': 'Octroi de crédit',
                                                            'type_entite': 'processus', 'niveau_risque': 'eleve', 'cycle_annees': ''})
r, _ = req('gestionnaire', 'get', '/fonction-audit/univers')
verif('risque passé à élevé : le crédit devient « à auditer »', r.data.decode().count('À auditer (échéance dépassée') == 2)
req('gestionnaire', 'post', '/fonction-audit/univers', data={'action': 'modifier', 'entite_id': str(e_credit), 'nom': 'Octroi de crédit',
                                                            'type_entite': 'processus', 'niveau_risque': 'eleve', 'cycle_annees': '15'})
with A.app.app_context():
    verif('cycle hors 1-10 ans : refusé', db.session.get(M.EntiteAuditable, e_credit).cycle_annees is None)
req('gestionnaire', 'post', '/fonction-audit/univers', data={'action': 'rattacher', 'entite_id': str(e_paie), 'audit_id': str(AID)})
with A.app.app_context():
    verif('rattacher un audit à une entité', db.session.get(M.Audit, AID).entite_auditable_id == e_paie)
req('gestionnaire', 'post', '/fonction-audit/univers', data={'action': 'retirer', 'entite_id': str(e_paie)})
with A.app.app_context():
    verif('retirer une entité (conservée)', db.session.get(M.EntiteAuditable, e_paie).actif is False)
r, fl = req('admin_b', 'post', '/fonction-audit/univers', data={'action': 'modifier', 'entite_id': str(e_credit), 'nom': 'pirate',
                                                               'niveau_risque': 'faible'})
with A.app.app_context():
    verif('autre organisation : ne modifie pas l\'entité', db.session.get(M.EntiteAuditable, e_credit).nom == 'Octroi de crédit', r.status_code)
r, _ = req('admin_b', 'get', '/fonction-audit/univers')
verif('autre organisation : ne voit pas l\'univers', b'Octroi de cr' not in r.data)

print('--- Charte d\'audit')
req('gestionnaire', 'post', '/fonction-audit/charte', data={'action': 'nouvelle'})
with A.app.app_context():
    ch = M.CharteAudit.query.filter_by(client_id=1).first()
    verif('brouillon créé depuis le modèle (nom de l\'organisation)', ch is not None and ch.statut == 'brouillon' and 'Normes internationales' in ch.texte
          and '{organisation}' not in ch.texte)
    texte = ch.texte
req('gestionnaire', 'post', '/fonction-audit/charte', data={'action': 'approuver', 'texte': texte, 'approuvee_le': (AUJ + dt.timedelta(days=1)).isoformat(),
                                                           'approuvee_par': "Conseil d'administration"})
with A.app.app_context():
    verif('approbation datée dans le futur : refusée', M.CharteAudit.query.filter_by(client_id=1).first().statut == 'brouillon')
req('gestionnaire', 'post', '/fonction-audit/charte', data={'action': 'approuver', 'texte': texte, 'approuvee_le': (AUJ - dt.timedelta(days=400)).isoformat(),
                                                           'approuvee_par': "Conseil d'administration"})
with A.app.app_context():
    ch = M.CharteAudit.query.filter_by(client_id=1).first()
    verif('charte v1 en vigueur, revue prévue un an après', ch.statut == 'approuvee' and ch.revue_prevue == (AUJ - dt.timedelta(days=400)).replace(year=(AUJ - dt.timedelta(days=400)).year + 1))
r, _ = req('gestionnaire', 'get', '/fonction-audit/charte')
verif('revue dépassée signalée', b'(d\xc3\xa9pass\xc3\xa9e)' in r.data)
req('gestionnaire', 'post', '/fonction-audit/charte', data={'action': 'nouvelle'})
req('gestionnaire', 'post', '/fonction-audit/charte', data={'action': 'approuver', 'texte': texte + '\n9. Révision 2026.', 'approuvee_le': AUJ.isoformat(),
                                                           'approuvee_par': "Comité d'audit"})
with A.app.app_context():
    vs = {c.version: c.statut for c in M.CharteAudit.query.filter_by(client_id=1).all()}
verif('v2 en vigueur, v1 remplacée et conservée', vs == {1: 'remplacee', 2: 'approuvee'}, vs)
with A.app.app_context():
    verif('approbations journalisées', M.JournalActiviteClient.query.filter_by(action='charte_audit_approuvee').count() == 2)

print('--- Qualité de la fonction')
import html as _html
r, _ = req('gestionnaire', 'get', '/fonction-audit/qualite')
h = _html.unescape(r.data.decode())
verif('alerte : aucune évaluation externe', 'Aucune évaluation externe' in h)
verif('observations par principe (charte v2, indépendance, univers…)', 'Charte en vigueur : version 2' in h and 'Univers d' in h and "Déclarations d'indépendance" in h)
r, _ = req('gestionnaire', 'post', '/fonction-audit/qualite/evaluation/nouvelle', data={'type_evaluation': 'interne', 'annee': str(AUJ.year)})
with A.app.app_context():
    ev = M.EvaluationQualiteAudit.query.filter_by(client_id=1, type_evaluation='interne').first()
verif('évaluation interne créée', ev is not None and ev.statut == 'brouillon')
EV = ev.id
r, _ = req('gestionnaire', 'get', f'/fonction-audit/qualite/evaluation/{EV}')
verif('grille : 15 principes, intitulés officiels', r.status_code == 200 and r.data.decode().count('_niveau"') >= 15 * 4
      and "Faire preuve d&#39;objectivité" in r.data.decode() and 'Autorité conférée par le Conseil' in r.data.decode())
partiel = {f'p{n}_niveau': 'conforme' for n in range(1, 15)}
req('gestionnaire', 'post', f'/fonction-audit/qualite/evaluation/{EV}', data={**partiel, 'conclusion': 'partiel', 'action': 'valider'})
with A.app.app_context():
    verif('validation refusée tant qu\'un principe manque (15)', db.session.get(M.EvaluationQualiteAudit, EV).statut == 'brouillon')
complet = {**partiel, 'p15_niveau': 'partiel', 'p15_action': 'Relancer les responsables des recommandations échues', 'conclusion': 'partiel',
           'date_evaluation': AUJ.isoformat(), 'synthese': 'Fonction globalement conforme ; suivi des recommandations à renforcer.'}
req('gestionnaire', 'post', f'/fonction-audit/qualite/evaluation/{EV}', data={**complet, 'action': 'valider'})
with A.app.app_context():
    ev = db.session.get(M.EvaluationQualiteAudit, EV)
    verif('évaluation interne validée', ev.statut == 'valide' and ev.reponses['15']['niveau'] == 'partiel' and 'Relancer' in ev.reponses['15']['action'])
req('gestionnaire', 'post', f'/fonction-audit/qualite/evaluation/{EV}', data={**complet, 'conclusion': 'conforme', 'action': 'enregistrer'})
with A.app.app_context():
    verif('évaluation validée : ne se modifie plus', db.session.get(M.EvaluationQualiteAudit, EV).conclusion == 'partiel')
req('gestionnaire', 'post', '/fonction-audit/qualite/evaluation/nouvelle', data={'type_evaluation': 'externe', 'annee': str(AUJ.year - 6)})
with A.app.app_context():
    ex = M.EvaluationQualiteAudit.query.filter_by(client_id=1, type_evaluation='externe').first()
complet_ext = {**complet, 'date_evaluation': (AUJ - dt.timedelta(days=6 * 365)).isoformat()}
req('gestionnaire', 'post', f'/fonction-audit/qualite/evaluation/{ex.id}', data={**complet_ext, 'action': 'valider'})
with A.app.app_context():
    verif('externe sans évaluateur : validation refusée', db.session.get(M.EvaluationQualiteAudit, ex.id).statut == 'brouillon')
req('gestionnaire', 'post', f'/fonction-audit/qualite/evaluation/{ex.id}', data={**complet_ext, 'evaluateur': 'Cabinet Exemple', 'action': 'valider'})
r, _ = req('gestionnaire', 'get', '/fonction-audit/qualite')
h = r.data.decode()
verif('externe de plus de 5 ans : « à renouveler »', 'Évaluation externe à renouveler' in h)
verif('évaluation interne de l\'année : plus d\'alerte', "Pas encore d'évaluation interne" not in h)
r, _ = req('admin_b', 'get', f'/fonction-audit/qualite/evaluation/{EV}')
verif('autre organisation : évaluation introuvable', r.status_code == 404, r.status_code)

print(f'\n{sum(res)}/{len(res)} vérifications réussies')
