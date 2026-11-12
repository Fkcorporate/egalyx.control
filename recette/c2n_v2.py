"""Contrôle interne N2, suite : seuils et échantillons réglables par organisation, échantillon élément par élément
(tirage aléatoire reproductible, résultats, preuves, totaux et anomalies), registre unique des plans d'action et plans
N2 visibles sur le dispositif et le risque."""
import datetime as dt
import io
import random
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


def go(role, m, url, **kw):
    r = appel(nav(role), m, url, **kw)
    return r, r.data.decode('utf-8', 'ignore')


oa = O['a']
with A.app.app_context():
    risque = db.session.get(M.Risque, oa['risque'])
    d1 = creer(M.DispositifMaitrise, reference='DM-V2-1', nom='Contrôle des virements', risque_id=risque.id,
               client_id=risque.client_id, statut='actif', efficacite_reelle=4, frequence='Quotidien', created_by=ids['admin_a'])
    db.session.flush()
    ref = creer(M.ReferentielControle, client_id=1, code_controle='CTRL-V2', nom='Revue des virements',
                dispositifs_ids=[d1.id], risques_ids=[risque.id], frequence='mensuel')
    pl = creer(M.PlanificationControle, reference='PL-V2', annee=2026, date_prevue=dt.date.today(), referentiel_id=ref.id,
               client_id=1, controleur_id=ids['gestionnaire'], validateur_requis_id=ids['validateur'], statut='en_cours',
               created_by=ids['admin_a'])
    db.session.commit()
    D1, RK, REF, PL = d1.id, risque.id, ref.id, pl.id

print('--- Réglages par organisation')
r, _ = go('lecteur', 'get', '/c2n/reglages/')
verif('Lecteur : réglages refusés', r.status_code in (302, 403), str(r.status_code))
r, t = go('admin_a', 'get', '/c2n/reglages/')
verif('Admin : page des réglages (seuils, tailles)', r.status_code == 200 and 'Conforme à partir de' in t and 'Quotidien' in t,
      f'{r.status_code} {socle.cause(A)}')
go('admin_a', 'post', '/c2n/reglages/', data={'action': 'enregistrer', 'seuil_conforme': '80', 'seuil_ameliorer': '90',
                                              'seuil_corriger': '50'})
with A.app.app_context():
    from egalyx.c2n_cartographie import reglages
    verif('Seuils incohérents refusés', reglages(1)['seuils']['conforme'] == 95, str(reglages(1)['seuils']))
data = {'action': 'enregistrer', 'seuil_conforme': '90', 'seuil_ameliorer': '70', 'seuil_corriger': '50'}
data.update({f'ech_{c}': v for c, v in [('quotidien', '30'), ('mensuel', '4')]})
go('admin_a', 'post', '/c2n/reglages/', data=data)
with A.app.app_context():
    from egalyx.c2n_cartographie import reglages, resultat, echantillon_recommande
    rg = reglages(1)
    verif('Réglages enregistrés', rg['seuils'] == {'conforme': 90, 'ameliorer': 70, 'corriger': 50}
          and rg['echantillons']['quotidien'] == 30, str(rg))
    verif('Autre organisation : valeurs par défaut', reglages(2)['seuils']['conforme'] == 95)

    class Ex:
        taux_conformite, gravite_deficience, nb_anomalies, nb_conformes, id = 75, None, 1, 0, -1

    class Pl:
        execution, type_test, client_id = Ex(), 'efficacite', 1
    verif('Taux 75 % : « à améliorer » avec les seuils de l\'organisation (« à corriger » par défaut)',
          resultat(Pl())[0] == 'À améliorer', resultat(Pl())[0])
    verif('Taille proposée selon l\'organisation (quotidien : 30)', echantillon_recommande(db.session.get(M.ReferentielControle, REF))[0] == 30)
go('admin_a', 'post', '/c2n/reglages/', data={'action': 'defaut'})
with A.app.app_context():
    verif('Rétablir les valeurs par défaut', reglages(1)['seuils']['conforme'] == 95 and not reglages(1)['personnalise'])

print('--- Échantillon élément par élément')
g = nav('gestionnaire')
r = appel(g, 'get', f'/c2n/planification/{PL}/echantillon')
t = r.data.decode('utf-8', 'ignore')
verif('Page Échantillon : tirage proposé avec la taille selon la fréquence (25)', r.status_code == 200
      and 'Tirer au hasard' in t and 'value="25"' in t, f'{r.status_code} {socle.cause(A)}')
population = [f'VIR-2026-{i:04d}' for i in range(1, 201)]
r = appel(g, 'post', f'/c2n/planification/{PL}/echantillon', data={'action': 'tirer', 'taille': '25',
                                                                    'population': '\n'.join(population + ['VIR-2026-0001'])})
