"""Recette : analyse des données d'audit (lot 1 : achats, fournisseurs, paiements).

Module sur activation, droits et cloisonnement ; import Excel / CSV, correspondance des colonnes, contrôle de qualité,
empreinte, chiffrement ; 21 tests achats (lot 1) sur un jeu fictif aux anomalies connues ; résultats, export Excel, feuille de travail,
échantillon reproductible, constat ; IA (faux fournisseur) sans données brutes ; dossier figé ; conservation échue."""
import hashlib
import io
import json
import os
import re
from datetime import datetime, timedelta
from types import SimpleNamespace as NS

os.environ['EGALYX_COLLECTE_AUTO'] = '0'
os.environ['MISTRAL_API_KEY'] = 'mistral-recette-' + 'y' * 30
import socle
from socle import Muet, appel
os.environ['OPENAI_API_KEY'] = 'sk-recette' + 'x' * 40
from cryptography.fernet import Fernet
os.environ['EGALYX_CLE_CHIFFREMENT'] = Fernet.generate_key().decode()
with Muet():
    A, ids = socle.preparer()
import tempfile
os.environ['EGALYX_DOSSIER_ANALYSES'] = tempfile.mkdtemp(prefix='recette_ad_')
import models as M
from models import db
from egalyx import ia_passerelle as P, ia as IA
from egalyx import analyse_moteur as am
import donnees_achats_demo as dd

res = []


def verif(nom, cond, detail=''):
    res.append(bool(cond)); print('OK   ' if cond else 'ÉCHEC', nom, detail)


APPELS, REPONSE = [], {'contenu': '{}'}


def faux(completions, *a, **kw):
    APPELS.append(json.dumps(kw.get('messages'), ensure_ascii=False))
    return NS(choices=[NS(message=NS(content=REPONSE['contenu'], tool_calls=None))])


P.installer()
P._etat['origine'] = faux


def jeton(c, url):
    r = appel(c, 'get', url)
    t = r.data.decode(errors='ignore')
    m = re.search(r'name="csrf_token" value="([^"]+)"', t) or re.search(r'name="csrf-token" content="([^"]+)"', t)
    return m.group(1) if m else ''


def poster(c, url, data=None, page=None, **kw):
    return appel(c, 'post', url, data={**(data or {}), 'csrf_token': jeton(c, page or url)}, **kw)


def ajax(c, url, page, **kw):
    return appel(c, 'post', url, headers={'X-CSRFToken': jeton(c, page), 'Accept': 'application/json'}, **kw)


sa, admin, gest, lect, admin_b = (socle.navigateur(A, ids[r]) for r in ('superadmin', 'admin_a', 'gestionnaire', 'lecteur', 'admin_b'))
with A.app.app_context():
    IA.ecrire_reglage('ia_active', True); IA.ecrire_reglage('ia_fournisseur', 'mistral'); IA.ecrire_reglage('ia_masquage', True)
    IA.ecrire_reglage('ia_fonctions', {})
    a = socle.creer(M.Audit, reference='AUD-AD', titre='Audit du cycle achats', type_audit='interne', client_id=1, statut='en_cours',
                    responsable_id=ids['gestionnaire'])
    g = db.session.get(M.User, ids['gestionnaire']); g.permissions = {**(g.permissions or {}), 'can_use_ia_analysis': True}
    db.session.commit()
    AID = a.id
BASE = '/analyse-donnees'

print('--- 0. Moteur : lecture des montants et des dates')
verif('montant « 1 250 000 FCFA »', am.lire_montant('1 250 000 FCFA') == 1250000.0)
verif('montant « 1.250.000 » (milliers)', am.lire_montant('1.250.000') == 1250000.0)
verif('montant « 1 234,56 » (virgule décimale)', am.lire_montant('1 234,56', ',') == 1234.56)
verif('montant « (5 000) » négatif', am.lire_montant('(5 000)') == -5000.0)
verif('montant « abc » signalé, jamais deviné', am.lire_montant('abc') == 'ERREUR')
verif('séparateur de colonne détecté (virgule décimale)', am.separateur_decimal(['1 200,50', '300', '12,5']) == ',')
verif('date « 05/03/2026 » lue jour/mois', am.lire_date('05/03/2026').isoformat() == '2026-03-05')
verif('date Excel (numéro de série 46086)', am.lire_date(46086).isoformat() == '2026-03-05')
verif('date « 31/02/2026 » signalée', am.lire_date('31/02/2026') == 'ERREUR')
verif('identifiants rapprochés (« F-001 » = « f001 »)', am.norm_id('F-001') == am.norm_id(' f001 '))

