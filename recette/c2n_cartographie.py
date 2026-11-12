"""Contrôle interne N2 relié à la cartographie : rattachement des dispositifs, méthode de test (échantillon,
conception / efficacité, gravité), effet d'une validation sur l'efficacité des dispositifs (par la campagne et par le
N2), annulation à la réouverture sans double pénalité, écrans et rapports, ménage (ancien module, pages de test)."""
import datetime as dt
import sys

import socle
import objets
from socle import Muet, appel, creer

with Muet():
    A, ids = socle.preparer()
    O = objets.peupler_objets(A, ids)
import models as M
from models import db

res = []


def verif(nom, cond, detail=''):
    res.append(bool(cond))
    print('OK   ' if cond else 'ÉCHEC', nom, detail)


def nav(role):
    return socle.navigateur(A, ids[role])


oa, ob = O['a'], O['b']
with A.app.app_context():
    pl = db.session.get(M.PlanificationControle, oa['planification'])
    ref_id = pl.referentiel_id
    ref = db.session.get(M.ReferentielControle, ref_id)
    ref.code_controle, ref.nom, ref.frequence = 'CTRL-PAI', 'Revue des paiements', 'mensuel'
    risque = db.session.get(M.Risque, oa['risque'])
    d1 = creer(M.DispositifMaitrise, reference='DM-PAI-1', nom='Double validation des paiements', risque_id=risque.id,
               client_id=risque.client_id, statut='actif', efficacite_reelle=4, frequence='Quotidien',
               created_by=ids['admin_a'])
    d2 = creer(M.DispositifMaitrise, reference='DM-PAI-2', nom='Rapprochement bancaire', risque_id=risque.id,
               client_id=risque.client_id, statut='actif', efficacite_reelle=4, frequence='Mensuel',
               created_by=ids['admin_a'])
    rb = db.session.get(M.Risque, ob['risque'])
    dx = creer(M.DispositifMaitrise, reference='DM-AUTRE', nom='Autre organisation', risque_id=rb.id,
               client_id=rb.client_id, statut='actif', efficacite_reelle=4, created_by=ids['admin_b'])
    db.session.commit()
    D1, D2, DX, RK = d1.id, d2.id, dx.id, risque.id


def dm(i):
    with A.app.app_context():
        db.session.expire_all()
        d = db.session.get(M.DispositifMaitrise, i)
        n = M.VerificationDispositif.query.filter_by(dispositif_id=i, type_verification='Contrôle N2').count()
        return d.efficacite_reelle, d.prochaine_verification, n


print('--- Rattachement du référentiel à la cartographie')
c = nav('admin_a')
r = appel(c, 'get', f'/c2n/referentiel/{ref_id}/modifier')
t = r.data.decode('utf-8', 'ignore')
verif('Référentiel : liste des dispositifs de la cartographie', r.status_code == 200 and 'DM-PAI-1' in t
      and 'Dispositifs de maîtrise testés' in t and 'DM-AUTRE' not in t, f'{r.status_code} {socle.cause(A)}')
r = appel(c, 'post', f'/c2n/referentiel/{ref_id}/modifier', data={
    'code_controle': 'CTRL-PAI', 'nom': 'Revue des paiements', 'processus': 'Paiements', 'metier': 'Finance',
    'objectif': 'Vérifier les paiements', 'risques_couverts': '', 'frequence': 'mensuel', 'responsable_id': '0',
    'dm_ids': [str(D1), str(D2), str(DX)], 'risque_ids': [str(RK)], 'frequence_execution': ''})
with A.app.app_context():
    ref = db.session.get(M.ReferentielControle, ref_id)
    verif('Dispositifs enregistrés (ceux d\'une autre organisation ignorés)', sorted(ref.dispositifs_ids or []) == sorted([D1, D2])
          and ref.risques_ids == [RK], f'{r.status_code} {ref.dispositifs_ids} {ref.risques_ids} {socle.cause(A)}')
    from egalyx.c2n_cartographie import echantillon_recommande, resultat
    taille, fourchette, freq = echantillon_recommande(ref)
    verif('Échantillon proposé selon le dispositif le plus fréquent (quotidien : 25, repère 20–40)',
          taille == 25 and fourchette == (20, 40), f'{taille} {fourchette} {freq}')
r = appel(c, 'get', f'/c2n/referentiel/{ref_id}/modifier')
t = r.data.decode('utf-8', 'ignore')
verif('Modification : dispositifs cochés', f'value="{D1}" id="dm{D1}"\n' in t or f'id="dm{D1}" data-risque="{RK}"\n                                               checked' in t
      or (f'id="dm{D1}"' in t and t.split(f'id="dm{D1}"')[1][:200].count('checked') >= 1), '')

print('--- Méthode de test dans les écrans')
r = appel(c, 'get', f'/c2n/planification/{oa["planification"]}/modifier')
t = r.data.decode('utf-8', 'ignore')
verif('Planification : type de test et taille d\'échantillon', r.status_code == 200 and 'Méthode de test' in t
      and 'taille_echantillon' in t and 'Test de conception' in t, f'{r.status_code} {socle.cause(A)}')
