"""PCA : droits, circuit de validation, exercices et résultats, activations, documents, liens, « Ma semaine »."""
import io
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


utilisateur('pca_gest', 'can_manage_bcp')                 # gère les PCA, SANS « Gérer les audits »
utilisateur('pca_lecteur', 'can_view_bcp')
utilisateur('pca_testeur', 'can_test_bcp')


def go(role, m, url, **kw):
    r = appel(socle.navigateur(A, ids[role]), m, url, **kw)
    return r, r.data.decode('utf-8', 'ignore'), socle.cause(A)


def plan():
    with A.app.app_context():
        p = M.PlanContinuiteActivite.query.filter_by(client_id=1).order_by(M.PlanContinuiteActivite.id.desc()).first()
        if p is not None:
            db.session.expunge(p)
        return p


print('--- Droits')
for role, attendu in (('pca_gest', 200), ('pca_lecteur', 200), ('pca_testeur', 200), ('lecteur', 302), ('operateur', 302)):
    r, _, e = go(role, 'get', '/pca/plans')
    verif(f'Liste des PCA pour {role} : {attendu}', r.status_code == attendu, f'{r.status_code} {e}')
for url in ('/pca/tableau-bord', '/pca/stress-test'):
    r, _, _ = go('lecteur', 'get', url)
    verif(f'{url} fermé sans droit PCA', r.status_code == 302, str(r.status_code))
r, _, _ = go('pca_lecteur', 'get', '/pca/plan/nouveau')
verif('« Voir » ne permet pas de créer un plan', r.status_code == 302)

print('--- Création (gestionnaire PCA sans droit audit)')
FORM = dict(reference='PCA-SIEGE', titre='PCA Siège', description='Continuité du siège', type_organisation='direction',
            pole_id='0', direction_id='0', service_id='0', processus_critiques='Paie\nTrésorerie',
            responsable_id=str(ids['pca_gest']), redacteur_id=str(ids['pca_gest']), valideur_id=str(ids['validateur']),
            delai_arret_max='4 h', perte_donnees_max='30 min', strategies='Site miroir', statut='valide', niveau_maturite='2',
            procedures_urgence='Appeler la cellule de crise')
r, t, e = go('pca_gest', 'post', '/pca/plan/nouveau', data=FORM)
p = plan()
verif('Le gestionnaire PCA crée un plan (avant : refusé faute de « Gérer les audits »)', p is not None, f'{r.status_code} {e}')
verif('La référence saisie est conservée', p and p.reference == 'PCA-SIEGE', p.reference if p else '')
verif('« Validé » choisi dans le formulaire : le plan reste en rédaction', p and p.statut == 'en_redaction', p.statut if p else '')
verif('RTO et RPO convertis en heures', p and p.rto_heures == 4 and p.rpo_heures == 0.5, f'{p.rto_heures} / {p.rpo_heures}')
pid = p.id
r, t, e = go('pca_lecteur', 'get', f'/pca/plan/{pid}')
verif('« Voir » ouvre la fiche (avant : il fallait « Gérer »)', r.status_code == 200 and 'id="pca-suivi"' in t, f'{r.status_code} {e}')
verif('… sans les boutons de gestion', 'Soumettre à validation' not in t and 'Déclencher le PCA' not in t)

print('--- Le valideur ne modifie pas le plan')
r, _, _ = go('validateur', 'post', f'/pca/plan/{pid}/modifier', data=dict(FORM, titre='MODIFIÉ PAR LE VALIDEUR'))
verif('Le valideur désigné ne peut pas modifier le plan', plan().titre == 'PCA Siège', plan().titre)

print('--- Circuit de validation')
with A.app.app_context():
    x = db.session.get(M.PlanContinuiteActivite, pid); x.procedures_urgence = None; db.session.commit()
go('pca_gest', 'post', f'/pca-suivi/{pid}/soumettre')
verif('Soumission refusée si les procédures d\'urgence manquent', plan().statut == 'en_redaction')
with A.app.app_context():
    x = db.session.get(M.PlanContinuiteActivite, pid); x.procedures_urgence = 'Appeler la cellule'; db.session.commit()
    n0 = M.Notification.query.filter_by(destinataire_id=ids['validateur'], type_notification='pca_a_valider').count()
go('pca_gest', 'post', f'/pca-suivi/{pid}/soumettre')
with A.app.app_context():
    n1 = M.Notification.query.filter_by(destinataire_id=ids['validateur'], type_notification='pca_a_valider').count()
