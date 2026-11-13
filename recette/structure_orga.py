"""Recette : structure de l'organisation, collaborateurs rattachés, périmètre, départs, profil, organigramme."""
import contextlib
import io
import json
import os
import re
os.environ['EGALYX_COLLECTE_AUTO'] = '0'
import socle
from socle import Muet, appel, creer
res = []


def verif(nom, cond, detail=''):
    res.append(bool(cond)); print('OK   ' if cond else 'ÉCHEC', nom, detail)


with Muet():
    A, ids = socle.preparer()
A.app.config['WTF_CSRF_ENABLED'] = False
import models as M
from models import db

with A.app.app_context():
    cid = db.session.get(M.User, ids['admin_a']).client_id
    cid_b = db.session.get(M.User, ids['admin_b']).client_id
    pays = creer(M.Pays, nom="Côte d'Ivoire", code='CIV', client_id=cid, drapeau='🇨🇮')
    pole = creer(M.Pole, nom='Pôle Support', client_id=cid, pays_id=pays.id, responsable_id=ids['validateur'])
    d1 = creer(M.Direction, nom='Direction financière', client_id=cid, pole_id=pole.id, responsable_id=ids['gestionnaire'])
    d2 = creer(M.Direction, nom='Direction générale', client_id=cid)
    s1 = creer(M.Service, nom='Comptabilité', direction_id=d1.id, client_id=cid, is_active=True)
    s2 = creer(M.Service, nom='Trésorerie', direction_id=d1.id, client_id=cid, is_active=True)
    db_b = creer(M.Direction, nom='Direction secrète B', client_id=cid_b)
    db.session.flush()
    g = db.session.get(M.User, ids['gestionnaire'])
    g.direction_id, g.service_id, g.perimetre_acces = d1.id, s1.id, 'direction'
    g.prenom, g.nom, g.fonction = 'Awa', 'Coulibaly', 'Directrice financière'
    g.permissions = dict(g.permissions or {}, can_view_departments=True)
    c1 = creer(M.Cartographie, nom='Carto finance', client_id=cid, direction_id=d1.id, is_archived=False)
    c2 = creer(M.Cartographie, nom='Carto direction générale', client_id=cid, direction_id=d2.id, is_archived=False)
    db.session.commit()
    I = {'pays': pays.id, 'pole': pole.id, 'd1': d1.id, 'd2': d2.id, 's1': s1.id, 's2': s2.id, 'db': db_b.id,
         'c1': c1.id, 'c2': c2.id}

admin = socle.navigateur(A, ids['admin_a'])

print('--- Page « Structure de l’organisation »')
r = appel(admin, 'GET', '/admin/directions')
h = r.data.decode()
verif('page structure : 200', r.status_code == 200, str(r.status_code))
verif('titre « Structure de l’organisation »', 'Structure de l\'organisation' in h or 'Structure de l&#39;organisation' in h)
cles = re.findall(r'<tr class="n-[a-z]+" data-cle="([a-z]+-\d+)"', h)
verif('toutes les entités listées (pays, pôle, 2 directions, 2 services)',
      {f"pays-{I['pays']}", f"pole-{I['pole']}", f"direction-{I['d1']}", f"direction-{I['d2']}", f"service-{I['s1']}", f"service-{I['s2']}"} <= set(cles), str(cles))
verif('direction générale (sans pôle) en tête, avant les pays', cles.index(f"direction-{I['d2']}") < cles.index(f"pays-{I['pays']}"))
verif('responsable affiché avec son nom et sa fonction', 'Awa Coulibaly' in h and 'Directrice financière' in h)
verif('direction sans responsable : « À pourvoir »', 'À pourvoir' in h)
verif('cloisonnement : rien d’une autre organisation', 'Direction secrète B' not in h)
verif('collaborateur rattaché listé sous son service', 'data-membres-de="service-%d"' % I['s1'] in h)
verif('actions : ajouter un service à une direction (formulaire pré-rempli, retour sur la page)',
      f'/admin/service/nouveau/{I["d1"]}?retour=/admin/directions' in h)
