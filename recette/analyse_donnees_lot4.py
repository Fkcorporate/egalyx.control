"""Recette : analyse des données, lot 4 — paie, habilitations informatiques, crédit, LCB-FT, détection statistique.

Import des fichiers du personnel, de la paie, des comptes utilisateurs, des clients (KYC), des crédits et des opérations ;
23 tests sur un jeu fictif aux anomalies connues ; pages, constat rattaché au bon processus, export."""
import csv
import io
import os
import re
import tempfile
from datetime import date

os.environ['EGALYX_COLLECTE_AUTO'] = '0'
import socle
from socle import Muet, appel
from cryptography.fernet import Fernet
os.environ['EGALYX_CLE_CHIFFREMENT'] = Fernet.generate_key().decode()
with Muet():
    A, ids = socle.preparer()
os.environ['EGALYX_DOSSIER_ANALYSES'] = tempfile.mkdtemp(prefix='recette_ad4_')
import models as M
from models import db
from egalyx import analyse_moteur as am
import donnees_paie_banque_demo as dd

res = []


def verif(nom, cond, detail=''):
    res.append(bool(cond)); print('OK   ' if cond else 'ÉCHEC', nom, detail)


def jeton(c, url):
    t = appel(c, 'get', url).data.decode(errors='ignore')
    m = re.search(r'name="csrf_token" value="([^"]+)"', t) or re.search(r'name="csrf-token" content="([^"]+)"', t)
    return m.group(1) if m else ''


def poster(c, url, data=None, page=None):
    return appel(c, 'post', url, data={**(data or {}), 'csrf_token': jeton(c, page or url)})


def en_csv(lignes):
    out = io.StringIO()
    w = csv.writer(out, delimiter=';')
    w.writerow(list(lignes[0]))
    for l in lignes:
        w.writerow([x.strftime('%d/%m/%Y') if isinstance(x, date) else '' if x is None else
                    (f'{x:,.0f}'.replace(',', ' ') if isinstance(x, (int, float)) else x) for x in l.values()])
    return out.getvalue().encode('cp1252', errors='replace')


gest, admin_b = socle.navigateur(A, ids['gestionnaire']), socle.navigateur(A, ids['admin_b'])
with A.app.app_context():
    db.session.get(M.Client, 1).modules_actifs = {'audit': True, 'analyse_donnees': True}
    a = socle.creer(M.Audit, reference='AUD-BQ', titre='Audit LCB-FT et crédit', type_audit='interne', client_id=1, statut='en_cours',
                    responsable_id=ids['gestionnaire'])
    db.session.commit()
    AID = a.id
poster(gest, f'/analyse-donnees/audit/{AID}/nouvelle', {'titre': 'Banque S1 2026'}, page=f'/analyse-donnees/audit/{AID}')
with A.app.app_context():
    ANID = M.AnalyseDonnees.query.filter_by(audit_id=AID).first().id
PAGE = f'/analyse-donnees/{ANID}'
G = dd.generer()

print('--- 0. Moteur')
verif('63 tests, 23 nouveaux (paie, habilitations, crédit, LCB-FT, statistique)', len(am.TESTS) == 63
      and sum(1 for t in am.TESTS if t['domaine'] in ('Paie', 'Habilitations informatiques', 'Crédit', 'LCB-FT', 'Analyse statistique')) == 23)
verif('correspondance sans les petits mots (« Expiration de la pièce » = « expiration pièce »)',
      am.proposer_correspondance('clients', ['Code client', 'Nom', 'Expiration de la pièce', 'Date de la dernière revue']).get('expiration_piece') == 'Expiration de la pièce')