verif('Soumis : en relecture, le valideur est prévenu', plan().statut == 'en_relecture' and n1 == n0 + 1)
r, t, _ = go('validateur', 'get', '/ma-semaine')
verif('« Ma semaine » du valideur : PCA à valider', 'PCA à valider' in t)
r, t, _ = go('validateur', 'get', f'/pca/plan/{pid}')
verif('Le valideur (sans droit PCA) ouvre la fiche et voit « Valider »', r.status_code == 200 and 'Valider le plan' in t, str(r.status_code))
r, _, _ = go('lecteur', 'get', f'/pca/plan/{pid}')
verif('Un autre utilisateur sans droit PCA ne l\'ouvre pas', r.status_code == 302, str(r.status_code))
go('pca_gest', 'post', f'/pca-suivi/{pid}/valider')
verif('Un autre que le valideur désigné ne peut pas valider', plan().statut == 'en_relecture')
go('validateur', 'post', f'/pca-suivi/{pid}/renvoyer', data={'motif': ''})
verif('Renvoi sans motif refusé', plan().statut == 'en_relecture')
go('validateur', 'post', f'/pca-suivi/{pid}/renvoyer', data={'motif': 'Ajouter le site de secours'})
verif('Renvoi motivé : retour en rédaction', plan().statut == 'en_redaction' and plan().motif_renvoi == 'Ajouter le site de secours')
go('pca_gest', 'post', f'/pca-suivi/{pid}/soumettre')
go('validateur', 'post', f'/pca-suivi/{pid}/valider')
p = plan()
verif('Le valideur valide : validé, valable un an', p.statut == 'valide' and p.valide_par_id == ids['validateur']
      and p.date_validite and p.date_validite > dt.date.today() + dt.timedelta(days=360), f'{p.statut} {p.date_validite}')
go('pca_gest', 'post', f'/pca/plan/{pid}/modifier', data=dict(FORM, titre='PCA Siège v2', statut='valide'))
p = plan()
verif('Modifier un plan validé le repasse en rédaction', p.titre == 'PCA Siège v2' and p.statut == 'en_redaction', f'{p.titre} {p.statut}')
go('pca_gest', 'post', f'/pca-suivi/{pid}/soumettre'); go('validateur', 'post', f'/pca-suivi/{pid}/valider')
verif('Revalidation : version suivante', plan().version == '1.1', plan().version)

print('--- Exercices')
r, _, e = go('pca_testeur', 'post', f'/pca/plan/{pid}/exercice/nouveau',
             data={'reference': 'X', 'nom': 'Bascule salle', 'type_exercice': 'technique', 'date_exercice': '2026-10-01', 'duree': '3'})
with A.app.app_context():
    ex = M.ExercicePCA.query.filter_by(plan_id=pid).first(); exid = ex.id if ex else None
verif('« Tester » permet de planifier un exercice', exid is not None, f'{r.status_code} {e}')
r, _, _ = go('pca_testeur', 'get', f'/pca/exercice/{exid}/modifier')
verif('« Tester » ouvre la modification d\'exercice (avant : « Gérer les audits »)', r.status_code == 200, str(r.status_code))
r, _, _ = go('pca_testeur', 'post', f'/pca/plan/{pid}/modifier', data=dict(FORM, titre='X'))
verif('« Tester » ne modifie pas le plan', plan().titre == 'PCA Siège v2')
r, t, e = go('pca_testeur', 'get', f'/pca-suivi/exercice/{exid}/resultat')
verif('Page de résultat d\'exercice', r.status_code == 200 and 'Durée réelle de reprise' in t, f'{r.status_code} {e}')
go('pca_testeur', 'post', f'/pca-suivi/exercice/{exid}/resultat',
   data={'statut': 'realise', 'date_exercice': '2026-10-01', 'note': '72', 'duree_reprise': '3 h',
         'points_forts': 'Bascule rapide', 'axes_amelioration': 'Mettre à jour l\'annuaire de crise\nTester la VPN', 'creer_actions': '1'})
p = plan()
with A.app.app_context():
    ex = db.session.get(M.ExercicePCA, exid)
    nb_actions = M.ActionPCA.query.filter_by(plan_id=pid).count()
    verif('Résultat enregistré (réalisé, 3 h, 72/100)', ex.statut == 'realise' and ex.duree_reprise_heures == 3 and ex.note == 72)
verif('Dernier test = date de l\'exercice, prochain = un an après', p.date_dernier_test == dt.date(2026, 10, 1)
      and p.date_prochain_test == dt.date(2027, 10, 1), f'{p.date_dernier_test} {p.date_prochain_test}')
verif('« Tester » seul ne crée pas d\'actions', nb_actions == 0, str(nb_actions))
go('pca_gest', 'post', f'/pca-suivi/exercice/{exid}/resultat',
   data={'statut': 'realise', 'date_exercice': '2026-10-01', 'note': '72', 'duree_reprise': '3 h',
         'axes_amelioration': 'Mettre à jour l\'annuaire de crise\nTester la VPN', 'creer_actions': '1'})
with A.app.app_context():
    acts = M.ActionPCA.query.filter_by(plan_id=pid).all()
    verif('Le gestionnaire : une action par axe d\'amélioration', len(acts) == 2, str(len(acts)))
    a0 = acts[0]; a0.responsable_id = ids['lecteur']; db.session.commit(); aid = a0.id