print('--- 1. Module fermé tant que le super admin ne l’a pas activé')
r = appel(admin, 'get', f'{BASE}/audit/{AID}')
verif('administrateur : page introuvable avant activation', r.status_code == 404, r.status_code)
r = appel(admin, 'get', f'/audit/{AID}')
verif('fiche de l’audit : pas de bouton « Analyse de données »', r.status_code == 200 and b'/analyse-donnees/audit/' not in r.data, r.status_code)
r = appel(sa, 'get', '/super-admin/client/1/modules')
verif('page Modules : case « Analyse de données » sur activation', r.status_code == 200 and re.search(rb'value="analyse_donnees"\s*>', r.data))
r = poster(sa, '/super-admin/client/1/modules', {'action': 'enregistrer', 'modules': ['cartographie', 'audit', 'ia', 'analyse_donnees']},
           page='/super-admin/client/1/modules')
verif('super admin : module activé pour le client', r.status_code in (302, 303), r.status_code)
r = appel(admin, 'get', f'/audit/{AID}')
verif('fiche de l’audit : bouton « Analyse de données »', b'/analyse-donnees/audit/' in r.data)
r = appel(gest, 'get', f'{BASE}/audit/{AID}')
verif('chef de mission (gestion de l’audit) : page ouverte', r.status_code == 200 and b'Nouvelle analyse' in r.data, r.status_code)
verif('lecteur (hors équipe, sans permission) : refusé', appel(lect, 'get', f'{BASE}/audit/{AID}').status_code in (403, 404))
verif('autre organisation : introuvable', appel(admin_b, 'get', f'{BASE}/audit/{AID}').status_code == 404)

r = appel(gest, 'get', '/dashboard')
verif('menu Audit Interne : entrée « Analyse de données »', b'href="/analyse-donnees/"' in r.data)
r = appel(admin, 'get', '/dashboard')
verif('menu Administration : « Sources de données » (administrateur)', b'href="/analyse-donnees/sources"' in r.data)
r = appel(gest, 'get', '/analyse-donnees/')
verif('page « Analyse de données » : missions proposées à la création', r.status_code == 200 and b'AUD-AD' in r.data)
verif('lecteur sans droit : page refusée', appel(lect, 'get', '/analyse-donnees/').status_code == 404)

print('--- 2. Création et modèles de fichiers')
r = poster(gest, f'{BASE}/audit/{AID}/nouvelle', {'titre': 'Cycle achats S1 2026'}, page=f'{BASE}/audit/{AID}')
with A.app.app_context():
    an = M.AnalyseDonnees.query.filter_by(audit_id=AID).first()
    ANID = an.id if an else 0
    verif(f'analyse créée (référence AD-, devise, {len(am.TESTS)} tests cochés)', an is not None and an.reference.startswith('AD-')
          and len(an.tests_choisis) == len(am.TESTS), getattr(an, 'reference', ''))
PAGE = f'{BASE}/{ANID}'
r = appel(gest, 'get', '/analyse-donnees/')
verif('page « Analyse de données » : l’analyse y figure avec sa mission', r.status_code == 200 and b'Cycle achats S1 2026' in r.data)
r = appel(gest, 'get', PAGE)
verif('page de l’analyse : étape Données, un emplacement par type de fichier, rangés par cycle', r.status_code == 200
      and len(re.findall(rb'class="ad-jeu[ "]', r.data)) == len(am.ORDRE_JEUX) and r.data.count(b'class="ad-cycle"') == len(am.CYCLES) and b'aria-current="step"' in r.data)