verif('actions : créer un collaborateur directement dans un service', f'service_id={I["s1"]}' in h)
verif('lien « voir dans l’organigramme » vers l’entité', f'#direction-{I["d1"]}' in h)
r = appel(admin, 'GET', '/admin/directions/cartes')
verif('ancienne vue en cartes toujours disponible', r.status_code == 200, str(r.status_code))
print('--- Bascule arborescence / cartes')
bc = socle.navigateur(A, ids['admin_a'])
h = appel(bc, 'GET', '/admin/directions').data.decode()
verif('par défaut : arborescence, avec la bascule', 'id="soTable"' in h and 'class="eg-bascule"' in h and '/admin/directions?vue=cartes' in h)
r = appel(bc, 'GET', '/admin/directions?vue=cartes'); h = r.data.decode()
verif('« Cartes » : ancienne vue (Gestion des Directions et Services)', r.status_code == 200 and 'Gestion des Directions et Services' in h and 'id="soTable"' not in h)
verif('l’ancienne vue a aussi la bascule (cartes active)', 'class="eg-bascule"' in h and re.search(r'class="actif"[^>]*>\s*<i class="fas fa-grip"', h) is not None)
verif('choix retenu (cookie)', 'eg_vue_structure=cartes' in (r.headers.get('Set-Cookie') or ''))
h = appel(bc, 'GET', '/admin/directions').data.decode()
verif('visite suivante : s’ouvre en cartes', 'Gestion des Directions et Services' in h and 'id="soTable"' not in h)
h = appel(bc, 'GET', '/admin/directions?pole=tous&tri=nom').data.decode()
verif('filtres de l’ancienne vue : restent en cartes', 'Gestion des Directions et Services' in h)
appel(bc, 'GET', '/admin/directions?vue=arbre')
h = appel(bc, 'GET', '/admin/directions').data.decode()
verif('retour à l’arborescence, retenu aussi', 'id="soTable"' in h)
r = appel(bc, 'GET', '/admin/directions?vue=nimporte')
verif('valeur inconnue : vue retenue, pas d’erreur', r.status_code == 200 and 'id="soTable"' in r.data.decode())
r = appel(socle.navigateur(A, ids['lecteur']), 'GET', '/admin/directions?vue=cartes')
verif('sans permission : refusé aussi en cartes', r.status_code in (302, 303), str(r.status_code))
r = appel(admin, 'GET', '/admin/services')
verif('/admin/services (cassée avant) renvoie vers la structure', r.status_code in (301, 302) and r.headers.get('Location', '').endswith('/admin/directions'))
lect = socle.navigateur(A, ids['lecteur'])
r = appel(lect, 'GET', '/admin/directions')
verif('sans permission : accès refusé (redirection)', r.status_code in (302, 303), str(r.status_code))
r = appel(socle.navigateur(A, ids['admin_b']), 'GET', '/admin/directions')
verif('autre organisation : ne voit que sa structure', r.status_code == 200 and 'Direction secrète B' in r.data.decode() and 'Direction financière' not in r.data.decode())

print('--- Archivage et suppression')
r = appel(admin, 'DELETE', f'/admin/service/{I["s1"]}/supprimer', headers={'Accept': 'application/json'})
d = r.get_json(silent=True) or {}
verif('service avec un collaborateur : archivage refusé, avec la raison', r.status_code == 400 and 'collaborateur' in (d.get('error') or ''), d.get('error'))
verif('message bien accordé (« Ce service est encore utilisé »)', (d.get('error') or '').startswith('Ce service est encore utilisé :'))
r = appel(admin, 'DELETE', f'/admin/direction/{I["d2"]}/supprimer', headers={'Accept': 'application/json'})
d = r.get_json(silent=True) or {}
verif('direction avec une cartographie : refus clair, sans « True »', r.status_code == 400 and 'cartographie' in d.get('error', '') and 'True' not in d.get('error', ''), d.get('error'))
verif('… au féminin (« Cette direction est encore utilisée »)', d.get('error', '').startswith('Cette direction est encore utilisée'))
r = appel(admin, 'DELETE', f'/admin/service/{I["s2"]}/supprimer', headers={'Accept': 'application/json'})
verif('service vide : archivé', r.status_code == 200 and (r.get_json(silent=True) or {}).get('success'), str(r.status_code))
h = appel(admin, 'GET', '/admin/directions').data.decode()
verif('service archivé : disparaît de la structure', f'data-cle="service-{I["s2"]}"' not in h)
r = appel(admin, 'DELETE', f'/admin/pays/{I["pays"]}/supprimer', headers={'Accept': 'application/json'})
verif('pays qui contient encore un pôle : refusé', r.status_code == 400 and 'pôle' in (r.get_json(silent=True) or {}).get('error', ''), str(r.status_code))

