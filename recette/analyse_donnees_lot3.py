"""Recette : analyse des données, lot 3 — sources de données (connecteurs) et analyses programmées (audit continu).

Bases de données (SQLite à la place du serveur), SFTP, lien https, Microsoft 365, Google Drive, Odoo, Business Central,
Xero, QuickBooks et Zoho Books simulés (aucun appel réseau) ; sécurité (adresses internes, requêtes, secrets) ;
lecture dans une analyse ; analyse programmée : contrôle N2 (éléments en anomalie), KRI, notifications, nouvelles
anomalies seulement, relevé automatique, erreur ; cloisonnement."""
import io
import json
import os
import re
import sqlite3
import tempfile
from datetime import date, datetime, timedelta
from types import SimpleNamespace as NS

os.environ['EGALYX_COLLECTE_AUTO'] = '0'
import socle
from socle import Muet, appel
from cryptography.fernet import Fernet
os.environ['EGALYX_CLE_CHIFFREMENT'] = Fernet.generate_key().decode()
with Muet():
    A, ids = socle.preparer()
os.environ['EGALYX_DOSSIER_ANALYSES'] = tempfile.mkdtemp(prefix='recette_ad3_')
import models as M
from models import db
from egalyx import analyse_moteur as am, analyse_connecteurs as ac, analyse_sources as asrc
import donnees_achats_demo as dd

res = []


def verif(nom, cond, detail=''):
    res.append(bool(cond)); print('OK   ' if cond else 'ÉCHEC', nom, detail)


def jeton(c, url):
    t = appel(c, 'get', url).data.decode(errors='ignore')
    m = re.search(r'name="csrf_token" value="([^"]+)"', t) or re.search(r'name="csrf-token" content="([^"]+)"', t)
    return m.group(1) if m else ''


def poster(c, url, data=None, page=None):
    return appel(c, 'post', url, data={**(data or {}), 'csrf_token': jeton(c, page or url)})


# ---------------------------------------------------------------- base « client » : SQLite à la place du serveur
G = dd.generer()
BASE = os.path.join(tempfile.mkdtemp(), 'erp.db')
cx = sqlite3.connect(BASE)
for t, lignes in G.items():
    cols = list(lignes[0])
    cx.execute(f'CREATE TABLE egalyx_{t} (' + ', '.join(f'"{c}"' for c in cols) + ')')
    cx.executemany(f'INSERT INTO egalyx_{t} VALUES (' + ','.join('?' * len(cols)) + ')',
                   [[v.isoformat() if isinstance(v, date) else v for v in l.values()] for l in lignes])
cx.commit(); cx.close()
from sqlalchemy import create_engine
ORIGINE_SQL = ac.MOTEUR_SQL['fabrique']
ac.MOTEUR_SQL['fabrique'] = lambda code, p, s: create_engine('sqlite:///' + BASE)
REQ = {'fournisseurs': 'SELECT * FROM egalyx_fournisseurs', 'factures': 'SELECT * FROM egalyx_factures WHERE "Date facture" BETWEEN :debut AND :fin',
       'paiements': 'SELECT * FROM egalyx_paiements WHERE "Date paiement" BETWEEN :debut AND :fin'}

# ---------------------------------------------------------------- services en ligne simulés
APPELS = []


class Rep:
    def __init__(self, code=200, corps=None, binaire=None, entetes=None):
        self.status_code, self._c, self.headers = code, (binaire if binaire is not None else json.dumps(corps).encode()), entetes or {}

    def iter_content(self, n):
        yield self._c

    def json(self):
        return json.loads(self._c)


ROUTES = {}


def faux_request(methode, url, **kw):
    APPELS.append((methode, url, kw))
    for motif, f in ROUTES.items():
        if re.search(motif, url):
            return f(methode, url, kw)
    return Rep(404, {'message': 'inconnu'})


import requests
requests.request = faux_request
PAIEMENTS_ODOO = [{'id': 1, 'name': 'PBNK1/2026/001', 'partner_id': [7, 'SOCIETE A'], 'date': '2026-03-02', 'amount': 1500000.0,
                   'partner_bank_id': [3, 'CI001 0001 000123 - SOCIETE A'], 'write_uid': [2, 'S. Diallo'], 'reconciled_bill_ids': [11],
                   'journal_id': [4, 'Banque']}]


