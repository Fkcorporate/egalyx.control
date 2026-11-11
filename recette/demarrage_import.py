"""Démarrage en une semaine : bibliothèque (contrôles types, nouvelle cartographie), import Excel/CSV « tel quel »
(reconnaissance des colonnes, échelles, anomalies, doublons, dispositifs), cloisonnement, jalons de la mise en route."""
import io
import re
import sys

import socle
import objets
from socle import Muet, appel

with Muet():
    A, ids = socle.preparer()
    O = objets.peupler_objets(A, ids)
import models as M
from models import db

res = []


def verif(nom, cond, detail=''):
    res.append(bool(cond))
    print('OK   ' if cond else 'ÉCHEC', nom, detail)


def go(role, m, url, **kw):
    r = appel(socle.navigateur(A, ids[role]), m, url, **kw)
    return r, r.data.decode('utf-8', 'ignore')


def compte(modele, **f):
    with A.app.app_context():
        db.session.expire_all()
        return modele.query.filter_by(**f).count()


print('--- Bibliothèque : nouvelle cartographie + contrôles types')
r, t = go('gestionnaire', 'get', '/risques/bibliotheque/?secteur=banque')
verif('Page bibliothèque affichée', r.status_code == 200 and 'contrôle(s) type(s)' in t, f'{r.status_code} {socle.cause(A)}')
avant_dm = compte(M.DispositifMaitrise, client_id=1)
r, t = go('gestionnaire', 'post', '/risques/bibliotheque/', data={'secteur': 'banque', 'cartographie_id': 'nouvelle',
                                                         'nouvelle_nom': 'Carto banque recette', 'avec_controles': '1',
                                                         'risques': ['0', '1', '2']})
with A.app.app_context():
    c = M.Cartographie.query.filter_by(nom='Carto banque recette', client_id=1).first()
    nb_r = M.Risque.query.filter_by(cartographie_id=c.id).count() if c else 0
    dms = M.DispositifMaitrise.query.join(M.Risque, M.Risque.id == M.DispositifMaitrise.risque_id) \
        .filter(M.Risque.cartographie_id == (c.id if c else -1)).all()
verif('Nouvelle cartographie créée avec 3 risques', c is not None and nb_r == 3, f'{r.status_code} {nb_r} {socle.cause(A)}')
verif('Contrôles types créés (référence DM-…, non évalués)', dms and all(d.reference.startswith('DM-R-BQ-') for d in dms)
      and all(getattr(d, 'efficacite_reelle', None) in (None, 0) for d in dms), str(len(dms)))
r, t = go('lecteur', 'get', '/risques/bibliotheque/')
verif('Lecteur : pas d\'accès à la bibliothèque', r.status_code in (302, 403), str(r.status_code))

print('--- Import Excel « tel quel »')
import openpyxl
wb = openpyxl.Workbook()
ws = wb.active
ws.title = 'Ma carto'
ws.append(['CARTOGRAPHIE DES RISQUES 2026 — Banque XYZ'])
ws.append([])
ws.append(['N°', 'Libellé du risque', 'Famille', 'Causes', 'Gravité', 'Fréquence', 'Contrôles existants', 'Propriétaire'])
ws.append(['R-01', 'Fraude interne sur les comptes dormants', 'Fraude', 'Absence de revue', 4, 3,
           'Revue mensuelle des comptes dormants ; Double validation des réactivations', 'gestionnaire'])
ws.append(['R-02', 'Indisponibilité du core banking', 'SI', '', 'Élevé', 'Possible', '- Plan de secours\n- Sauvegardes', 'Inconnu Total'])
ws.append(['', '', 'ligne sans intitulé', '', '', '', '', ''])
ws.append(['R-03', 'Fraude interne sur les comptes dormants', 'Fraude', '', 2, 2, '', ''])
ws.append(['R-04', 'Erreur de saisie des virements', 'Opérations', '', 'bof', 'Probable', '', ''])
buf = io.BytesIO()
wb.save(buf)
buf.seek(0)
with A.app.app_context():
    u_g = db.session.get(M.User, ids['gestionnaire'])
    ws_user = u_g.username