with A.app.app_context():
    pl = db.session.get(M.PlanificationControle, oa['planification'])
    pl.type_test, pl.taille_echantillon = 'efficacite', 25
    db.session.commit()

print('--- Validation par la campagne → cartographie')
cid = oa['campagne']
op, val = nav('operateur'), nav('validateur')
appel(op, 'post', f'/operateur/campagne/{cid}/demarrer')
form = dict(nb_dossiers_controles='10', nb_conformes='7', nb_anomalies='3', motifs_anomalie='Pièce manquante',
            commentaire_general='RAS', conclusion='70 %', actions_correctives='Former', action='submit')
appel(op, 'post', f'/operateur/campagne/{cid}/executer', data=form)
socle.cause(A)
r = appel(val, 'get', f'/c2n/planification/{oa["planification"]}')
t = r.data.decode('utf-8', 'ignore')
verif('Détail N2 : encadré « Méthode et cartographie » avec les dispositifs', r.status_code == 200 and 'Méthode et cartographie' in t
      and 'DM-PAI-1' in t, f'{r.status_code} {socle.cause(A)}')
r = appel(val, 'post', f'/operateur/campagne/{cid}/valider', data={'action': 'valider', 'commentaire': 'OK'})
e = socle.cause(A)
with A.app.app_context():
    camp = db.session.get(M.CampagneControle, cid)
    statut = camp.statut
eff1, prochaine1, nv1 = dm(D1)
verif('Campagne validée', statut == 'termine', f'{statut} {e}')
verif('Taux 70 % → « À corriger » : efficacité 4 → 3 sur chaque dispositif testé', eff1 == 3 and dm(D2)[0] == 3,
      f'{eff1} {dm(D2)[0]}')
verif('Vérification « Contrôle N2 » enregistrée sur le dispositif', nv1 == 1, str(nv1))
verif('Prochaine vérification dans 30 jours (après un échec)', prochaine1 == dt.date.today() + dt.timedelta(days=30), str(prochaine1))
verif('Dispositif d\'une autre organisation intact', dm(DX)[0] == 4)
with A.app.app_context():
    h = M.DispositifHistoriqueEfficacite.query.filter_by(dispositif_id=D1).order_by(M.DispositifHistoriqueEfficacite.id.desc()).first()
    pl = db.session.get(M.PlanificationControle, oa['planification'])
    trace = pl.execution.impact_cartographie if pl.execution else None
    verif('Historique d\'efficacité tracé', h is not None and h.ancienne_efficacite == 4 and h.efficacite == 3)
    verif('Trace sur l\'exécution (avant / après, résultat)', trace and trace.get('resultat') == 'À corriger'
          and trace['dispositifs'][str(D1)] == {'avant': 4, 'apres': 3, 'verification_id': trace['dispositifs'][str(D1)]['verification_id']},
          str(trace)[:200])
    from egalyx.c2n_cartographie import section_rapport
    html = section_rapport(pl)
    verif('Rapport PDF : section méthode et effet (4 → 3)', 'MÉTHODE DE TEST' in html and 'efficacité 4 → 3' in html, html[:150])

print('--- Réouverture : effet annulé, puis nouvelle validation sans double pénalité')
r = appel(nav('admin_a'), 'post', f'/operateur/campagne/{cid}/rouvrir', data={'raison': 'Pièces complémentaires reçues'})
e = socle.cause(A)
eff, _p, nv = dm(D1)
verif('Réouverture : efficacité rétablie (4) et vérification N2 retirée', eff == 4 and nv == 0, f'{eff} {nv} {e}')
appel(op, 'post', f'/operateur/campagne/{cid}/executer', data=form)
appel(val, 'post', f'/operateur/campagne/{cid}/valider', data={'action': 'valider', 'commentaire': 'OK'})
socle.cause(A)
eff, _p, nv = dm(D1)
verif('Nouvelle validation : 4 → 3 une seule fois, une seule vérification', eff == 3 and nv == 1, f'{eff} {nv}')
with A.app.app_context():
    from egalyx.c2n_cartographie import appliquer
    pl = db.session.get(M.PlanificationControle, oa['planification'])
    n = appliquer(pl, db.session.get(M.User, ids['validateur']))
    db.session.commit()
verif('Appliquer deux fois ne change rien (idempotent)', n == 0 and dm(D1)[0] == 3, str(n))

