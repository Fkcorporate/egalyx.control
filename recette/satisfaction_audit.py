"""Recette : questionnaire de satisfaction des audités en fin de mission."""
import datetime as dt
import os
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


ROLES = ('admin_a', 'gestionnaire', 'validateur', 'lecteur', 'operateur', 'admin_b')
C = {r: socle.navigateur(A, ids[r]) for r in ROLES if r in ids}


def req(role, methode, url, **kw):
    r = appel(C[role], methode, url, **kw)
    with C[role].session_transaction() as s:
        fl = [m for _, m in (s.get('_flashes') or [])]
        s.pop('_flashes', None)
    return r, fl


with A.app.app_context():
    audit = socle.creer(M.Audit, reference='AUD-SAT', titre='Audit de la paie', type_audit='interne', client_id=1, statut='en_cours',
                        responsable_id=ids['gestionnaire'], equipe_audit_ids=str([ids['gestionnaire'], ids['validateur']]),
                        participants_ids=str([ids['lecteur'], ids['validateur']]), etat_rapport='provisoire',
                        date_limite_reponses=dt.date.today() - dt.timedelta(days=1))
    socle.creer(M.Constatation, reference='CST-SAT', description='Variables de paie non contrôlées', audit_id=audit.id, client_id=1,
                reponse_audite='OK', position_audite='accord')
    reco = socle.creer(M.Recommandation, reference='REC-SAT', description='Contrôle mensuel des variables', type_recommandation='corrective', urgence=3, impact_operationnel=3, audit_id=audit.id, client_id=1,
                       responsable_id=ids['operateur'] if 'operateur' in ids else ids['admin_a'])
    db.session.commit()
    AID = audit.id
URL = f'/audit-suivi/{AID}/satisfaction'

print('--- Avant le rapport définitif')
r, fl = req('lecteur', 'get', URL)
verif('questionnaire fermé avant le définitif', r.status_code == 302 and any('rapport définitif' in m for m in fl), r.status_code)

print('--- Rapport définitif : invitations')
r, fl = req('gestionnaire', 'post', f'/audit-suivi/{AID}/rapport/definitif')
with A.app.app_context():
    a = db.session.get(M.Audit, AID)
    verif('rapport définitif émis', a.etat_rapport == 'definitif', fl)
    inv = {n.destinataire_id for n in M.Notification.query.filter_by(type_notification='audit_satisfaction', entite_id=AID).all()}
    autre = ids['operateur'] if 'operateur' in ids else ids['admin_a']
    verif('audités invités (participant, responsable de recommandation)', {ids['lecteur'], autre} <= inv, inv)
    verif('équipe d\'audit non invitée (pas d\'auto-évaluation)', ids['validateur'] not in inv and ids['gestionnaire'] not in inv, inv)
    n = M.Notification.query.filter_by(type_notification='audit_satisfaction', destinataire_id=ids['lecteur']).first()
    verif('lien de la notification vers le questionnaire', n is not None and n.get_url() == URL, n and n.get_url())
    verif('rapport définitif journalisé (correction : l\'entrée se perdait)',
          M.JournalActiviteClient.query.filter_by(action='audit_rapport_definitif').count() == 1)

print('--- Réponses')
r, _ = req('validateur', 'get', URL)
verif('membre de l\'équipe : ne répond pas', r.status_code == 403, r.status_code)
r, _ = req('admin_b', 'get', URL)
verif('autre organisation : 404', r.status_code == 404, r.status_code)
r, _ = req('lecteur', 'get', URL)
verif('audité : questionnaire affiché', r.status_code == 200 and b'Votre avis' in r.data and b'Sans avis' in r.data, r.status_code)
r, _ = req('lecteur', 'get', f'/audit-suivi/{AID}/reponses')
verif('page « Constats et réponses » : bouton « Donner mon avis »', b'Donner mon avis' in r.data)
req('lecteur', 'post', URL, data={})
with A.app.app_context():
    verif('réponse vide refusée', M.SatisfactionAudit.query.filter_by(audit_id=AID).count() == 0)
req('lecteur', 'post', URL, data={'preparation': '5', 'professionnalisme': '4', 'organisation': '9', 'constats': '', 'valeur': '4',
                                  'commentaire': 'Équipe à l\'écoute ; calendrier un peu serré.'})
with A.app.app_context():
    rs = M.SatisfactionAudit.query.filter_by(audit_id=AID).all()
    verif('réponse enregistrée ; note hors échelle et « sans avis » ignorées', len(rs) == 1 and rs[0].notes == {'preparation': 5, 'professionnalisme': 4, 'valeur': 4}, rs and rs[0].notes)
    j = M.JournalActiviteClient.query.filter_by(action='audit_satisfaction').first()
    verif('journal sans les notes (anonymat)', j is not None and 'preparation' not in str(j.details), j and j.details)
req('lecteur', 'post', URL, data={'preparation': '3', 'valeur': '4'})
with A.app.app_context():
    rs = M.SatisfactionAudit.query.filter_by(audit_id=AID).all()
    verif('une seule réponse par personne, modifiable', len(rs) == 1 and rs[0].notes == {'preparation': 3, 'valeur': 4})

print('--- Anonymat')
r, _ = req('gestionnaire', 'get', f'/audit-suivi/{AID}/reponses')
verif('1 réponse : résultats masqués', b'Satisfaction des audit' in r.data and b'partir de 2 r' in r.data and b'Moyenne g' not in r.data)
autre_role = 'operateur' if 'operateur' in ids else 'admin_a'
r, fl = req(autre_role, 'post', URL, data={'preparation': '5', 'constats': '2', 'valeur': '2', 'commentaire': 'Constats mal expliqués.'})
r, _ = req('gestionnaire', 'get', f'/audit-suivi/{AID}/reponses')
html = r.data.decode()
verif('2 réponses : moyennes affichées (préparation 4,0 ; valeur 3,0)', '4.0 / 5' in html and '3.0 / 5' in html, fl)
verif('commentaires sans nom', 'Constats mal expliqués.' in html and 'calendrier un peu serré' not in html)  # 2e réponse du lecteur sans commentaire
with A.app.app_context():
    u_lect = db.session.get(M.User, ids['lecteur'])
verif('aucun nom d\'audité dans le bloc', u_lect.username not in html.split('Satisfaction des audit')[1].split('</table>')[0])

print('--- Synthèse de l\'année')
r, _ = req('gestionnaire', 'get', '/audit-suivi/satisfaction')
verif('synthèse : gestionnaire', r.status_code == 200 and b'AUD-SAT' in r.data and b'2 / 2' in r.data, r.status_code)
r, _ = req('lecteur', 'get', '/audit-suivi/satisfaction')
verif('synthèse refusée à un audité', r.status_code == 403, r.status_code)
r, _ = req('admin_b', 'get', '/audit-suivi/satisfaction')
verif('autre organisation : ne voit pas cette mission', b'AUD-SAT' not in r.data)
r, _ = req('admin_a', 'get', '/dashboard')
verif('menu Audit interne : « Satisfaction des audités »', b'/audit-suivi/satisfaction' in r.data)

print(f'\n{sum(res)}/{len(res)} vérifications réussies')