print('--- Formulaires ouverts depuis la page')
r = appel(admin, 'GET', f'/admin/pole/nouveau?pays_id={I["pays"]}&retour=/admin/directions')
verif('nouveau pôle avec ?pays_id= : pays pré-choisi', r.status_code == 200 and "['pays_id','pole_id','direction_id']" in r.data.decode())
r = appel(admin, 'POST', '/admin/pole/nouveau?retour=/admin/directions',
          data={'nom': 'Pôle Contrôle', 'pays_id': I['pays'], 'couleur': '#7c3aed', 'ordre': '0', 'description': '',
                'type_responsable': 'utilisateur', 'responsable_id': str(ids['validateur'])})
verif('après enregistrement : retour sur la structure', r.status_code in (302, 303) and r.headers.get('Location', '').endswith('/admin/directions'),
      f"{r.status_code} {r.headers.get('Location')}")
r = appel(admin, 'POST', '/admin/pole/nouveau?retour=https://pirate.example/x',
          data={'nom': 'Pôle Test', 'pays_id': I['pays'], 'couleur': '#7c3aed', 'ordre': '0', 'description': '',
                'type_responsable': 'utilisateur', 'responsable_id': str(ids['validateur'])})
verif('retour vers un site extérieur : ignoré', 'pirate.example' not in (r.headers.get('Location') or ''), r.headers.get('Location'))

print('--- Collaborateurs : identité et rattachement')
u_id = ids['operateur']
with A.app.app_context():
    db.session.get(M.User, u_id).email = 'operateur@banque-recette.com'; db.session.commit()
r = appel(admin, 'GET', f'/client-admin/utilisateur/creer?service_id={I["s1"]}')
h = r.data.decode()
verif('créer un collaborateur depuis un service : service pré-choisi',
      r.status_code == 200 and re.search(rf'<option value="{I["s1"]}" data-direction="{I["d1"]}" selected', h) is not None)
verif('… et sa direction aussi', re.search(rf'<option value="{I["d1"]}" selected', h) is not None)
verif('champs prénom, nom, fonction dans le formulaire', all(f'name="eg_{x}"' in h for x in ('prenom', 'nom', 'fonction')))
r = appel(admin, 'GET', f'/client-admin/utilisateur/{u_id}/editer')
h = r.data.decode()
champs = {m[0]: m[1] for m in re.findall(r'name="([a-z_]+)"[^>]*?value="([^"]*)"', h)}
form = {k: v for k, v in champs.items() if k in ('username', 'email', 'csrf_token')}
form.update({'role': 'utilisateur', 'is_active': 'y', 'password': '', 'confirm_password': '', 'department': '',
             'template_permissions': '0', 'submit': 'Mettre à jour', 'eg_affectation': '1', 'eg_prenom': 'Marc', 'eg_nom': 'Diallo',
             'eg_fonction': 'Contrôleur interne', 'eg_direction_id': I['d1'], 'eg_service_id': I['s1'], 'eg_perimetre': 'service'})