# le responsable est l'identifiant du gestionnaire
wb2 = openpyxl.load_workbook(io.BytesIO(buf.getvalue()))
wb2.active['H4'] = ws_user
buf = io.BytesIO()
wb2.save(buf)
contenu = buf.getvalue()

r, t = go('gestionnaire', 'get', '/cartographie-import/')
verif('Page d\'import affichée', r.status_code == 200 and 'Analyser le fichier' in t, f'{r.status_code} {socle.cause(A)}')
r, t = go('gestionnaire', 'get', '/cartographie-import/modele.xlsx')
verif('Modèle Excel téléchargeable', r.status_code == 200 and r.data[:2] == b'PK', str(r.status_code))
c_g = socle.navigateur(A, ids['gestionnaire'])
r = appel(c_g, 'post', '/cartographie-import/', data={'fichier': (io.BytesIO(contenu), 'ma_carto.xlsx')},
          content_type='multipart/form-data')
loc = r.headers.get('Location', '') if r.status_code == 302 else ''
jeton = (re.findall(r'/cartographie-import/([0-9a-f]{32})', loc) or [''])[0]
verif('Fichier analysé, redirection vers l\'aperçu', bool(jeton), f'{r.status_code} {loc} {socle.cause(A)}')
r = appel(c_g, 'get', f'/cartographie-import/{jeton}')
t = r.data.decode('utf-8', 'ignore')
verif('Aperçu affiché', r.status_code == 200 and 'Ce qui sera créé' in t, f'{r.status_code} {socle.cause(A)}')
verif('En-tête trouvé sous le titre (ligne 3)', 'en-tête en ligne 3' in t)
verif('Colonnes reconnues (Libellé du risque → intitulé, Gravité → impact, Propriétaire → responsable)',
      re.search(r'name="col_intitule">.*?<option value="1" selected', t, re.S)
      and re.search(r'name="col_impact">.*?<option value="4" selected', t, re.S)
      and re.search(r'name="col_responsable">.*?<option value="7" selected', t, re.S))
verif('Contrôles découpés (« ; » et tirets)', 'Double validation des réactivations' in t and '<li>Sauvegardes</li>' in t)
verif('Doublon signalé', 'en double dans le fichier' in t)
verif('Anomalies signalées (valeur illisible, échelle, responsable inconnu, ligne vide)',
      '« bof » non reconnu' in t and 'inconnu parmi les utilisateurs' in t and 'intitulé manquant' in t, '')

c_l = socle.navigateur(A, ids['admin_b'])
r = appel(c_l, 'get', f'/cartographie-import/{jeton}')
verif('Autre organisation : aperçu inaccessible', r.status_code == 302 and jeton not in (r.headers.get('Location') or ''),
      str(r.status_code))
r, _ = go('lecteur', 'get', f'/cartographie-import/{jeton}')
verif('Lecteur : import refusé', r.status_code in (302, 403), str(r.status_code))

# corriger la correspondance : pas de colonne responsable
form = {'csrf_token': '', 'entete': '3', 'col_reference': '0', 'col_intitule': '1', 'col_categorie': '2', 'col_cause': '3',
        'col_impact': '4', 'col_probabilite': '5', 'col_controles': '6', 'col_responsable': '7'}
r = appel(c_g, 'post', f'/cartographie-import/{jeton}', data=dict(form, action='actualiser'))
verif('Correspondance enregistrée', r.status_code == 302, str(r.status_code))

avant = compte(M.Risque, client_id=1)
r = appel(c_g, 'post', f'/cartographie-import/{jeton}',
          data=dict(form, action='importer', cartographie_id='nouvelle', nouvelle_nom='Carto importée recette',
                    creer_dispositifs='1', ignorer_doublons=['0', '1']))
