"""Recette : rapport complet d'audit et éditeur de feuille de travail (nouvelle présentation)."""
import datetime as dt
import socle
from socle import Muet
with Muet():
    A, ids = socle.preparer()
import objets, models as M
from models import db
with Muet():
    try: objets.peupler_objets(A, ids)
    except TypeError: objets.peupler_objets(A)
with A.app.app_context():
    uid = ids['admin_a']; cid = db.session.get(M.User, uid).client_id
    r = M.Risque.query.filter_by(client_id=cid).first()
    au = M.Audit(reference='AUD-2026-014', titre='Audit du processus achats et paiement fournisseurs', type_audit='interne', client_id=cid,
                 statut='en_cours', created_by=uid, responsable_id=uid, date_debut_prevue=dt.date(2026, 10, 5), date_fin_prevue=dt.date(2026, 11, 28),
                 description="Revue du cycle achats : création des fournisseurs, commandes, réception, facturation et paiement.",
                 objectifs="Vérifier la séparation des tâches, la fiabilité des données fournisseurs et la conformité des paiements.",
                 portee="Siège et filiale de Douala — période du 01/01/2026 au 30/09/2026.", equipe_audit_ids=str(uid))
    db.session.add(au); db.session.flush()
    c1 = M.Constatation(reference='CONST-01', audit_id=au.id, client_id=cid, type_constatation='non_conformite', gravite='critique', statut='en_action',
                        description="Trois changements de RIB fournisseurs ont été effectués sans double validation ni contre-appel.",
                        cause_racine="Le paramétrage de l'ERP n'impose pas de second valideur.", risque_id=r.id if r else None, created_by=uid, is_archived=False)
    c2 = M.Constatation(reference='CONST-02', audit_id=au.id, client_id=cid, type_constatation='observation', gravite='moyenne', statut='a_valider',
                        description="12 % des factures sont payées avant le rapprochement avec le bon de réception.", created_by=uid, is_archived=False)
    db.session.add_all([c1, c2]); db.session.flush()
    rc = M.Recommandation(reference='REC-01', audit_id=au.id, client_id=cid, type_recommandation='corrective', statut='en_cours', constatation_id=c1.id,
                          description="Imposer une double validation et un contre-appel pour toute modification de coordonnées bancaires.",
                          responsable_id=uid, date_echeance=dt.date(2026, 12, 31), urgence=4, impact_operationnel=5)
    db.session.add(rc); db.session.flush()
    pa = M.PlanAction(reference='PA-AUD-01', nom='Sécuriser les changements de RIB', audit_id=au.id, client_id=cid, statut='en_cours',
                      pourcentage_realisation=40, date_debut=dt.date(2026, 11, 1), date_fin_prevue=dt.date(2026, 12, 31), responsable_id=uid,
                      recommandation_id=rc.id, risque_id=r.id if r else None, is_archived=False)
    db.session.add(pa)
    fe = M.FeuilleTravail(reference='FT-ACH-01', titre='Tests sur les paiements fournisseurs', audit_id=au.id, client_id=cid, is_archived=False)
    db.session.add(fe); db.session.flush()
    for obj, res, el, err, crit in (('Double validation des changements de RIB', 'non_conforme', 25, 3, 'critique'),
                                    ('Rapprochement facture / bon de réception', 'partiellement_conforme', 60, 7, 'moyen'),
                                    ('Respect des délais de paiement', 'conforme', 40, 0, 'faible')):
        db.session.add(M.TestControleFeuille(feuille_travail_id=fe.id, objet_test=obj, resultat=res, nb_elements_testes=el, nb_erreurs_trouvees=err,
                                             niveau_criticite=crit, is_archived=False, procedure='Échantillon aléatoire sur la période.',
                                             ecart_constate=('Écarts relevés sur ' + str(err) + ' éléments.') if err else None))
    db.session.commit()
    aid, fid = au.id, fe.id
res = []


def verif(nom, cond, detail=''):
    res.append(bool(cond)); print('OK   ' if cond else 'ÉCHEC', nom, detail)


c = socle.navigateur(A, ids['admin_a'])
r = c.get(f'/audit/{aid}/rapport-complet'); t = r.get_data(as_text=True)
verif('rapport complet : page OK', r.status_code == 200, f'{r.status_code} {socle.cause(A)}')
for s_ in ('1.</span>Synthèse', '3.</span>Constatations', '4.</span>Tests de contrôle', '5.</span>Recommandations', '6.</span>Plans d', '8.</span>Annexes'):
    verif(f'rapport : section {s_.split(">")[-1]}', s_ in t)
verif('rapport : responsable affiché (était « Non assigné »)', 'Non assigné' not in t and 'admin_a' in t)
verif('rapport : gravité et statut lisibles', '>Critique<' in t and '>En action<' in t and '>Moyenne<' in t)
verif('rapport : anomalie détaillée', 'Anomalies détectées (1)' in t and 'Écarts relevés sur 3 éléments' in t)
verif('rapport : point d\'attention prioritaire', 'CONST-01' in t.split('Points d')[1][:400] if 'Points d' in t else False)
verif('rapport : dates en français', 'November' not in t)
verif('rapport : autre organisation refusée', socle.navigateur(A, ids['admin_b']).get(f'/audit/{aid}/rapport-complet').status_code in (302, 403, 404))
r = c.get(f'/editer-feuille-travail/{fid}'); t = r.get_data(as_text=True)
verif('éditeur de feuille : page OK', r.status_code == 200, f'{r.status_code} {socle.cause(A)}')
for ident in ('id="globalProgress"', 'id="progressText"', 'id="editorTabs"', 'id="progressionSlider"', 'id="testsCount"', "saveVersion()", "showVersions()",
              "exportFeuille('pdf-complet')", 'calculerProgressionReelle()', 'toggleFullScreen()'):
    verif(f'éditeur : {ident} conservé', ident in t)
verif('éditeur : nouvel en-tête et indicateurs', 'ft-entete' in t and 'ft-kpis' in t and 'AUD-2026-014' in t)
verif('éditeur : taux de conformité calculé (33 %)', '33 %' in t)
print(f'\n{sum(res)}/{len(res)}')