r = appel(admin, 'POST', f'/client-admin/utilisateur/{u_id}/editer', data=form)
with A.app.app_context():
    u = db.session.get(M.User, u_id)
    verif('édition : prénom, nom, fonction enregistrés', (u.prenom, u.nom, u.fonction) == ('Marc', 'Diallo', 'Contrôleur interne'), f'{r.status_code} {u.prenom} {u.nom}')
    verif('édition : rattachement et périmètre enregistrés', (u.direction_id, u.service_id, u.perimetre_acces) == (I['d1'], I['s1'], 'service'))
    verif('nom affiché : « Prénom Nom »', u.nom_affiche == 'Marc Diallo')
    sans = db.session.get(M.User, ids['lecteur'])
    verif('sans prénom/nom : identifiant mis en forme', sans.nom_affiche == 'Lecteur')
h = appel(admin, 'GET', '/client-admin/utilisateurs').data.decode()
verif('liste : nom complet et fonction', 'Marc Diallo' in h and 'Contrôleur interne' in h)
verif('liste : direction et service (plus de « Non spécifié »)', 'Direction financière' in h and 'Comptabilité' in h and 'Non spécifié' not in h)
verif('liste : périmètre limité signalé', 'Voit : son service' in h)
verif('liste : responsable d’un pôle affiché comme tel', 'Pôle Support' in h and 'Responsable · pôle' in h)
verif('liste : export sans risque d’apostrophe (noms en JSON)', "rows.push([" in h and '"Marc Diallo"' in h)
r = appel(admin, 'GET', '/client-admin/utilisateur/nouveau')
verif('une seule page de création (« nouveau » → « creer »)', r.status_code in (302, 307) and '/client-admin/utilisateur/creer' in r.headers.get('Location', ''))

print('--- Départ d’un collaborateur')
with A.app.app_context():
    v = creer(M.User, username='depart.test', email='depart@recette.test', role='utilisateur', client_id=cid, is_active=True,
              permissions=socle.perms())
    db.session.commit(); vid = v.id
    d1o = db.session.get(M.Direction, I['d2']); d1o.responsable_id = vid; db.session.commit()
r = appel(admin, 'POST', f'/admin/utilisateur/{vid}/supprimer', headers={'Content-Type': 'application/json'}, data='{}')
d = r.get_json(silent=True) or {}
with A.app.app_context():
    v = db.session.get(M.User, vid)
    verif('« Désactiver » depuis la fiche (ancienne suppression définitive) : compte conservé, désactivé', v is not None and v.is_active is False, str(r.status_code))
    verif('… historique conservé : il dirige toujours la direction jusqu’au transfert', db.session.get(M.Direction, I['d2']).responsable_id == vid)
verif('… réponse JSON avec la page de transfert', d.get('success') and d.get('responsabilites', 0) >= 1 and '/responsabilites' in (d.get('redirect') or ''), json.dumps(d)[:200])
r = appel(admin, 'POST', f'/admin/utilisateur/{vid}/supprimer', data={'x': '1'})
verif('depuis un formulaire classique : redirection (pas de JSON brut)', r.status_code in (302, 303), str(r.status_code))
r = appel(admin, 'POST', f'/client-admin/utilisateur/{ids["admin_a"]}/supprimer', headers={'Content-Type': 'application/json'}, data='{}')
verif('impossible de se désactiver soi-même', r.status_code == 400)
r = appel(admin, 'GET', f'/client-admin/utilisateur/{vid}/responsabilites')
verif('page des responsabilités à transférer', r.status_code == 200 and 'Direction générale' in r.data.decode())
h = appel(admin, 'GET', f'/client-admin/utilisateur/{u_id}/editer').data.decode()
verif('fiche utilisateur : bouton « Désactiver le compte » (plus « Supprimer définitivement »)',
      'Désactiver le compte' in h and 'Supprimer définitivement' not in h and 'irréversible' not in h)
h = appel(admin, 'GET', '/client-admin/utilisateurs').data.decode()
verif('liste : fenêtre de désactivation cohérente (plus « données perdues »)', 'Toutes les données associées seront perdues' not in h and 'historique reste attribué' in h)