go('pca_gest', 'post', f'/pca-suivi/exercice/{exid}/resultat',
   data={'statut': 'realise', 'date_exercice': '2026-10-01', 'duree_reprise': '3 h', 'axes_amelioration': 'Mettre à jour l\'annuaire de crise\nTester la VPN', 'creer_actions': '1'})
with A.app.app_context():
    verif('Ré-enregistrer ne recrée pas les mêmes actions', M.ActionPCA.query.filter_by(plan_id=pid).count() == 2)
r, t, _ = go('pca_gest', 'get', f'/pca/plan/{pid}')
verif('La fiche compare la reprise au RTO', 'RTO respecté' in t)
r, _, _ = go('lecteur', 'get', f'/pca/action/{aid}/modifier')
verif('Le responsable d\'une action (sans droit PCA) peut la mettre à jour', r.status_code == 200, str(r.status_code))
r, t, _ = go('lecteur', 'get', '/ma-semaine')
verif('« Ma semaine » : l\'action de PCA confiée', 'Action de PCA' in t)

print('--- Activation réelle')
with A.app.app_context():
    dmr = socle.creer(M.DispositifMaitrise, risque_id=O['a']['risque'], client_id=1, created_by=ids['gestionnaire'])
    inc = socle.creer(M.Incident, reference='INC-PCA', titre='Panne électrique', client_id=1, risque_id=O['a']['risque'],
                      dispositif_id=dmr.id, created_by=ids['gestionnaire'])
    db.session.commit(); iid = inc.id
go('pca_lecteur', 'post', f'/pca-suivi/{pid}/activer', data={'motif': 'x'})
with A.app.app_context():
    verif('« Voir » ne déclenche pas le PCA', M.ActivationPCA.query.count() == 0)
go('pca_gest', 'post', f'/pca-suivi/{pid}/activer', data={'motif': 'Coupure de courant', 'incident_id': str(iid)})
with A.app.app_context():
    a = M.ActivationPCA.query.filter_by(plan_id=pid).first()
    verif('PCA déclenché, lié à l\'incident', a and a.incident_id == iid and a.fin is None)
    a.debut = dt.datetime.utcnow() - dt.timedelta(hours=6); db.session.commit(); acid = a.id
go('pca_gest', 'post', f'/pca-suivi/activation/{acid}/cloturer', data={'bilan': 'Reprise sur site de secours'})
with A.app.app_context():
    a = db.session.get(M.ActivationPCA, acid)
    verif('Retour à la normale : durée constatée (6 h), au-delà du RTO de 4 h', a.fin and a.duree_heures() == 6.0, str(a.duree_heures()))
r, t, _ = go('pca_gest', 'get', f'/pca/plan/{pid}')
verif('La fiche signale le dépassement du RTO', 'RTO dépassé' in t)

print('--- Liens et documents')
with A.app.app_context():
    rb = O['b']['risque']
go('pca_gest', 'post', f'/pca-suivi/{pid}/liens', data={'risque_ids': [str(O['a']['risque']), str(rb)]})
verif('Risques couverts : seul celui de l\'organisation est retenu', plan().risque_ids == [O['a']['risque']], str(plan().risque_ids))
go('pca_gest', 'post', f'/pca-suivi/{pid}/document', data={'fichier': (io.BytesIO(b'Annuaire de crise'), 'annuaire.txt'),
                                                           'categorie': 'procedure'}, content_type='multipart/form-data')
with A.app.app_context():
    d = M.DocumentPCA.query.filter_by(plan_id=pid).first(); did = d.id if d else None
verif('Document joint', did is not None)
r, _, _ = go('pca_lecteur', 'get', f'/pca-suivi/document/{did}')
verif('« Voir » télécharge le document', r.status_code == 200 and r.data == b'Annuaire de crise', str(r.status_code))
r, _, _ = go('admin_b', 'get', f'/pca-suivi/document/{did}')
verif('Une autre organisation ne le télécharge pas', r.status_code in (403, 404), str(r.status_code))
go('pca_gest', 'post', f'/pca-suivi/document/{did}/supprimer')
with A.app.app_context():
    verif('Document supprimé', db.session.get(M.DocumentPCA, did) is None)

print('--- Étanchéité')
for url in (f'/pca/plan/{pid}', f'/pca-suivi/exercice/{exid}/resultat'):
    r, _, _ = go('admin_b', 'get', url)
    verif(f'Autre organisation : {url} introuvable', r.status_code in (302, 403, 404), str(r.status_code))
go('admin_b', 'post', f'/pca-suivi/{pid}/valider')
verif('Autre organisation : pas de validation', plan().statut == 'valide')
print(f'\n{sum(res)}/{len(res)} vérifications réussies')
sys.exit(0 if all(res) else 1)
