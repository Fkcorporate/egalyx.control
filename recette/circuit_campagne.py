"""Circuit campagne de contrôle ↔ contrôle interne N2, de bout en bout, sur la vraie base et par les vraies pages."""
import sys
import socle, objets
from socle import Muet, appel
with Muet():
    A, ids = socle.preparer()
    O = objets.peupler_objets(A, ids)['a']
import models as M
from models import db
cid = O['campagne']; pid = O['planification']
op, val, lec = (socle.navigateur(A, ids[r]) for r in ('operateur', 'validateur', 'lecteur'))
resultats = []
def verif(nom, cond, detail=''):
    resultats.append((nom, bool(cond), detail)); print(('OK   ' if cond else 'ÉCHEC'), nom, detail)
def etat():
    with A.app.app_context():
        c = db.session.get(M.CampagneControle, cid); p = db.session.get(M.PlanificationControle, pid)
        nc = M.NonConformiteC2N.query.filter_by(client_id=c.client_id).count()
        an = M.AnomalieDetectee.query.filter_by(campagne_id=cid).all() if hasattr(M.AnomalieDetectee, 'campagne_id') else []
        ex = db.session.get(M.ExecutionControle, c.execution_c2n_id) if c.execution_c2n_id else None
        return dict(statut=c.statut, pl=p.statut, nc=nc, anomalies=len(an), soumis_par=c.soumis_par_id, date_soumission=c.date_soumission,
                    valide_par=c.valide_par_id, raison_rejet=c.raison_rejet, historique=len(c.historique_actions or []),
                    ex_volume=getattr(ex, 'volume_controle', None) if ex else None, ex_id=c.execution_c2n_id,
                    nb=(c.nb_dossiers_controles, c.nb_conformes, c.nb_anomalies))

r = appel(op, 'post', f'/operateur/campagne/{cid}/demarrer'); socle.cause(A)
verif('L\'opérateur démarre la campagne', etat()['statut'] == 'en_cours', str(r.status_code))
form = dict(nb_dossiers_controles='10', nb_conformes='7', nb_anomalies='3', motifs_anomalie='Pièce manquante\nSignature absente\nMontant erroné',
            commentaire_general='RAS', conclusion='Conforme à 70 %', actions_correctives='Former', action='save')
r = appel(op, 'post', f'/operateur/campagne/{cid}/executer', data=form); e = socle.cause(A)
s = etat(); verif('Saisie enregistrée (volumes)', s['nb'] == (10, 7, 3), f"{s['nb']} {e}")
verif('Anomalies créées depuis les motifs', s['anomalies'] == 3, f"{s['anomalies']} anomalies")
r = appel(op, 'post', f'/operateur/campagne/{cid}/executer', data=form | {'action': 'save'}); socle.cause(A)
verif('Ré-enregistrer ne duplique pas les anomalies', etat()['anomalies'] == 3, f"{etat()['anomalies']}")
r = appel(op, 'post', f'/operateur/campagne/{cid}/executer', data=form | {'action': 'submit'}); e = socle.cause(A)
s = etat()
verif('Soumission : campagne en attente de validation', s['statut'] == 'en_attente_validation', s['statut'] + ' ' + e)
verif('Soumission : planification N2 « soumis »', s['pl'] == 'soumis', s['pl'])
verif('Soumission : aucune non-conformité créée', not s['nc'], str(s['nc']))
verif('Soumission : auteur et date enregistrés en base', s['soumis_par'] == ids['operateur'] and s['date_soumission'] is not None, str((s['soumis_par'], s['date_soumission'])))
verif('Soumission : exécution N2 créée avec les volumes', s['ex_id'] is not None, f"exécution {s['ex_id']} volume {s['ex_volume']}")
with A.app.app_context():
    n = M.Notification.query.filter_by(destinataire_id=ids['validateur']).count()
verif('Le validateur est notifié', n >= 1, f'{n} notification(s)')
r = appel(op, 'post', f'/operateur/campagne/{cid}/valider', data={'action': 'valider', 'commentaire': 'je me valide'}); socle.cause(A)
verif('L\'opérateur ne peut pas valider sa propre campagne', etat()['statut'] == 'en_attente_validation', etat()['statut'])
r = appel(lec, 'post', f'/operateur/campagne/{cid}/valider', data={'action': 'valider'}); socle.cause(A)
verif('Un simple lecteur ne peut pas valider', etat()['statut'] == 'en_attente_validation', etat()['statut'])
r = appel(val, 'get', f'/controle/campagne/{cid}'); e = socle.cause(A)
txt = r.data.decode('utf-8', 'ignore') if r.status_code == 200 else ''
verif('Le validateur voit l\'encadré de décision', 'Valider la campagne' in txt, f'{r.status_code} {e}')
r = appel(val, 'post', f'/operateur/campagne/{cid}/rejeter', data={'raison': 'court'}); socle.cause(A)
verif('Rejet sans motif suffisant refusé', etat()['statut'] == 'en_attente_validation', etat()['statut'])
r = appel(val, 'post', f'/operateur/campagne/{cid}/rejeter', data={'raison': 'Volumes à justifier par les pièces'}); e = socle.cause(A)
s = etat(); verif('Rejet : campagne rejetée, motif gardé en base', s['statut'] == 'rejete' and s['raison_rejet'], f"{s['statut']} / {s['raison_rejet']} {e}")
verif('Rejet : aucune non-conformité', not s['nc'], str(s['nc']))
r = appel(op, 'post', f'/operateur/campagne/{cid}/executer', data=form | {'action': 'submit'}); e = socle.cause(A)
verif('Correction puis nouvelle soumission', etat()['statut'] == 'en_attente_validation', etat()['statut'] + ' ' + e)
r = appel(val, 'post', f'/operateur/campagne/{cid}/valider', data={'action': 'valider', 'commentaire': 'OK'}); e = socle.cause(A)
s = etat()
verif('Validation : campagne terminée', s['statut'] == 'termine', s['statut'] + ' ' + e)
verif('Validation : planification N2 validée', s['pl'] == 'valide', s['pl'])
verif('Validation : 1 non-conformité par anomalie', s['nc'] == 3, str(s['nc']))
verif('Historique enregistré en base', s['historique'] >= 4, f"{s['historique']} entrées")
r = appel(op, 'post', f'/operateur/campagne/{cid}/rouvrir', data={'raison': 'Je veux rouvrir'}); socle.cause(A)
verif('L\'opérateur ne peut pas rouvrir une campagne validée', etat()['statut'] == 'termine', etat()['statut'])
print(f"\n{sum(1 for x in resultats if x[1])}/{len(resultats)} vérifications réussies")
sys.exit(0 if all(x[1] for x in resultats) else 1)
