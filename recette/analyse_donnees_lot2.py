"""Recette : analyse des données, lot 2 — comptabilité (grand livre SYSCOHADA et fichier FEC), ventes et encaissements.

Import FEC (tabulations, dates AAAAMMJJ, virgule décimale) et export SYSCOHADA ; date de clôture proposée puis confirmée ;
19 tests sur un jeu fictif aux anomalies connues ; constat rattaché au bon processus ; export."""
import io
import json
import os
import re
import tempfile

os.environ['EGALYX_COLLECTE_AUTO'] = '0'
import socle
from socle import Muet, appel
from cryptography.fernet import Fernet
os.environ['EGALYX_CLE_CHIFFREMENT'] = Fernet.generate_key().decode()
with Muet():
    A, ids = socle.preparer()
os.environ['EGALYX_DOSSIER_ANALYSES'] = tempfile.mkdtemp(prefix='recette_ad2_')
import models as M
from models import db
from egalyx import analyse_moteur as am
import donnees_compta_ventes_demo as dd

res = []


def verif(nom, cond, detail=''):
    res.append(bool(cond)); print('OK   ' if cond else 'ÉCHEC', nom, detail)


def jeton(c, url):
    t = appel(c, 'get', url).data.decode(errors='ignore')
    m = re.search(r'name="csrf_token" value="([^"]+)"', t) or re.search(r'name="csrf-token" content="([^"]+)"', t)
    return m.group(1) if m else ''


def poster(c, url, data=None, page=None):
    return appel(c, 'post', url, data={**(data or {}), 'csrf_token': jeton(c, page or url)})


sa, gest = socle.navigateur(A, ids['superadmin']), socle.navigateur(A, ids['gestionnaire'])
with A.app.app_context():
    c = db.session.get(M.Client, 1); c.modules_actifs = {'audit': True, 'analyse_donnees': True}
    a = socle.creer(M.Audit, reference='AUD-CPT', titre='Audit de la clôture des comptes 2025', type_audit='interne', client_id=1,
                    statut='en_cours', responsable_id=ids['gestionnaire'])
    db.session.commit()
    AID = a.id

print('--- 0. Moteur')
verif('horodatage « 11/06/2025 23:40 » : heure conservée', am.lire_horodatage('11/06/2025 23:40').hour == 23)
verif('horodatage FEC « 20250611 »', am.lire_horodatage('20250611').day == 11)
verif('19 tests comptabilité et ventes dans la bibliothèque', len(am.TESTS) >= 40
      and sum(1 for t in am.TESTS if t['domaine'] in ('Comptabilité', 'Ventes et encaissements')) == 19)

poster(gest, f'/analyse-donnees/audit/{AID}/nouvelle', {'titre': 'Clôture 2025'}, page=f'/analyse-donnees/audit/{AID}')
with A.app.app_context():
    ANID = M.AnalyseDonnees.query.filter_by(audit_id=AID).first().id
PAGE = f'/analyse-donnees/{ANID}'
G = dd.generer()


def importer(t, octets, nom):
    r = appel(gest, 'post', f'{PAGE}/jeu/{t}/importer', data={'csrf_token': jeton(gest, PAGE), 'fichier': (io.BytesIO(octets), nom)},
              content_type='multipart/form-data')
    with A.app.app_context():
        j = M.JeuDonneesAnalyse.query.filter_by(analyse_id=ANID, type_jeu=t).order_by(M.JeuDonneesAnalyse.id.desc()).first()
        corr = dict(j.correspondance or {})
    appel(gest, 'post', f'{PAGE}/jeu/{t}/colonnes', data={'csrf_token': jeton(gest, f'{PAGE}/jeu/{t}/colonnes')} | {f'c_{k}': v for k, v in corr.items()})
    with A.app.app_context():
        return db.session.get(M.JeuDonneesAnalyse, j.id), corr


print('--- 1. Import du FEC')
j, corr = importer('grand_livre', dd.en_fec(G['grand_livre']), 'FEC_2025.txt')
verif('FEC : colonnes reconnues automatiquement (EcritureNum, EcritureDate, CompteNum, Debit, Credit, ValidDate…)',
      corr.get('numero') == 'EcritureNum' and corr.get('date') == 'EcritureDate' and corr.get('compte') == 'CompteNum'
      and corr.get('debit') == 'Debit' and corr.get('credit') == 'Credit' and corr.get('date_saisie') == 'ValidDate', corr)
verif('FEC : prêt, dates AAAAMMJJ et virgule décimale lues sans erreur', j.statut == 'pret' and j.nb_lignes == len(G['grand_livre'])
      and all(c['erreurs'] == 0 for c in j.qualite['champs']), (j.statut, j.nb_lignes))
verif('FEC : totaux débit et crédit, écart signalé (écriture déséquilibrée plantée)', abs(j.qualite['total'] - j.qualite['total_credit'] - 10_000) < 1
      and any('débits' in w for w in j.qualite['avertissements']))
verif('grand livre : une ligne n’a qu’un côté, pas d’alerte « débit vide »', not any('« Débit »' in w for w in j.qualite['avertissements']))

print('--- 2. Export SYSCOHADA, ventes, clients, encaissements')
for t, (octets, nom) in {'grand_livre': (dd.en_csv(G['grand_livre']), 'Grand_livre_2025.csv'), 'ventes': (dd.en_xlsx(G['ventes']), 'Ventes_2025.xlsx'),
                         'clients': (dd.en_csv(G['clients']), 'Clients.csv'), 'encaissements': (dd.en_csv(G['encaissements']), 'Encaissements_2025.csv')}.items():
    j, corr = importer(t, octets, nom)
    verif(f'{t} : prêt ({j.nb_lignes} lignes)', j.statut == 'pret' and j.nb_lignes == len(G[t]), corr)