socle.cause(A)
with A.app.app_context():
    p = db.session.get(M.PlanificationControle, PL)
    els = M.ElementEchantillonN2.query.filter_by(execution_id=p.execution_id).order_by(M.ElementEchantillonN2.numero).all()
    t_ = p.execution.tirage_echantillon if p.execution else {}
    verif('25 éléments tirés parmi 200 (doublon de la population ignoré)', len(els) == 25 and t_.get('population') == 200,
          f'{len(els)} {t_}')
    verif('Tirage reproductible avec la graine conservée', [e.reference for e in els] == random.Random(t_['graine']).sample(population, 25))
    EIDS = [e.id for e in els]
form = {'action': 'enregistrer'}
for i, eid in enumerate(EIDS):
    if i < 20:
        form[f'res_{eid}'] = 'conforme'
    elif i < 23:
        form.update({f'res_{eid}': 'anomalie', f'motif_{eid}': 'Virement sans double signature', f'crit_{eid}': 'majeur'})
    else:
        form[f'res_{eid}'] = 'a_tester'
form[f'preuve_{EIDS[0]}'] = (io.BytesIO(b'%PDF-1.4 preuve'), 'releve.pdf')
r = appel(g, 'post', f'/c2n/planification/{PL}/echantillon', data=form, content_type='multipart/form-data')
e = socle.cause(A)
with A.app.app_context():
    db.session.expire_all()
    ex = db.session.get(M.PlanificationControle, PL).execution
    an = M.AnomalieDetectee.query.filter_by(execution_id=ex.id).all()
    verif('Totaux calculés : 23 testés, 20 conformes, 3 anomalies', (ex.volume_controle, ex.nb_conformes, ex.nb_anomalies) == (23, 20, 3),
          f'{(ex.volume_controle, ex.nb_conformes, ex.nb_anomalies)} {e}')
    verif('Taux de conformité calculé (≈ 87 %)', ex.taux_conformite is not None and 86 <= float(ex.taux_conformite) <= 88, str(ex.taux_conformite))
    verif('Chaque élément en anomalie devient une anomalie du contrôle (référence, criticité)', len(an) == 3
          and all(a.criticite == 'majeur' and a.element_concerne.startswith('VIR-2026-') for a in an), str(len(an)))
    el0 = db.session.get(M.ElementEchantillonN2, EIDS[0])
    verif('Preuve jointe et testeur tracés', el0.preuve_nom == 'releve.pdf' and el0.teste_par_id == ids['gestionnaire'])
r = appel(g, 'get', f'/c2n/echantillon/preuve/{EIDS[0]}')
verif('Preuve téléchargeable par l\'organisation', r.status_code == 200 and r.data.startswith(b'%PDF'), str(r.status_code))
r, _ = go('admin_b', 'get', f'/c2n/echantillon/preuve/{EIDS[0]}')
verif('Preuve introuvable pour une autre organisation', r.status_code == 404, str(r.status_code))
r = appel(g, 'post', f'/c2n/planification/{PL}/echantillon', data={'action': 'tirer', 'taille': '5', 'population': 'A\nB\nC\nD\nE\nF'})
with A.app.app_context():
    n = M.ElementEchantillonN2.query.filter_by(execution_id=ex.id).count()
verif('Nouveau tirage refusé quand des éléments sont déjà testés', n == 25, str(n))
appel(g, 'post', f'/c2n/planification/{PL}/echantillon', data={'action': 'enregistrer', f'res_{EIDS[20]}': 'conforme',
                                                               **{f'res_{x}': 'conforme' for x in EIDS[:20]},
                                                               f'res_{EIDS[21]}': 'anomalie', f'motif_{EIDS[21]}': 'Virement sans double signature',
                                                               f'res_{EIDS[22]}': 'anomalie', f'motif_{EIDS[22]}': 'Virement sans double signature'})
with A.app.app_context():
    db.session.expire_all()
    ex = db.session.get(M.PlanificationControle, PL).execution
    verif('Anomalie corrigée en « conforme » : anomalie retirée, totaux à jour', ex.nb_anomalies == 2
          and M.AnomalieDetectee.query.filter_by(execution_id=ex.id).count() == 2, f'{ex.nb_anomalies}')
r = appel(g, 'post', f'/c2n/planification/{PL}/echantillon', data={'action': 'ajouter', 'references': 'VIR-SPEC-1\nVIR-SPEC-2'})
with A.app.app_context():
    n = M.ElementEchantillonN2.query.filter_by(execution_id=ex.id).count()