print('--- Règle de résultat (taux et gravité)')
with A.app.app_context():
    from egalyx.c2n_cartographie import resultat as res_fn

    class Ex:
        def __init__(self, t, g, nb=1):
            self.taux_conformite, self.gravite_deficience, self.nb_anomalies, self.nb_conformes, self.id = t, g, nb, 0, -1

    class Pl:
        def __init__(self, ex, tt='efficacite'):
            self.execution, self.type_test = ex, tt
    cas = [((100, 'aucune', 0), 'Conforme'), ((96, 'mineure'), 'Conforme'), ((90, None), 'À améliorer'),
           ((70, None), 'À corriger'), ((50, None), 'Non conforme'), ((99, 'significative'), 'À corriger'),
           ((99, 'majeure'), 'Non conforme')]
    ok = all(res_fn(Pl(Ex(*a)))[0] == attendu for a, attendu in cas)
    verif('Taux ≥ 95 conforme, 80–95 à améliorer, 60–80 à corriger, < 60 non conforme ; gravité prise si plus sévère', ok,
          str([(a, res_fn(Pl(Ex(*a)))[0]) for a, _x in cas]))
    verif('Test de conception : le taux ne compte pas, seule la gravité', res_fn(Pl(Ex(40, 'mineure'), 'conception'))[0] == 'Conforme')

print('--- Validation directement dans le N2 (déficience majeure → −2)')
with A.app.app_context():
    ref2 = creer(M.ReferentielControle, client_id=1, code_controle='CTRL-N2', nom='Contrôle N2 direct',
                 dispositifs_ids=[D2], risques_ids=[RK])
    pl2 = creer(M.PlanificationControle, reference='PL-N2', annee=2026, date_prevue=dt.date.today(), referentiel_id=ref2.id,
                client_id=1, controleur_id=ids['operateur'], validateur_requis_id=ids['validateur'], statut='soumis',
                soumis_par_id=ids['operateur'], date_soumission=dt.datetime.utcnow())
    ex2 = creer(M.ExecutionControle, volume_controle=10, nb_conformes=10, nb_anomalies=0, taux_conformite=100,
                gravite_deficience='majeure', client_id=1, execute_par_id=ids['operateur'])
    db.session.flush()
    pl2.execution_id = ex2.id
    db.session.commit()
    avant = db.session.get(M.DispositifMaitrise, D2).efficacite_reelle
    ok, msg = db.session.get(M.PlanificationControle, pl2.id).valider(db.session.get(M.User, ids['validateur']), 'OK')
    db.session.commit()
    apres = db.session.get(M.DispositifMaitrise, D2).efficacite_reelle
verif('Validation dans le N2 : déficience majeure → non conforme, efficacité −2', ok and apres == max(1, avant - 2),
      f'{ok} {msg} {avant} → {apres}')

print('--- Gravité saisie sur la page d\'exécution du N2')
with A.app.app_context():
    pl3 = creer(M.PlanificationControle, reference='PL-EXE', annee=2026, date_prevue=dt.date.today(), referentiel_id=ref_id,
                client_id=1, controleur_id=ids['gestionnaire'], validateur_requis_id=ids['validateur'], statut='en_cours',
                created_by=ids['admin_a'])
    db.session.commit()
    P3 = pl3.id
r = appel(nav('gestionnaire'), 'get', f'/c2n/planification/{P3}/executer')
t = r.data.decode('utf-8', 'ignore')
verif('Exécution : choix de la gravité et rappel de l\'effet sur les dispositifs', r.status_code == 200
      and 'Gravité de la déficience' in t and 'dispositif(s) de maîtrise seront mis à jour' in t, f'{r.status_code} {socle.cause(A)}')
with A.app.app_context():
    v = db.session.get(M.PlanificationControle, P3).version
r = appel(nav('gestionnaire'), 'post', f'/c2n/planification/{P3}/executer', data={'version': str(v or 1), 'volume_controle': '25',
          'nb_conformes': '24', 'nb_anomalies': '0', 'resultats': 'ok', 'commentaires': '', 'conclusion': 'ok',
          'gravite_deficience': 'significative', 'action': 'save'})
e = socle.cause(A)
with A.app.app_context():
    p3 = db.session.get(M.PlanificationControle, P3)
    g = p3.execution.gravite_deficience if p3.execution else None
verif('Gravité enregistrée avec l\'exécution', g == 'significative', f'{r.status_code} {g} {e}')

print('--- Ménage')
r = appel(nav('admin_a'), 'get', '/controle/programmes')
verif('Ancien module « programmes de contrôle » → planification N2', r.status_code == 302
      and '/c2n/planification' in (r.headers.get('Location') or ''), f'{r.status_code} {r.headers.get("Location")}')
r = appel(nav('admin_a'), 'get', '/controle/mission/nouvelle')
verif('Ancien module « missions » → planification N2', r.status_code == 302 and '/c2n/planification' in (r.headers.get('Location') or ''))
r = appel(nav('admin_a'), 'get', '/test-multi-tenant')
verif('Page de test : introuvable pour un administrateur client', r.status_code == 404, str(r.status_code))
r = appel(A.app.test_client(), 'get', '/test-api')
verif('Page de test : introuvable sans connexion', r.status_code == 404, str(r.status_code))
r = appel(nav('superadmin'), 'get', '/test-multi-tenant')
verif('Page de test : accessible au super admin', r.status_code != 404, str(r.status_code))

print(f'\n{sum(res)}/{len(res)} vérifications réussies')
sys.exit(0 if all(res) else 1)