verif('Import confirmé → fiche de la cartographie', r.status_code == 302 and '/cartographie' in (r.headers.get('Location') or ''),
      f'{r.status_code} {r.headers.get("Location")} {socle.cause(A)}')
with A.app.app_context():
    c = M.Cartographie.query.filter_by(nom='Carto importée recette', client_id=1).first()
    rs = {x.intitule: x for x in M.Risque.query.filter_by(cartographie_id=c.id).all()} if c else {}
    r1 = rs.get('Fraude interne sur les comptes dormants')
    r2 = rs.get('Indisponibilité du core banking')
    r4 = rs.get('Erreur de saisie des virements')
    d1 = M.DispositifMaitrise.query.filter_by(risque_id=r1.id).all() if r1 else []
    d2 = M.DispositifMaitrise.query.filter_by(risque_id=r2.id).all() if r2 else []
    print('   ', {k: (v.reference, v.impact, v.probabilite, v.score_risque) for k, v in rs.items()})
    verif('3 risques créés (doublon et ligne vide ignorés)', len(rs) == 3, str(len(rs)))
    verif('Référence du client conservée', r1 is not None and r1.reference == 'R-01', r1.reference if r1 else '')
    verif('Cotation chiffrée reprise et score calculé', r1 is not None and r1.score_risque == 12, str(r1.score_risque if r1 else ''))
    verif('Cotation en mots convertie (Élevé = 4, Possible = 3)', r2 is not None and r2.score_risque == 12,
          str(r2.score_risque if r2 else ''))
    verif('Valeur illisible : cotation provisoire 3 × probabilité', r4 is not None and r4.score_risque == 12, str(r4.score_risque if r4 else ''))
    verif('Dispositifs créés depuis la colonne contrôles', len(d1) == 2 and len(d2) == 2, f'{len(d1)} {len(d2)}')
    verif('Responsable reconnu rattaché aux dispositifs', d1 and all(d.responsable_id == ids['gestionnaire'] for d in d1))
    verif('Responsable inconnu noté sur le risque', r2 is not None and 'Inconnu Total' in (r2.description or ''))
    verif('Cotation manquante signalée comme provisoire', r4 is not None and 'provisoire' in (r4.description or '')
          and (r4.metadonnees or {}).get('cotation_a_completer'))
r = appel(c_g, 'get', f'/cartographie-import/{jeton}')
verif('Jeton supprimé après import', r.status_code == 302)

print('--- CSV ; et échelle 1-10')
csv_txt = 'Risque;Impact;Probabilité;Mesures\nVol de données clients;10;2;Chiffrement\n'
r = appel(c_g, 'post', '/cartographie-import/', data={'fichier': (io.BytesIO(csv_txt.encode('cp1252')), 'c.csv')},
          content_type='multipart/form-data')
jeton2 = (re.findall(r'/cartographie-import/([0-9a-f]{32})', r.headers.get('Location', '')) or [''])[0]
r = appel(c_g, 'get', f'/cartographie-import/{jeton2}')
t = r.data.decode('utf-8', 'ignore')
verif('CSV Windows (;) lu, échelle 1-10 ramenée à 1-5', r.status_code == 200 and 'Vol de données clients' in t
      and re.search(r'imp-note">5</span> × <span class="imp-note">2<', t), socle.cause(A))
r = appel(c_g, 'post', '/cartographie-import/', data={'fichier': (io.BytesIO(b'x'), 'vieux.xls')}, content_type='multipart/form-data')
verif('Ancien .xls refusé avec un message clair', r.status_code == 302)

print('--- Mise en route : jalons')
r, t = go('admin_a', 'get', '/demarrage')
verif('Mise en route affichée avec jalons', r.status_code == 200 and 'Compte ouvert le' in t and 'Atteint le' in t,
      f'{r.status_code} {socle.cause(A)}')
verif('Lien vers l\'import Excel', '/cartographie-import/' in t or 'Identifier au moins 10 risques' in t)

print(f'\n{sum(res)}/{len(res)} vérifications réussies')
sys.exit(0 if all(res) else 1)