print('--- 1. Import')
for t, lignes in G.items():
    r = appel(gest, 'post', f'{PAGE}/jeu/{t}/importer', data={'csrf_token': jeton(gest, PAGE), 'fichier': (io.BytesIO(en_csv(lignes)), f'{t}.csv')},
              content_type='multipart/form-data')
    with A.app.app_context():
        j = M.JeuDonneesAnalyse.query.filter_by(analyse_id=ANID, type_jeu=t).order_by(M.JeuDonneesAnalyse.id.desc()).first()
        corr = dict(j.correspondance or {})
    appel(gest, 'post', f'{PAGE}/jeu/{t}/colonnes', data={'csrf_token': jeton(gest, f'{PAGE}/jeu/{t}/colonnes')} | {f'c_{k}': v for k, v in corr.items()})
    with A.app.app_context():
        j = db.session.get(M.JeuDonneesAnalyse, j.id)
        verif(f'{t} : prêt ({j.nb_lignes} lignes), aucune valeur illisible', j.statut == 'pret' and j.nb_lignes == len(lignes)
              and all(c['erreurs'] == 0 for c in j.qualite['champs']), corr)
r = appel(gest, 'get', f'{PAGE}?etape=donnees')
verif('page Données : cycles « Personnel, paie et habilitations » et « Banque et microfinance »', 'Banque et microfinance'.encode() in r.data
      and 'Personnel, paie et habilitations'.encode() in r.data and r.data.count(b'class="ad-cycle"') == len(am.CYCLES))

print('--- 2. Tests')
codes = [t['code'] for t in am.TESTS if t['domaine'] in ('Paie', 'Habilitations informatiques', 'Crédit', 'LCB-FT', 'Analyse statistique')]
r = appel(gest, 'get', f'{PAGE}?etape=tests')
verif('les 23 nouveaux tests sont applicables', r.data.count(b'data-applicable="1"') >= 23, r.data.count(b'data-applicable="1"'))
poster(gest, f'{PAGE}/executer', {f't_{c}': '1' for c in codes} | {'cloture': '30/06/2026',
       'p_CRD_DELEGATION_plafonds': 'Chef d’agence Plateau = 25 000 000\nComité de crédit = 1 000 000 000'}, page=f'{PAGE}?etape=tests')
with A.app.app_context():
    R = db.session.get(M.AnalyseDonnees, ANID).resultats or {}
    for code, refs in dd.ATTENDU.items():
        x = R.get(code) or {'anomalies': [], 'nb': 0}
        trouve = {a['ref'] for a in x['anomalies']} | {a['tiers'].split(' — ')[0] for a in x['anomalies']}
        verif(f'{code} : anomalies plantées retrouvées ({x["nb"]} ligne(s))', refs <= trouve, refs - trouve)
    verif('compte désactivé jamais signalé', not any(a['ref'] == 'ancien' for c in codes for a in R[c]['anomalies']))
for code in ('SI_DEPARTS', 'LCB_TRANSIT', 'KYC_INCOMPLET', 'STAT_MONTANTS', 'PAIE_RIB_PARTAGE'):
    r = appel(gest, 'get', f'{PAGE}/test/{code}')
    verif(f'détail {code}', r.status_code == 200 and 'Anomalies à examiner'.encode() in r.data, r.status_code)
r = appel(gest, 'get', f'{PAGE}/test/LCB_FRACTIONNEMENT/constat')
verif('constat LCB-FT pré-rempli (CENTIF)', r.status_code == 200 and b'CENTIF' in r.data)
poster(gest, f'{PAGE}/test/LCB_FRACTIONNEMENT/constat', {'titre': 'Dépôts fractionnés', 'gravite': 'majeure', 'fait': 'Trois dépôts en espèces juste sous le seuil.'},
       page=f'{PAGE}/test/LCB_FRACTIONNEMENT/constat')
with A.app.app_context():
    c = M.Constatation.query.filter_by(audit_id=AID).order_by(M.Constatation.id.desc()).first()
    verif('constat rattaché à « Conformité LCB-FT »', c is not None and c.processus_concerne == 'Conformité LCB-FT')
r = appel(gest, 'get', f'{PAGE}/export.xlsx')
verif('export Excel', r.status_code == 200 and r.data[:2] == b'PK')
verif('autre organisation : introuvable', appel(admin_b, 'get', f'{PAGE}/test/SI_DEPARTS').status_code == 404)

print(f'\n{sum(res)}/{len(res)} vérifications réussies')
raise SystemExit(0 if all(res) else 1)