def odoo(m_, url, kw):
    p = kw['json']['params']
    if p['service'] == 'common':
        return Rep(200, {'result': 2 if p['args'][2] == 'cle-odoo' else False})
    modele, _meth, dom, opts = p['args'][3], p['args'][4], p['args'][5], p['args'][6]
    if opts.get('offset'):
        return Rep(200, {'result': []})
    if modele == 'account.payment':
        return Rep(200, {'result': PAIEMENTS_ODOO})
    if modele == 'account.move':
        return Rep(200, {'result': [{'id': 11, 'name': 'BILL/2026/011'}]})
    return Rep(200, {'result': [{'name': 'Ma société'}]})


ROUTES[r'erp\.odoo\.com/jsonrpc'] = odoo
ROUTES[r'login\.microsoftonline\.com/.+/token'] = lambda m_, u, kw: Rep(200, {'access_token': 'jeton-ms'})
ROUTES[r'api\.businesscentral\.dynamics\.com/.+/companies$'] = lambda m_, u, kw: Rep(200, {'value': [{'name': 'CRONUS', 'id': '1'}]})
ROUTES[r'api\.businesscentral\.dynamics\.com/.+/purchaseInvoices'] = lambda m_, u, kw: Rep(200, {'value': [
    {'number': 'PI-1', 'vendorNumber': 'V01', 'invoiceDate': '2026-02-10', 'totalAmountIncludingTax': 2360000}], '@odata.nextLink': None})
JETONS_XERO = {'n': 0}


def xero_jeton(m_, u, kw):
    JETONS_XERO['n'] += 1
    return Rep(200, {'access_token': 'acc', 'refresh_token': f'nouveau-refresh-{JETONS_XERO["n"]}'})


ROUTES[r'identity\.xero\.com/connect/token'] = xero_jeton
ROUTES[r'api\.xero\.com/api\.xro/2\.0/Invoices'] = lambda m_, u, kw: Rep(200, {'Invoices': [
    {'InvoiceNumber': 'INV-9', 'Contact': {'ContactID': 'c-1'}, 'Date': '/Date(1772668800000+0000)/', 'Total': 990000, 'Type': 'ACCPAY'}]})
ROUTES[r'oauth\.platform\.intuit\.com'] = lambda m_, u, kw: Rep(200, {'access_token': 'acc', 'refresh_token': 'qb-refresh-2'})
ROUTES[r'quickbooks\.api\.intuit\.com/v3/company/123/query'] = lambda m_, u, kw: Rep(200, {'QueryResponse': {'Bill': [
    {'Id': '5', 'DocNumber': 'B-5', 'VendorRef': {'value': '42'}, 'TxnDate': '2026-03-03', 'TotalAmt': 120000}]}})
ROUTES[r'accounts\.zoho\.eu/oauth'] = lambda m_, u, kw: Rep(200, {'access_token': 'acc'})
ROUTES[r'www\.zohoapis\.eu/books/v3/customerpayments'] = lambda m_, u, kw: Rep(200, {'customerpayments': [
    {'payment_number': 'CP-1', 'customer_id': '9', 'date': '2026-04-01', 'amount': 50000, 'invoice_numbers': 'INV-1'}],
    'page_context': {'has_more_page': False}})
CSV_SP = dd.en_csv(G['fournisseurs'])
ROUTES[r'graph\.microsoft\.com/v1\.0/sites/societe\.sharepoint\.com:/sites/Finance$'] = lambda m_, u, kw: Rep(200, {'id': 'site-1'})
ROUTES[r'graph\.microsoft\.com/v1\.0/sites/site-1/drive/root:/Audit/fournisseurs\.csv:/content'] = \
    lambda m_, u, kw: Rep(302, entetes={'Location': 'https://societe.sharepoint.com/_layouts/download?x=1'})
ROUTES[r'societe\.sharepoint\.com/_layouts/download'] = lambda m_, u, kw: Rep(200, binaire=CSV_SP)
ROUTES[r'graph\.microsoft\.com/v1\.0/sites/site-1/drive/root:/Audit/piege\.csv:/content'] = \
    lambda m_, u, kw: Rep(302, entetes={'Location': 'https://pirate.example.com/vol'})