r = appel(gest, 'get', f'{BASE}/modele/tous.xlsx')
from openpyxl import load_workbook
wb = load_workbook(io.BytesIO(r.data)) if r.status_code == 200 else None
verif('modèles de fichiers : un classeur, une feuille par type + mode d’emploi', wb is not None and len(wb.sheetnames) == len(am.ORDRE_JEUX) + 1
      and wb['Fournisseurs']['A1'].value == 'Code fournisseur *', wb.sheetnames if wb else r.status_code)

print('--- 3. Import, correspondance, qualité, empreinte, chiffrement')
G = dd.generer()
FICHIERS = {t: ((dd.en_xlsx(l), f'{t}.xlsx') if t in ('fournisseurs', 'commandes') else (dd.en_csv(l), f'{t}.csv')) for t, l in G.items()}


def importer(c, t, octets, nom, **extra):
    return appel(c, 'post', f'{PAGE}/jeu/{t}/importer', data={'csrf_token': jeton(c, PAGE), 'fichier': (io.BytesIO(octets), nom), **extra},
                 content_type='multipart/form-data')


r = importer(gest, 'factures', b'xx', 'vieux.xls')
verif('ancien format .xls : refusé avec explication', r.status_code in (302, 303) and b'.xlsx' in appel(gest, 'get', PAGE).data)
r = importer(gest, 'factures', b'', 'vide.csv')
with A.app.app_context():
    verif('fichier vide : rien n’est importé', M.JeuDonneesAnalyse.query.filter_by(analyse_id=ANID).count() == 0)
for t in FICHIERS:
    octets, nom = FICHIERS[t]
    r = importer(gest, t, octets, nom)
    ok = r.status_code in (302, 303) and f'/jeu/{t}/colonnes' in (r.location or '')
    p = appel(gest, 'get', f'{PAGE}/jeu/{t}/colonnes')
    sel = len(re.findall(rb'<option value="[^"]+" selected', p.data))
    verif(f'{t} : importé, colonnes proposées ({sel})', ok and p.status_code == 200 and sel >= len([c for c in am.champs(t) if c[2]]), r.status_code)
    with A.app.app_context():
        j = M.JeuDonneesAnalyse.query.filter_by(analyse_id=ANID, type_jeu=t).order_by(M.JeuDonneesAnalyse.id.desc()).first()
        data = {'csrf_token': jeton(gest, f'{PAGE}/jeu/{t}/colonnes')} | {f'c_{k}': v for k, v in j.correspondance.items()}
    r = appel(gest, 'post', f'{PAGE}/jeu/{t}/colonnes', data=data)
    with A.app.app_context():
        j = db.session.get(M.JeuDonneesAnalyse, j.id)
        brut = open(j.chemin_brut, 'rb').read()
        verif(f'{t} : prêt, {j.nb_lignes} lignes, empreinte = SHA-256 du fichier, contenu chiffré sur le disque',
              j.statut == 'pret' and j.nb_lignes == len(G[t]) and j.empreinte == hashlib.sha256(octets).hexdigest()
              and brut.startswith(b'EGXAD1') and b'FOURNISSEUR' not in brut and j.chiffre, (j.statut, j.nb_lignes))
with A.app.app_context():
    j = M.JeuDonneesAnalyse.query.filter_by(analyse_id=ANID, type_jeu='factures', statut='pret').first()
    attendu = sum(x['Montant TTC'] for x in G['factures'])
    verif('contrôle de qualité : total des factures exact, période, aucune valeur illisible', abs(j.qualite['total'] - attendu) < 1
          and j.qualite['periode'][0] == '2026-01-05' and all(c['erreurs'] == 0 for c in j.qualite['champs']), (j.qualite['total'], attendu))
    verif('fichier Excel : en-têtes trouvés sous le titre (ligne 3)', M.JeuDonneesAnalyse.query.filter_by(
        analyse_id=ANID, type_jeu='fournisseurs', statut='pret').first().qualite['infos']['premiere_ligne'] == 4)