r = appel(gest, 'get', f'{PAGE}?etape=donnees')
verif('page Données : cycles, carte du grand livre avec débit et crédit', r.data.count(b'class="ad-cycle"') == len(am.CYCLES) and 'Crédit</dt>'.encode() in r.data)

print('--- 3. Date de clôture')
r = appel(gest, 'get', f'{PAGE}?etape=tests')
verif('clôture proposée d’après les données : 31/12/2025', b'value="31/12/2025"' in r.data and 'vérifiez-la'.encode() in r.data)
verif('tests comptabilité, ventes et statistiques applicables', r.data.count(b'data-applicable="1"') == 21, r.data.count(b'data-applicable="1"'))
codes = [t['code'] for t in am.TESTS if t['domaine'] in ('Comptabilité', 'Ventes et encaissements')]
donnees = {f't_{c}': '1' for c in codes}
r = poster(gest, f'{PAGE}/executer', dict(donnees, cloture='32/13/2025'), page=f'{PAGE}?etape=tests')
with A.app.app_context():
    verif('date de clôture illisible : refusée, rien n’est exécuté', not db.session.get(M.AnalyseDonnees, ANID).resultats)
poster(gest, f'{PAGE}/executer', dict(donnees, cloture=''), page=f'{PAGE}?etape=tests')
with A.app.app_context():
    R = db.session.get(M.AnalyseDonnees, ANID).resultats
    sans = [c for c in codes if R[c]['statut'] == 'non_applicable']
    verif('sans date de clôture : les 4 tests de fin de période l’indiquent', sorted(sans) == sorted(['GL_APRES_CLOTURE', 'GL_EXTOURNES', 'VTE_AVOIRS_CLOTURE', 'VTE_CUT_OFF'])
          and 'clôture' in R['GL_EXTOURNES']['raison'], sans)
poster(gest, f'{PAGE}/executer', dict(donnees, cloture='31/12/2025', p_GL_UTILISATEURS_habilites='M. Traoré\nA. Koné\nK. Yao'), page=f'{PAGE}?etape=tests')
with A.app.app_context():
    an = db.session.get(M.AnalyseDonnees, ANID)
    R = an.resultats
    verif('clôture enregistrée avec les résultats', an.execution.get('cloture') == '2025-12-31' and an.parametres['_general']['cloture'] == '2025-12-31')
    for code, refs in dd.ATTENDU.items():
        trouve = {x['ref'] for x in R[code]['anomalies']} | {x['tiers'].split(' — ')[0] for x in R[code]['anomalies']}
        verif(f'{code} : anomalies plantées retrouvées ({R[code]["nb"]} ligne(s))', refs <= trouve, refs - trouve)
    verif('Benford sur le grand livre : conforme, aucune ligne signalée', R['GL_BENFORD']['statut'] == 'ok' and R['GL_BENFORD']['tableau']['mad'] <= 0.012)
    verif('contre-passation : les deux écritures dans le même cas', len({x['groupe'] for x in R['GL_EXTOURNES']['anomalies']}) == 1)
r = appel(gest, 'get', f'{PAGE}?etape=resultats')
verif('page Résultats', r.status_code == 200 and 'Écritures de fin de période contre-passées'.encode() in r.data)
r = appel(gest, 'get', f'{PAGE}/test/VTE_NUMEROTATION')
verif('détail : numéros manquants 412 à 414', r.status_code == 200 and b'412, 413, 414' in r.data)
r = appel(gest, 'get', f'{PAGE}/test/GL_ATTENTE')
verif('détail : compte d’attente 471100 et son ancienneté', r.status_code == 200 and b'471100' in r.data and b'jours)' in r.data)
r = appel(gest, 'get', f'{PAGE}/test/GL_BENFORD')
verif('Benford conforme : pas de page d’anomalies à examiner', r.status_code in (200, 404))

print('--- 4. Constat et export')
r = appel(gest, 'get', f'{PAGE}/test/VTE_CUT_OFF/constat')
verif('constat pré-rempli (séparation des exercices)', r.status_code == 200 and 'livraison effective'.encode() in r.data)
poster(gest, f'{PAGE}/test/VTE_CUT_OFF/constat', {'titre': 'Vente annulée après la clôture', 'gravite': 'majeure',
                                                  'fait': 'La facture FV-2025-0795 a été annulée par un avoir le 05/01/2026.'},
       page=f'{PAGE}/test/VTE_CUT_OFF/constat')
with A.app.app_context():
    c = M.Constatation.query.filter_by(audit_id=AID).order_by(M.Constatation.id.desc()).first()
    verif('constat rattaché au processus « ventes »', c is not None and c.processus_concerne == 'Ventes, facturation et encaissements', getattr(c, 'processus_concerne', None))
r = appel(gest, 'get', f'{PAGE}/export.xlsx')
from openpyxl import load_workbook
wb = load_workbook(io.BytesIO(r.data)) if r.status_code == 200 else None
verif('export : clôture indiquée, feuille par test', wb is not None and 'clôture retenue : 31/12/2025' in str(wb['Synthèse']['A3'].value)
      and any(n.startswith('Numérotation') for n in wb.sheetnames), wb.sheetnames[:3] if wb else r.status_code)
r = appel(gest, 'get', '/analyse-donnees/modele/grand_livre.xlsx')
wb = load_workbook(io.BytesIO(r.data)) if r.status_code == 200 else None
verif('modèle du grand livre : date et heure de saisie', wb is not None and 'Date et heure de saisie' in [x.value for x in wb['Grand livre (écritures)'][1]])

print(f'\n{sum(res)}/{len(res)} vérifications réussies')
raise SystemExit(0 if all(res) else 1)