ROUTES[r'oauth2\.googleapis\.com/token'] = lambda m_, u, kw: Rep(200, {'access_token': 'g'})
ROUTES[r'www\.googleapis\.com/drive/v3/files/1AbCdEfGhIjK/export'] = lambda m_, u, kw: Rep(200, binaire=dd.en_xlsx(G['commandes']))
ROUTES[r'www\.googleapis\.com/drive/v3/files/1AbCdEfGhIjK$'] = lambda m_, u, kw: (
    Rep(200, {'name': 'Commandes', 'mimeType': 'application/vnd.google-apps.spreadsheet'}))
ROUTES[r'exports\.societe\.example/paiements\.csv'] = lambda m_, u, kw: Rep(200, binaire=dd.en_csv(G['paiements']),
                                                                         entetes={'Content-Disposition': 'attachment; filename="paiements_2026.csv"'})
import egalyx.kri_sources_securite as KS
_hp = KS.hote_public
KS.hote_public = lambda h: not re.match(r'^(127\.|10\.|192\.168\.|localhost|interne)', h or '')

print('--- 1. Connecteurs (sans réseau)')
try:
    ORIGINE_SQL('postgresql', {'hote': '127.0.0.1', 'base': 'x', 'utilisateur': 'u'}, {})
    refuse = False
except ac.ErreurSource as e:
    refuse = 'interne' in str(e) or 'non installé' in str(e)
verif('base de données sur une adresse interne : refusée', refuse)
for q, attendu in (('DELETE FROM t', False), ('SELECT 1; DROP TABLE t', False), ('select replace(a, 1, 2) from t', True),
                   ('SELECT * INTO copie FROM t', False), ("SELECT 'update' AS x FROM t", True)):
    try:
        ac.verifier_requete(q); ok = True
    except ac.ErreurSource:
        ok = False
    verif(f'requête « {q[:30]} » : {"acceptée" if attendu else "refusée"}', ok == attendu)
ext = ac.extraire('postgresql', {'hote': 'db.societe.example', 'base': 'erp', 'utilisateur': 'lecture', 'extractions': {'paiements': {'requete': REQ['paiements']}}},
                  {'mot_de_passe': 'x'}, 'paiements', date(2026, 3, 1), date(2026, 3, 31))
verif('base : requête avec période (:debut, :fin)', ext.lignes and all('2026-03' in str(l[2]) for l in ext.lignes), len(ext.lignes or []))
ext = ac.extraire('odoo', {'url': 'https://erp.odoo.com', 'base': 'prod', 'utilisateur': 'audit@societe.ci'}, {'cle': 'cle-odoo'}, 'paiements')
verif('Odoo : paiements rangés dans les colonnes de l’outil (facture rapprochée, RIB)', ext.correspondance.get('montant') == 'Montant payé'
      and ext.lignes[0][ext.entetes.index('N° de facture payée')] == 'BILL/2026/011' and ext.lignes[0][ext.entetes.index('RIB / IBAN bénéficiaire')] == 'CI001 0001 000123')
try:
    ac.extraire('odoo', {'url': 'https://erp.odoo.com', 'base': 'prod', 'utilisateur': 'audit@societe.ci'}, {'cle': 'mauvaise'}, 'paiements'); ok = False
except ac.ErreurSource as e:
    ok = 'refusés' in str(e)
verif('Odoo : clé refusée, message clair', ok)
ext = ac.extraire('business_central', {'tenant': 'societe.onmicrosoft.com', 'client_id': 'app', 'environnement': 'production',
                                       'societe': '12345678-1234-1234-1234-123456789012'}, {'secret': 's'}, 'factures', date(2026, 1, 1), date(2026, 6, 30))
verif('Business Central : factures, filtre de période envoyé', ext.lignes[0][0] == 'PI-1'
      and 'invoiceDate ge 2026-01-01' in str([c[2].get('params') for c in APPELS if 'purchaseInvoices' in c[1]][-1]))
ext = ac.extraire('xero', {'client_id': 'x', 'organisation': 't-1'}, {'secret': 's', 'refresh_token': 'ancien'}, 'factures')
verif('Xero : jeton de renouvellement remplacé (à réenregistrer), date /Date()/ lue', ext.secrets_a_jour.get('refresh_token', '').startswith('nouveau-refresh')
      and str(ext.lignes[0][2]) == '2026-03-05', ext.lignes[0] if ext.lignes else None)