# colonne indispensable retirée : refus
octets, nom = FICHIERS['salaries']
importer(gest, 'salaries', octets, nom)
r = appel(gest, 'post', f'{PAGE}/jeu/salaries/colonnes', data={'csrf_token': jeton(gest, f'{PAGE}/jeu/salaries/colonnes'), 'c_matricule': 'Matricule'})
with A.app.app_context():
    j = M.JeuDonneesAnalyse.query.filter_by(analyse_id=ANID, type_jeu='salaries').order_by(M.JeuDonneesAnalyse.id.desc()).first()
    ancien = M.JeuDonneesAnalyse.query.filter_by(analyse_id=ANID, type_jeu='salaries', statut='remplace').first()
    verif('colonnes indispensables manquantes : fichier non validé', j.statut == 'a_valider')
    verif('fichier remplacé : l’ancien contenu est effacé du disque', ancien is not None and ancien.chemin_brut is None)
    data = {'csrf_token': jeton(gest, f'{PAGE}/jeu/salaries/colonnes')} | {f'c_{k}': v for k, v in am.proposer_correspondance('salaries', j.entetes).items()}
appel(gest, 'post', f'{PAGE}/jeu/salaries/colonnes', data=data)
# valeurs illisibles signalées
mauvais = dd.en_csv([{'Référence': 'P1', 'Fournisseur': 'F001', 'Date paiement': '32/13/2026', 'Montant': 'douze', 'RIB bénéficiaire': 'CI001'}])
from egalyx.analyse_moteur import lire_fichier, normaliser, proposer_correspondance
e, l, inf = lire_fichier(mauvais, 'p.csv')
_df, q = normaliser('paiements', e, inf['lignes_brutes'], proposer_correspondance('paiements', e), inf['premiere_ligne'])
qc = {c['code']: c for c in q['champs']}
verif('date, montant et RIB illisibles : signalés avec la ligne', qc['date']['erreurs'] == 1 and qc['montant']['erreurs'] == 1
      and qc['rib']['erreurs'] == 1 and qc['date']['exemples'][0]['ligne'] == 2 and q['avertissements'])

print('--- 4. IA : correspondance des colonnes sans les données')
REPONSE['contenu'] = json.dumps({'correspondance': {'numero': 'N° facture', 'fournisseur': 'Code fournisseur', 'date': 'Date facture',
                                                    'montant': 'Montant TTC', 'commande': 'Colonne inventée'}})
APPELS.clear()
r = ajax(gest, f'{PAGE}/jeu/factures/colonnes/ia', f'{PAGE}/jeu/factures/colonnes')
d = r.get_json() if r.status_code == 200 else {}
verif('IA : correspondance proposée, colonne inventée écartée', d.get('origine') == 'ia' and d['correspondance'].get('montant') == 'Montant TTC'
      and 'commande' not in d['correspondance'], d)
verif('IA : seuls les noms de colonnes sont envoyés (aucune valeur du fichier)', APPELS and 'FA-0001' not in APPELS[-1]
      and 'M. Traoré' not in APPELS[-1] and 'Montant TTC' in APPELS[-1])

print('--- 5. Tests et résultats')
r = appel(gest, 'get', f'{PAGE}?etape=tests')
APPL = sum(1 for t in am.TESTS if t['domaine'] in ('Factures', 'Paiements', 'Achats', 'Fournisseurs', 'Analyse des montants')) + 3   # + paie RIB, statistiques
verif('étape Tests : toute la bibliothèque, les tests achats applicables avec les 5 fichiers', r.status_code == 200
      and r.data.count(b'class="ad-test"') == len(am.TESTS) and r.data.count(b'data-applicable="1"') == APPL, r.data.count(b'data-applicable="1"'))