verif('Ajout manuel d\'éléments', n == 27, str(n))
r = appel(g, 'get', f'/c2n/planification/{PL}/echantillon.csv')
t = r.data.decode('utf-8-sig', 'ignore')
verif('Export CSV : tirage (graine) et éléments', r.status_code == 200 and 'graine' in t and 'VIR-SPEC-1' in t, str(r.status_code))
r = appel(g, 'get', f'/c2n/planification/{PL}/executer')
t = r.data.decode('utf-8', 'ignore')
verif('Exécution : volumes calculés depuis l\'échantillon (champs verrouillés)', 'Volumes calculés depuis l\'échantillon' in t
      and 'readonly title="Calculé depuis' in t, f'{r.status_code} {socle.cause(A)}')
with A.app.app_context():
    v = db.session.get(M.PlanificationControle, PL).version
appel(g, 'post', f'/c2n/planification/{PL}/executer', data={'version': str(v or 1), 'volume_controle': '99', 'nb_conformes': '99',
                                                            'nb_anomalies': '0', 'resultats': 'x', 'conclusion': 'x', 'action': 'save'})
with A.app.app_context():
    db.session.expire_all()
    ex = db.session.get(M.PlanificationControle, PL).execution
verif('Enregistrer l\'exécution ne remplace pas les volumes de l\'échantillon', (ex.volume_controle, ex.nb_anomalies) == (23, 2),
      f'{(ex.volume_controle, ex.nb_anomalies)} {socle.cause(A)}')
with A.app.app_context():
    from egalyx.c2n_cartographie import section_rapport
    html = section_rapport(db.session.get(M.PlanificationControle, PL))
verif('Rapport PDF : échantillon suivi et tirage', 'Échantillon suivi' in html and 'tirage aléatoire de 25 parmi 200' in html, html[:120])
r, _ = go('lecteur', 'get', f'/c2n/planification/{PL}/echantillon')
verif('Lecteur sans droit N2 : refusé', r.status_code in (302, 403), str(r.status_code))
with A.app.app_context():
    p = db.session.get(M.PlanificationControle, PL)
    p.statut = 'valide'
    db.session.commit()
r = appel(g, 'get', f'/c2n/planification/{PL}/echantillon')
t = r.data.decode('utf-8', 'ignore')
verif('Planification validée : échantillon en lecture seule', r.status_code == 200 and 'Tirer au hasard' not in t
      and 'name="res_' not in t, str(r.status_code))

print('--- Registre unique des plans d\'action')
with A.app.app_context():
    exid = db.session.get(M.PlanificationControle, PL).execution_id
    nc = creer(M.NonConformiteC2N, reference='NC-V2', execution_id=exid, description='Virements sans double signature',
               client_id=1, created_by=ids['admin_a'], statut='ouverte')
    db.session.flush()
    pa = creer(M.PlanActionC2N, reference='PAC2N-V2', non_conformite_id=nc.id, action_corrective='Rappeler la double signature',
               date_echeance=dt.date.today() - dt.timedelta(days=3), statut='en_cours', responsable_id=ids['gestionnaire'],
               client_id=1, createur_id=ids['admin_a'], taux_avancement=40)
    pr = creer(M.PlanAction, reference='PA-RISQ-V2', nom='Revoir le circuit des virements', risque_id=RK, client_id=1,
               created_by=ids['admin_a'], statut='en_cours', responsable_id=ids['gestionnaire'],
               date_fin_prevue=dt.date.today() + dt.timedelta(days=20))
    db.session.commit()
r, t = go('admin_a', 'get', '/plans-action/registre/')
verif('Registre : plans des risques et plans N2 ensemble', r.status_code == 200 and 'PAC2N-V2' in t and 'PA-RISQ-V2' in t,
      f'{r.status_code} {socle.cause(A)}')
verif('Plan N2 rattaché à son contrôle et signalé en retard', 'Contrôle CTRL-V2' in t and 'en retard' in t)
r, t = go('admin_a', 'get', '/plans-action/registre/?source=n2')
verif('Filtre « Contrôle N2 »', 'PAC2N-V2' in t and 'PA-RISQ-V2' not in t)
r, t = go('admin_a', 'get', '/plans-action/registre/?retard=1')
verif('Filtre « En retard »', 'PAC2N-V2' in t and 'PA-RISQ-V2' not in t)
r, t = go('admin_b', 'get', '/plans-action/registre/')
verif('Autre organisation : rien de A', 'PAC2N-V2' not in t and 'PA-RISQ-V2' not in t)
r, t = go('admin_a', 'get', f'/dispositif/{D1}')
verif('Fiche du dispositif : plans d\'action du contrôle N2', r.status_code == 200 and 'Plans d\'action du contrôle N2' in t
      and 'PAC2N-V2' in t, f'{r.status_code} {socle.cause(A)}')
r, t = go('admin_a', 'get', f'/risque/{RK}')
verif('Fiche du risque : plans d\'action du contrôle N2', r.status_code == 200 and 'PAC2N-V2' in t, f'{r.status_code} {socle.cause(A)}')

print(f'\n{sum(res)}/{len(res)} vérifications réussies')
sys.exit(0 if all(res) else 1)