ext = ac.extraire('quickbooks', {'client_id': 'q', 'societe': '123'}, {'secret': 's', 'refresh_token': 'r'}, 'factures')
verif('QuickBooks : factures (Bill)', ext.lignes[0][0] == 'B-5')
ext = ac.extraire('zoho_books', {'client_id': 'z', 'organisation': '77', 'centre': 'eu'}, {'secret': 's', 'refresh_token': 'r'}, 'encaissements')
verif('Zoho Books : encaissements', ext.lignes[0][0] == 'CP-1')
ext = ac.extraire('m365', {'tenant': 'societe.onmicrosoft.com', 'client_id': 'app', 'site': 'https://societe.sharepoint.com/sites/Finance',
                           'extractions': {'fournisseurs': {'chemin': 'Audit/fournisseurs.csv'}}}, {'secret': 's'}, 'fournisseurs')
verif('SharePoint : fichier téléchargé (redirection vers sharepoint.com acceptée)', ext.octets == CSV_SP)
try:
    ac.extraire('m365', {'tenant': 'societe.onmicrosoft.com', 'client_id': 'app', 'site': 'https://societe.sharepoint.com/sites/Finance',
                         'extractions': {'fournisseurs': {'chemin': 'Audit/piege.csv'}}}, {'secret': 's'}, 'fournisseurs'); ok = False
except ac.ErreurSource:
    ok = True
verif('SharePoint : redirection vers un autre domaine refusée', ok)
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
cle = rsa.generate_private_key(public_exponent=65537, key_size=2048).private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                                                                   serialization.NoEncryption()).decode()
ext = ac.extraire('google_drive', {'extractions': {'commandes': {'fichier': 'https://docs.google.com/spreadsheets/d/1AbCdEfGhIjK/edit'}}},
                  {'compte_service': json.dumps({'client_email': 'audit@projet.iam.gserviceaccount.com', 'private_key': cle})}, 'commandes')
verif('Google Drive : Google Sheet exportée en Excel (jeton signé RS256)', ext.nom == 'Commandes.xlsx' and ext.octets[:2] == b'PK')
ext = ac.extraire('https', {'extractions': {'paiements': {'url': 'https://exports.societe.example/paiements.csv'}}}, {'jeton': 'abc'}, 'paiements')
verif('lien https : fichier lu, nom repris de l’en-tête, jeton envoyé', ext.nom == 'paiements_2026.csv'
      and [c for c in APPELS if 'exports.societe' in c[1]][-1][2]['headers'].get('Authorization') == 'Bearer abc')
try:
    ac.extraire('https', {'extractions': {'paiements': {'url': 'https://interne.societe/x.csv'}}}, {}, 'paiements'); ok = False
except ac.ErreurSource:
    ok = True
verif('lien https vers une adresse interne : refusé', ok)


class FauxSFTP:
    def listdir(self, d):
        return ['a']

    def listdir_attr(self, d):
        return [NS(filename='paiements_2026-05.csv', st_mtime=1), NS(filename='paiements_2026-06.csv', st_mtime=2), NS(filename='autre.txt', st_mtime=3)]

    def stat(self, c):
        return NS(st_size=1000)

    def open(self, c, mode):
        FauxSFTP.lu = c
        return io.BytesIO(dd.en_csv(G['paiements']))


ac.SFTP['client'] = lambda p, s: (FauxSFTP(), 'SHA256:abc', NS(close=lambda: None))
ext = ac.extraire('sftp', {'hote': 'sftp.societe.example', 'extractions': {'paiements': {'chemin': '/depot/paiements_*.csv'}}}, {'mot_de_passe': 'x'}, 'paiements')
verif('SFTP : le fichier le plus récent qui correspond au motif', FauxSFTP.lu == '/depot/paiements_2026-06.csv' and ext.secrets_a_jour.get('_empreinte_hote'))