data = {f't_{t["code"]}': '1' for t in am.TESTS}
data['p_DELEGATION_plafonds'] = 'S. Diallo = 10 000 000\nD. Kouassi = 50 000 000\nDirection générale = 1 000 000 000'
data['p_FRACTIONNEMENT_seuil'] = '5 000 000'
r = poster(gest, f'{PAGE}/executer', data, page=f'{PAGE}?etape=tests')
with A.app.app_context():
    an = db.session.get(M.AnalyseDonnees, ANID)
    R = an.resultats or {}
    verif('tous les tests exécutés (les autres cycles non applicables faute de données), empreintes enregistrées', len(R) == len(am.TESTS)
          and sum(1 for x in R.values() if x['statut'] == 'non_applicable') == len(am.TESTS) - APPL and len(an.execution['jeux']) == 5
          and all(len(x['empreinte']) == 64 for x in an.execution['jeux']))
    verif('réglages lus (« 5 000 000 » = 5 000 000)', R['FRACTIONNEMENT']['parametres']['seuil'] == 5_000_000)
    for code, refs in dd.ATTENDU.items():
        trouve = {x['ref'] for x in R[code]['anomalies']} | {x['tiers'].split(' — ')[0] for x in R[code]['anomalies']}
        verif(f'{code} : anomalies plantées retrouvées ({R[code]["nb"]} ligne(s))', refs <= trouve, refs - trouve)
    verif('Benford : tableau des 9 chiffres et écart moyen', len(R['BENFORD']['tableau']['tableau']) == 9 and R['BENFORD']['tableau']['mad'] < 0.02)
    verif('doublon : les deux factures dans le même cas', len({x['groupe'] for x in R['FAC_DOUBLON']['anomalies'] if x['ref'].startswith('FA-0100')}) == 1)
    verif('chaque anomalie renvoie à la ligne du fichier d’origine', all(x['ligne'] > 1 for x in R['PAI_DOUBLON']['anomalies']))
r = appel(gest, 'get', f'{PAGE}?etape=resultats')
verif('page Résultats : indicateurs, tableau par priorité', r.status_code == 200 and b'Tests avec anomalies' in r.data and b'Paiements en double' in r.data)
r = appel(gest, 'get', f'{PAGE}/test/PAI_DOUBLON')
verif('détail d’un test : anomalies, règle attendue, suites possibles', r.status_code == 200 and b'VIR-0300-B' in r.data
      and b'Cr\xc3\xa9er la feuille de travail' in r.data)
verif('détail : filtre', b'VIR-0300' in appel(gest, 'get', f'{PAGE}/test/PAI_DOUBLON?q=0300').data)
r = appel(gest, 'get', f'{PAGE}/test/BENFORD')
verif('détail Benford : tableau des chiffres (si anomalies) ou absent du détail', r.status_code in (200, 404))

print('--- 6. Export, feuille de travail, échantillon, constat')
r = appel(gest, 'get', f'{PAGE}/export.xlsx')
wb = load_workbook(io.BytesIO(r.data)) if r.status_code == 200 else None
verif('export Excel : synthèse + une feuille par test avec anomalies', wb is not None and wb.sheetnames[0] == 'Synthèse'
      and any(s.startswith('Paiements en double') for s in wb.sheetnames), wb.sheetnames[:4] if wb else r.status_code)
r = poster(gest, f'{PAGE}/test/PAI_DOUBLON/feuille', page=f'{PAGE}/test/PAI_DOUBLON')
with A.app.app_context():
    f = M.FeuilleTravail.query.filter_by(audit_id=AID).order_by(M.FeuilleTravail.id.desc()).first()
    t = M.TestControleFeuille.query.filter_by(feuille_travail_id=f.id).first() if f else None
    verif('feuille de travail créée : test exhaustif, anomalies listées, empreinte dans la procédure', f is not None and t is not None
          and t.methode_echantillonnage == 'exhaustif' and 'VIR-0300-B' in (t.echantillon or '') and 'SHA-256' in (t.procedure or ''))
    verif('lien gardé dans l’analyse', (db.session.get(M.AnalyseDonnees, ANID).liens or {}).get('PAI_DOUBLON', {}).get('feuille') == f.reference)


def echantillon(graine):
    poster(gest, f'{PAGE}/echantillon', {'jeu': 'paiements', 'taille': '10', 'methode': 'aleatoire', 'graine': graine}, page=f'{PAGE}?etape=resultats')
    with A.app.app_context():
        f = M.FeuilleTravail.query.filter_by(audit_id=AID).order_by(M.FeuilleTravail.id.desc()).first()
        return [x['ref'] for x in f.contenu['analyse_donnees']['echantillon']['elements']]