print('--- Périmètre')
gc = socle.navigateur(A, ids['gestionnaire'])
h = appel(gc, 'GET', '/cartographies').data.decode() if appel(gc, 'GET', '/cartographies').status_code == 200 else appel(gc, 'GET', '/cartographie').data.decode()
verif('limité à sa direction : voit la cartographie de sa direction', 'Carto finance' in h)
verif('… mais pas celle d’une autre direction', 'Carto direction générale' not in h)
r = appel(gc, 'GET', f'/cartographie/{I["c2"]}')
verif('… et l’adresse directe répond « introuvable »', r.status_code == 404, str(r.status_code))

print('--- Mon profil')
pc = socle.navigateur(A, ids['lecteur'])
with A.app.app_context():
    avant = db.session.get(M.User, ids['lecteur']).password_hash
r = appel(pc, 'POST', '/profil/update', data={'email': 'lecteur@recette.test', 'new_password': 'court', 'confirm_password': 'court'})
with A.app.app_context():
    verif('mot de passe trop faible : pas d’erreur serveur, refus expliqué', r.status_code in (302, 303)
          and db.session.get(M.User, ids['lecteur']).password_hash == avant, str(r.status_code))
with pc.session_transaction() as s:
    msgs = [m for _c, m in s.get('_flashes', [])]
verif('… message clair', any('12 caractères' in m for m in msgs), str(msgs))
r = appel(pc, 'POST', '/profil/update', data={'email': 'gestionnaire@recette.test', 'prenom': 'Léa', 'nom': 'Kouamé', 'fonction': 'Auditrice'})
with A.app.app_context():
    u = db.session.get(M.User, ids['lecteur'])
    verif('profil : prénom, nom, fonction enregistrés', (u.prenom, u.nom, u.fonction) == ('Léa', 'Kouamé', 'Auditrice'))
    verif('profil : e-mail déjà pris par un autre compte refusé', u.email == 'lecteur@recette.test')
r = appel(pc, 'GET', '/profil')
verif('profil : champs identité et rattachement affichés', r.status_code == 200 and 'name="prenom"' in r.data.decode() and 'Direction / service' in r.data.decode())

print('--- Organigramme')
r = appel(admin, 'GET', '/admin/organigramme')
h = r.data.decode()
verif('organigramme : 200', r.status_code == 200, str(r.status_code))
verif('organigramme : noms et fonctions des responsables', 'Awa Coulibaly' in h and 'Directrice financière' in h)
donnees = json.loads(re.search(r'<script id="ocDonnees" type="application/json">(.*?)</script>', h, re.S).group(1))
verif('organigramme : un pays n’a pas de faux « poste à pourvoir »', f'data-cle="pays-{I["pays"]}"' in h
      and 'Responsable pays' not in h.split(f'data-cle="pays-{I["pays"]}"', 1)[1].split('oc-chiffres', 1)[0])
verif('organigramme : responsable de pôle non compté « sans rattachement »',
      'Validateur' not in (h.split('<details class="oc-sans"', 1)[1].split('</details>', 1)[0] if '<details class="oc-sans"' in h else ''))
verif('organigramme : fiche latérale lisible (couleurs définies hors du graphique)', '.oc, .oc-fiche {' in h)
verif('organigramme : plein écran, vue en liste, ouverture sur une entité (#…)',
      'ocPleinEcran' in h and 'Vue en liste' in h and 'allerA(cle)' in h)
verif('organigramme : avatars des collaborateurs en couleur (compte Egalyx)', 'class="oc-av  manuel">AA' not in h)
verif('organigramme : départ à une taille lisible (pas 45 %)', 'var LISIBLE = 0.78' in h)
verif('organigramme : fiche d’une direction avec ses services', any(e['nom'] == 'Comptabilité' for e in donnees[f'direction-{I["d1"]}']['enfants']))

print('--- Journaux')
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    admin.get('/admin/directions'); admin.get('/client-admin/utilisateurs')
lignes = [l for l in buf.getvalue().splitlines() if 'Permission' in l or 'permission' in l]
verif('aucune trace de vérification de droits dans les journaux', not lignes, str(lignes[:2]))

print(f'\n{sum(res)}/{len(res)} vérifications réussies')