print('--- 2. Sources : droits, secrets')
sa, admin, gest, lect, admin_b = (socle.navigateur(A, ids[r]) for r in ('superadmin', 'admin_a', 'gestionnaire', 'lecteur', 'admin_b'))
with A.app.app_context():
    db.session.get(M.Client, 1).modules_actifs = {'audit': True, 'analyse_donnees': True, 'controle_n2': True, 'kri': True}
    db.session.get(M.Client, 2).modules_actifs = {'audit': True, 'analyse_donnees': True}
    ref = socle.creer(M.ReferentielControle, code_controle='N2-ACH-01', nom='Contrôle des paiements fournisseurs', client_id=1)
    kri = socle.creer(M.KRI, nom='Paiements en double (nombre)', client_id=1)
    audit = socle.creer(M.Audit, reference='AUD-SRC', titre='Audit des achats', type_audit='interne', client_id=1, statut='en_cours',
                        responsable_id=ids['gestionnaire'])
    db.session.commit()
    REF, KRI_ID, AID = ref.id, kri.id, audit.id
verif('sources : page réservée aux administrateurs', appel(admin, 'get', '/analyse-donnees/sources').status_code == 200
      and appel(gest, 'get', '/analyse-donnees/sources').status_code == 403)
data = {'nom': 'ERP (base)', 'connecteur': 'postgresql', 'f_hote': 'db.societe.example', 'f_port': '5432', 'f_base': 'erp', 'f_utilisateur': 'lecture',
        'f_mot_de_passe': 'MotDePasseTresSecret', 'x_fournisseurs': REQ['fournisseurs'], 'x_factures': REQ['factures'], 'x_paiements': REQ['paiements'],
        'action': 'enregistrer'}
poster(admin, '/analyse-donnees/sources/nouvelle', data, page='/analyse-donnees/sources/nouvelle?connecteur=postgresql')
with A.app.app_context():
    s = M.SourceAnalyse.query.filter_by(client_id=1, nom='ERP (base)').first()
    SID = s.id if s else 0
    verif('source enregistrée, mot de passe chiffré en base', s is not None and 'MotDePasseTresSecret' not in json.dumps(s.secrets)
          and asrc.secrets_de(s).get('mot_de_passe') == 'MotDePasseTresSecret')
r = appel(admin, 'get', f'/analyse-donnees/sources/{SID}/modifier')
verif('formulaire : le mot de passe n’est jamais réaffiché', r.status_code == 200 and b'MotDePasseTresSecret' not in r.data and 'enregistré'.encode() in r.data)
r = poster(admin, '/analyse-donnees/sources/nouvelle', dict(data, nom='Piège', x_paiements='DELETE FROM egalyx_paiements'),
           page='/analyse-donnees/sources/nouvelle?connecteur=postgresql')
with A.app.app_context():
    verif('requête d’écriture refusée à l’enregistrement', M.SourceAnalyse.query.filter_by(nom='Piège').count() == 0)
poster(admin, f'/analyse-donnees/sources/{SID}/tester', page='/analyse-donnees/sources')
with A.app.app_context():
    verif('tester la connexion', db.session.get(M.SourceAnalyse, SID).dernier_test_ok is True)
verif('autre organisation : source introuvable', appel(admin_b, 'get', f'/analyse-donnees/sources/{SID}/modifier').status_code == 404)
poster(admin, '/analyse-donnees/sources/nouvelle', {'nom': 'Xero', 'connecteur': 'xero', 'f_client_id': 'x', 'f_secret': 's', 'f_refresh_token': 'ancien',
                                                    'f_organisation': 't-1', 'action': 'enregistrer'}, page='/analyse-donnees/sources/nouvelle?connecteur=xero')

print('--- 3. Lecture dans une analyse de mission')
poster(gest, f'/analyse-donnees/audit/{AID}/nouvelle', {'titre': 'Achats S1'}, page=f'/analyse-donnees/audit/{AID}')
with A.app.app_context():
    ANID = M.AnalyseDonnees.query.filter_by(audit_id=AID).first().id
    XID = M.SourceAnalyse.query.filter_by(nom='Xero').first().id
r = appel(gest, 'get', f'/analyse-donnees/{ANID}?etape=donnees')
verif('carte « Lire depuis une source »', b'Lire depuis une source' in r.data and b'ERP (base)' in r.data)
r = poster(gest, f'/analyse-donnees/{ANID}/jeu/paiements/source', {'source_id': SID, 'debut': '2026-01-01', 'fin': '2026-06-30'}, page=f'/analyse-donnees/{ANID}')
with A.app.app_context():
    j = M.JeuDonneesAnalyse.query.filter_by(analyse_id=ANID, type_jeu='paiements').first()
    dans = sum(1 for x in G['paiements'] if date(2026, 1, 1) <= x['Date paiement'] <= date(2026, 6, 30))
    verif('paiements de la période lus dans la base : fichier tracé (source, période, empreinte)', j is not None and j.nb_lignes == dans
          and j.qualite['infos']['origine']['source'] == 'ERP (base)' and len(j.empreinte) == 64, getattr(j, 'nb_lignes', None))
    corr = dict(j.correspondance)