e1, e2 = echantillon('1234'), echantillon('1234')
verif('échantillon aléatoire reproductible (même graine = même tirage)', len(e1) == 10 and e1 == e2, e1[:3])
r = appel(gest, 'get', f'{PAGE}/test/RIB_PAIEMENT/constat')
verif('constat pré-rempli : fait chiffré, critère et recommandation de la bibliothèque', r.status_code == 200
      and b'VIR-RIB' in r.data and 'compte enregistré et vérifié'.encode() in r.data)
r = poster(gest, f'{PAGE}/test/RIB_PAIEMENT/constat', {'titre': 'Paiement sur un compte non référencé', 'gravite': 'majeure',
                                                         'fait': 'Un paiement de 1 675 430 FCFA a été viré sur un compte différent.',
                                                         'critere': 'Paiement vers le RIB vérifié.', 'cause': 'Saisie libre du compte.',
                                                         'consequence': 'Détournement.', 'recommandation': 'Bloquer la saisie libre.'},
           page=f'{PAGE}/test/RIB_PAIEMENT/constat')
with A.app.app_context():
    c = M.Constatation.query.filter_by(audit_id=AID).order_by(M.Constatation.id.desc()).first()
    verif('constat créé sur la mission (5 C, gravité, pièce = analyse et empreintes)', c is not None and c.critere == 'Paiement vers le RIB vérifié.'
          and c.cause_racine == 'Saisie libre du compte.' and c.gravite == 'majeure' and 'SHA-256' in (c.documents_justificatifs or '')
          and c.statut == 'a_analyser', getattr(c, 'reference', None))

print('--- 7. IA : synthèse et constat à partir des chiffres agrégés')
REPONSE['contenu'] = json.dumps({'synthese': 'Synthèse de recette.', 'priorites': ['Vérifier VIR-RIB'], 'tests_complementaires': ['Circularisation']})
APPELS.clear()
r = ajax(gest, f'{PAGE}/synthese', f'{PAGE}?etape=resultats')
d = r.get_json() if r.status_code == 200 else {}
envoye = APPELS[-1] if APPELS else ''
verif('synthèse rédigée par l’IA et enregistrée', d.get('origine') == 'ia' and d.get('synthese') == 'Synthèse de recette.', d.get('origine'))
verif('synthèse : ni RIB, ni nom de fournisseur, ni fichier envoyés', envoye and 'CI0' not in envoye and 'FOURNISSEUR 0' not in envoye
      and 'Paiements en double' in envoye)
REPONSE['contenu'] = json.dumps({'titre': 'T', 'fait': 'Fait reformulé.', 'critere': 'C', 'cause': 'À compléter', 'consequence': 'Q',
                                 'recommandation': 'R', 'gravite': 'majeure', 'type': 'non_conformite', 'points_a_verifier': ['x']})
r = ajax(gest, f'{PAGE}/test/FAC_DOUBLON/constat/ia', f'{PAGE}/test/FAC_DOUBLON/constat')
d = r.get_json() if r.status_code == 200 else {}
verif('constat reformulé par l’IA', d.get('origine') == 'ia' and d['constat']['fait'] == 'Fait reformulé.', d.get('origine'))
with A.app.app_context():
    IA.ecrire_reglage('ia_fonctions', {'analyse_donnees': False})
APPELS.clear()
r = ajax(gest, f'{PAGE}/synthese', f'{PAGE}?etape=resultats')
d = r.get_json() if r.status_code == 200 else {}
verif('fonction IA coupée par le super admin : synthèse automatique, aucun appel', d.get('origine') == 'automatique' and not APPELS
      and 'Périmètre' in d.get('synthese', ''), d.get('origine'))
verif('… et correspondance par l’IA refusée', ajax(gest, f'{PAGE}/jeu/factures/colonnes/ia', f'{PAGE}/jeu/factures/colonnes').status_code == 403)
r = appel(sa, 'get', '/super-admin/ia/')
if r.status_code in (301, 302, 308):
    r = appel(sa, 'get', '/super-admin/ia')
verif('réglages IA du super admin : interrupteur « Analyse de données »', r.status_code == 200 and 'Analyse de données'.encode() in r.data, r.status_code)