appel(gest, 'post', f'/analyse-donnees/{ANID}/jeu/paiements/colonnes',
      data={'csrf_token': jeton(gest, f'/analyse-donnees/{ANID}/jeu/paiements/colonnes')} | {f'c_{k}': v for k, v in corr.items()})
with A.app.app_context():
    verif('… colonnes reconnues, prêt pour les tests', db.session.get(M.JeuDonneesAnalyse, j.id).statut == 'pret')
poster(gest, f'/analyse-donnees/{ANID}/jeu/factures/source', {'source_id': XID}, page=f'/analyse-donnees/{ANID}')
with A.app.app_context():
    x = db.session.get(M.SourceAnalyse, XID)
    j = M.JeuDonneesAnalyse.query.filter_by(analyse_id=ANID, type_jeu='factures').first()
    verif('Xero : factures lues, correspondance exacte, nouveau jeton enregistré (chiffré)', j is not None and j.correspondance.get('numero') == 'N° de facture'
          and asrc.secrets_de(x).get('refresh_token', '').startswith('nouveau-refresh'))
verif('autre organisation : lecture refusée', poster(admin_b, f'/analyse-donnees/{ANID}/jeu/paiements/source', {'source_id': SID}, page='/dashboard').status_code == 404)

print('--- 4. Analyse programmée (audit continu)')
ac_periode = ac.periode
ac.periode = lambda code, j=None: (date(2026, 1, 1), date(2026, 6, 30))
verif('analyses programmées : ouvertes au gestionnaire de l’audit, pas au lecteur', appel(gest, 'get', '/analyse-donnees/programmes').status_code == 200
      and appel(lect, 'get', '/analyse-donnees/programmes').status_code == 403)
codes_achats = [t['code'] for t in am.TESTS if t['domaine'] not in ('Comptabilité', 'Ventes et encaissements')]
form = {'nom': 'Paiements fournisseurs — mensuel', 'source_id': SID, 'jeux': ['fournisseurs', 'factures', 'paiements'], 'periode': 'annee_en_cours',
        'frequence': 'mensuelle', 'responsable_id': ids['gestionnaire'], 'actif': '1', 'referentiel_id': REF, 'controleur_id': ids['gestionnaire'],
        'kri_0': KRI_ID, 'kri_test_0': 'PAI_DOUBLON', 'kri_mesure_0': 'nb'} | {f't_{c}': '1' for c in codes_achats}
appel(gest, 'post', '/analyse-donnees/programmes/nouveau', data=dict(form, csrf_token=jeton(gest, '/analyse-donnees/programmes/nouveau')))
with A.app.app_context():
    p = M.AnalyseProgrammee.query.filter_by(client_id=1).first()
    PID = p.id if p else 0
    verif('analyse programmée enregistrée (prochaine exécution la nuit)', p is not None and p.prochaine_execution and p.prochaine_execution.hour == 2
          and p.kri_liens == [{'kri_id': KRI_ID, 'test': 'PAI_DOUBLON', 'mesure': 'nb'}])