print('--- 8. Cloisonnement')
for url in (PAGE, f'{PAGE}/test/PAI_DOUBLON', f'{PAGE}/export.xlsx', f'{PAGE}/jeu/factures/colonnes'):
    verif(f'autre organisation : {url.replace(PAGE, "…")} introuvable', appel(admin_b, 'get', url).status_code == 404)
r = poster(admin_b, f'{PAGE}/executer', {'t_FAC_DOUBLON': '1'}, page='/dashboard')
verif('autre organisation : exécution refusée', r.status_code == 404, r.status_code)
verif('lecteur : export refusé', appel(lect, 'get', f'{PAGE}/export.xlsx').status_code in (403, 404))

print('--- 9. Dossier figé')
with A.app.app_context():
    a = db.session.get(M.Audit, AID); a.etat_rapport = 'definitif'; a.dossier_rouvert_le = None; db.session.commit()
    avant = json.dumps(db.session.get(M.AnalyseDonnees, ANID).resultats, sort_keys=True)
r = poster(gest, f'{PAGE}/executer', {'t_FAC_DOUBLON': '1'}, page=PAGE)
r2 = importer(gest, 'factures', *FICHIERS['factures'])
with A.app.app_context():
    verif('dossier figé : ni nouvelle exécution, ni import', json.dumps(db.session.get(M.AnalyseDonnees, ANID).resultats, sort_keys=True) == avant
          and M.JeuDonneesAnalyse.query.filter_by(analyse_id=ANID, type_jeu='factures', statut='pret').count() == 1)
verif('dossier figé : consultation toujours possible', appel(gest, 'get', f'{PAGE}?etape=resultats').status_code == 200
      and 'figé'.encode() in appel(gest, 'get', PAGE).data)
with A.app.app_context():
    a = db.session.get(M.Audit, AID); a.etat_rapport = None; db.session.commit()

print('--- 10. Conservation échue')
with A.app.app_context():
    j = M.JeuDonneesAnalyse.query.filter_by(analyse_id=ANID, type_jeu='paiements', statut='pret').first()
    chemins = (j.chemin_brut, j.chemin_normalise)
    j.expire_le = datetime.utcnow() - timedelta(days=1); db.session.commit()
    JID = j.id
appel(gest, 'get', PAGE)
with A.app.app_context():
    j = db.session.get(M.JeuDonneesAnalyse, JID)
    verif('fichier échu supprimé du disque, empreinte et résultats conservés', j.statut == 'supprime' and not any(os.path.exists(c) for c in chemins)
          and j.empreinte and db.session.get(M.AnalyseDonnees, ANID).resultats.get('PAI_DOUBLON', {}).get('nb'))
r = poster(admin, f'{PAGE}/reglages', {'conservation_jours': '180'}, page=PAGE)
with A.app.app_context():
    from egalyx.analyse_donnees import conservation_jours
    verif('durée de conservation réglable par l’organisation', conservation_jours(1) == 180)

print('--- 11. Journal et aide')
with A.app.app_context():
    J = M.JournalActiviteClient
    actions = {x.action for x in J.query.filter(J.action.like('analyse_donnees%')).all()}
    verif('journal : import, exécution, export, constat', {'analyse_donnees_import', 'analyse_donnees_executee', 'analyse_donnees_export',
                                                          'analyse_donnees_constat'} <= actions, sorted(actions))
    from egalyx.aide_contenu import ARTICLES
    verif('centre d’aide : article « Analyse de données »', any(x['id'] == 'analyse_donnees' for x in ARTICLES))

print('--- 12. Suppression')
r = poster(gest, f'{PAGE}/supprimer', page=f'{PAGE}?etape=resultats')
with A.app.app_context():
    verif('analyse supprimée, feuilles et constats conservés', db.session.get(M.AnalyseDonnees, ANID) is None
          and M.JeuDonneesAnalyse.query.filter_by(analyse_id=ANID).count() == 0 and M.Constatation.query.filter_by(audit_id=AID).count() >= 1)

print(f'\n{sum(res)}/{len(res)} vérifications réussies')
raise SystemExit(0 if all(res) else 1)