poster(gest, f'/analyse-donnees/programmes/{PID}/executer', page=f'/analyse-donnees/programmes/{PID}')
with A.app.app_context():
    ex = M.ExecutionAnalyseProgrammee.query.filter_by(programme_id=PID).order_by(M.ExecutionAnalyseProgrammee.id.desc()).first()
    verif('exécution : données lues, tests lancés, nouvelles anomalies', ex is not None and ex.statut == 'ok' and ex.nouvelles > 0
          and all(len(x['empreinte']) == 64 for x in ex.jeux), getattr(ex, 'message', None))
    pl = db.session.get(M.PlanificationControle, ex.suites['n2']['planification_id']) if ex and ex.suites.get('n2') else None
    els = M.ElementEchantillonN2.query.filter_by(execution_id=pl.execution_id).all() if pl else []
    verif('contrôle N2 : planification de la période, éléments « en anomalie » à examiner', pl is not None and pl.referentiel_id == REF
          and pl.statut == 'en_cours' and els and all(e.resultat == 'anomalie' for e in els) and len(els) == ex.suites['n2']['elements'], len(els))
    verif('… anomalies détectées créées (même circuit qu’un contrôle manuel)', M.AnomalieDetectee.query.filter_by(execution_id=pl.execution_id).count() == len(els))
    verif('… doublon VIR-0300 présent avec sa criticité', any(e.reference.startswith('VIR-0300') and e.criticite == 'majeur' for e in els))
    mes = M.MesureKRI.query.filter_by(kri_id=KRI_ID).all()
    verif('KRI : mesure créée (nombre de paiements en double)', len(mes) == 1 and mes[0].valeur == ex.resultats['PAI_DOUBLON']['nb'], [x.valeur for x in mes])
    notif = M.Notification.query.filter_by(destinataire_id=ids['gestionnaire'], entite_type='analyse_programmee').count()
    verif('responsable prévenu', notif >= 1)
    N1 = len(els)
poster(gest, f'/analyse-donnees/programmes/{PID}/executer', page=f'/analyse-donnees/programmes/{PID}')
with A.app.app_context():
    ex2 = M.ExecutionAnalyseProgrammee.query.filter_by(programme_id=PID).order_by(M.ExecutionAnalyseProgrammee.id.desc()).first()
    pl = db.session.get(M.PlanificationControle, ex.suites['n2']['planification_id'])
    verif('2e exécution sur les mêmes données : aucune nouvelle anomalie, rien d’ajouté au N2', ex2.statut == 'ok' and ex2.nouvelles == 0
          and M.ElementEchantillonN2.query.filter_by(execution_id=pl.execution_id).count() == N1)
    verif('… mais le KRI reçoit sa mesure à chaque exécution', M.MesureKRI.query.filter_by(kri_id=KRI_ID).count() == 2)
r = appel(gest, 'get', f'/analyse-donnees/programmes/{PID}')
verif('page de l’analyse programmée : historique et résultats', r.status_code == 200 and 'Historique des exécutions'.encode() in r.data and b'VIR-0300' in r.data)
with A.app.app_context():
    p = db.session.get(M.AnalyseProgrammee, PID); p.prochaine_execution = datetime.utcnow() - timedelta(minutes=5); db.session.commit()
    n = asrc.relever_programmes(A.app)
    p = db.session.get(M.AnalyseProgrammee, PID)
    verif('relevé automatique : analyse échue exécutée, prochaine échéance dans un mois', n == 1 and p.prochaine_execution > datetime.utcnow() + timedelta(days=25)
          and M.ExecutionAnalyseProgrammee.query.filter_by(programme_id=PID, declenchement='automatique').count() == 1)
    verif('… et pas deux fois (réservation)', asrc.relever_programmes(A.app) == 0)
    s = db.session.get(M.SourceAnalyse, SID); s.parametres = dict(s.parametres, extractions=dict(s.parametres['extractions'], paiements={'requete': 'SELECT * FROM table_absente'}))
    db.session.commit()
poster(gest, f'/analyse-donnees/programmes/{PID}/executer', page=f'/analyse-donnees/programmes/{PID}')
with A.app.app_context():
    ex3 = M.ExecutionAnalyseProgrammee.query.filter_by(programme_id=PID).order_by(M.ExecutionAnalyseProgrammee.id.desc()).first()
    verif('erreur de lecture : exécution « erreur » avec un message clair, responsable prévenu', ex3.statut == 'erreur' and 'requête refusée' in (ex3.message or '')
          and M.Notification.query.filter(M.Notification.titre.like('%erreur%'), M.Notification.destinataire_id == ids['gestionnaire']).count() >= 1, ex3.message)
verif('autre organisation : analyse programmée introuvable', appel(admin_b, 'get', f'/analyse-donnees/programmes/{PID}').status_code == 404)
r = appel(gest, 'get', '/dashboard')
verif('menu : entrée « Audit continu »', b'/analyse-donnees/programmes' in r.data)
ac.periode = ac_periode
KS.hote_public = _hp

print(f'\n{sum(res)}/{len(res)} vérifications réussies')
raise SystemExit(0 if all(res) else 1)
