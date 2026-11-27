"""Recette : formation à la conformité (e-learning), lot 1.

Activation par le super admin (module sur activation, fermé par défaut), droits (gestion, suivi, participant),
module (contenu, vidéo, quiz, publication, versions), campagne (cible, notifications, relance, ajout, clôture, export),
« Mes formations » (suivre, quiz noté, bonnes réponses cachées avant validation, validation sans quiz),
cloisonnement entre organisations et entre personnes, sécurité du contenu (pas de HTML injecté)."""
import io
import json
import os
import re
from datetime import date, timedelta

os.environ['EGALYX_COLLECTE_AUTO'] = '0'
import socle
from socle import Muet, appel
with Muet():
    A, ids = socle.preparer()
import models as M
from models import db
from egalyx import formation_conformite as fc

res = []


def verif(nom, cond, detail=''):
    res.append(bool(cond)); print('OK   ' if cond else 'ÉCHEC', nom, detail)


def jeton(c, url='/dashboard'):
    t = appel(c, 'get', url).data.decode(errors='ignore')
    m = re.search(r'name="csrf_token" value="([^"]+)"', t) or re.search(r'name="csrf-token" content="([^"]+)"', t)
    return m.group(1) if m else ''


def suivre(c, url):
    r = appel(c, 'get', url)
    while r.status_code in (301, 302):
        r = appel(c, 'get', r.location)
    return r


sa, admin, gest, lect, oper, admin_b = (socle.navigateur(A, ids[r]) for r in
                                        ('superadmin', 'admin_a', 'gestionnaire', 'lecteur', 'operateur', 'admin_b'))

print('--- 1. Module fermé tant que le super admin ne l’a pas activé')
r = appel(admin, 'get', '/formation-conformite/')
verif('administrateur, module non activé : page fermée', r.status_code in (403, 404), r.status_code)
t = appel(admin, 'get', '/dashboard').data.decode(errors='ignore')
verif('menu : pas d’entrée « Formations conformité »', 'Formations conformité' not in t and 'Mes formations' not in t)
r = appel(sa, 'get', '/super-admin/client/1/modules')
verif('super admin : le module apparaît dans la page « Modules » du client', r.status_code == 200
      and 'Formation à la conformité (e-learning)'.encode() in r.data and b'formation_conformite' in r.data, r.status_code)
with A.app.app_context():
    actuels = {k for k, v in ((db.session.get(M.Client, 1).modules_actifs or {}).items()) if v}
from egalyx.modules_client import MODULES
coches = sorted((actuels or set(MODULES) - {'carto_processus', 'analyse_donnees'}) | {'formation_conformite'})
r = appel(sa, 'post', '/super-admin/client/1/modules', data={'csrf_token': jeton(sa, '/super-admin/client/1/modules'), 'modules': coches})
with A.app.app_context():
    verif('super admin : module activé pour l’organisation A', fc.module_actif(1) and not fc.module_actif(2), r.status_code)

print('--- 2. Droits')
r = appel(admin, 'get', '/formation-conformite/')
verif('administrateur de l’organisation : accès à la gestion', r.status_code == 200 and 'Formations à la conformité'.encode() in r.data, r.status_code)
t = appel(admin, 'get', '/dashboard').data.decode(errors='ignore')
verif('menu : « Formations conformité » dans Conformité', 'Formations conformité' in t)
r = appel(lect, 'get', '/formation-conformite/')
verif('simple utilisateur : pas d’accès à la gestion', r.status_code == 403, r.status_code)
r = appel(lect, 'get', '/formation-conformite/module/nouveau')
verif('simple utilisateur : pas de création de module', r.status_code == 403, r.status_code)
r = appel(admin_b, 'get', '/formation-conformite/')
verif('autre organisation (module non activé) : fermé', r.status_code in (403, 404), r.status_code)
with A.app.app_context():
    u = db.session.get(M.User, ids['gestionnaire']); p = dict(u.permissions or {}); p['can_view_formation_conformite'] = True
    u.permissions = p; db.session.commit()
r = appel(gest, 'get', '/formation-conformite/')
verif('permission « Voir le suivi » : accès en lecture', r.status_code == 200 and b'Nouveau module' not in r.data, r.status_code)
r = appel(gest, 'get', '/formation-conformite/module/nouveau')
verif('… mais pas de création', r.status_code == 403, r.status_code)

print('--- 3. Module : contenu, quiz, publication')
QUESTIONS = [
    {'texte': 'À qui déclarer un soupçon de blanchiment ?', 'choix': ['À la CENTIF', 'Au client', 'À personne'], 'bonnes': [0],
     'explication': 'La déclaration de soupçon se fait auprès de la cellule de renseignement financier.'},
    {'texte': 'Quels éléments font partie de la connaissance client ?', 'choix': ['Identité', 'Bénéficiaire effectif', 'Couleur préférée'],
     'bonnes': [0, 1]},
]
r = appel(admin, 'post', '/formation-conformite/module/nouveau', data={
    'csrf_token': jeton(admin, '/formation-conformite/module/nouveau'), 'titre': 'LCB-FT : les bases', 'categorie': 'lcb_ft',
    'resume': 'Reconnaître une opération suspecte.', 'duree_minutes': '20', 'score_min': '100',
    'contenu': "## Pourquoi\nLe blanchiment **finance** le crime.\n\n- point un\n- point deux\n\n<script>alert(1)</script>",
    'video_url': 'https://www.youtube.com/watch?v=dQw4w9WgXcQ', 'questions_json': json.dumps(QUESTIONS), 'action': 'publier'})
with A.app.app_context():
    mod = M.ModuleFormationConformite.query.filter_by(client_id=1).first()
    verif('module créé, publié, quiz de 2 questions', mod is not None and mod.statut == 'publie' and len(mod.questions) == 2
          and mod.questions[1]['bonnes'] == [0, 1], r.status_code)
    MID = mod.id
r = appel(admin, 'post', '/formation-conformite/module/nouveau', data={
    'csrf_token': jeton(admin, '/formation-conformite/module/nouveau'), 'titre': 'Incomplet', 'contenu': 'x',
    'questions_json': json.dumps([{'texte': 'Q ?', 'choix': ['a', 'b'], 'bonnes': []}]), 'action': 'enregistrer'})
verif('question sans bonne réponse : refusée avec un message clair', 'cochez au moins une bonne réponse'.encode() in r.data)
r = appel(admin, 'post', '/formation-conformite/module/nouveau', data={
    'csrf_token': jeton(admin, '/formation-conformite/module/nouveau'), 'titre': 'Vidéo douteuse', 'contenu': 'x',
    'video_url': 'javascript:alert(1)', 'questions_json': '[]', 'action': 'enregistrer'})
verif('lien de vidéo non https : refusé', 'doit commencer par https://'.encode() in r.data)
r = appel(admin, 'get', f'/formation-conformite/module/{MID}/apercu')
t = r.data.decode(errors='ignore')
verif('aperçu : texte mis en forme (chapitre, gras, liste)', r.status_code == 200 and 'tabindex="-1">Pourquoi</h2>' in t
      and '<strong>finance</strong>' in t and '<li>point un</li>' in t)
verif('aperçu : HTML du contenu neutralisé (pas de script injecté)', '<script>alert(1)</script>' not in t and '&lt;script&gt;' in t)
verif('aperçu : vidéo YouTube intégrée en mode sans cookies', 'youtube-nocookie.com/embed/dQw4w9WgXcQ' in t)
verif('aperçu : les bonnes réponses ne sont pas révélées', 'bonne réponse' not in t and 'cellule de renseignement' not in t)
verif('vidéo Vimeo reconnue, autre site affiché en lien', fc.video_integree('https://vimeo.com/123456789') == 'https://player.vimeo.com/video/123456789'
      and fc.video_integree('https://exemple.com/v.mp4') is None)
verif('notation : exactement les bonnes réponses', fc.noter(QUESTIONS, {0: {0}, 1: {0, 1}}) == (100, [True, True])
      and fc.noter(QUESTIONS, {0: {0}, 1: {0}}) == (50, [True, False]) and fc.noter([], {}) == (100, []))

print('--- 4. Campagne')
with A.app.app_context():
    cibles = [ids['lecteur'], ids['operateur']]
r = appel(admin, 'post', '/formation-conformite/campagne/nouvelle', data={
    'csrf_token': jeton(admin, '/formation-conformite/campagne/nouvelle'), 'module_id': str(MID), 'titre': 'LCB-FT 2026',
    'date_limite': (date.today() + timedelta(days=30)).isoformat(), 'cible_type': 'utilisateurs',
    'cible_utilisateurs': [str(x) for x in cibles]})
with A.app.app_context():
    c = M.CampagneFormationConformite.query.filter_by(client_id=1).first()
    aff = M.AffectationFormationConformite.query.filter_by(campagne_id=c.id).all() if c else []
    notifs = M.Notification.query.filter_by(entite_type='formation_campagne').count()
    verif('campagne lancée : 2 personnes, 2 notifications', c is not None and sorted(a.user_id for a in aff) == sorted(cibles)
          and notifs == 2, (r.status_code, len(aff), notifs))
    KID = c.id
    AID = next(a.id for a in aff if a.user_id == ids['lecteur'])
    AID_OP = next(a.id for a in aff if a.user_id == ids['operateur'])
r = appel(admin, 'post', '/formation-conformite/campagne/nouvelle', data={
    'csrf_token': jeton(admin, '/formation-conformite/campagne/nouvelle'), 'module_id': str(MID),
    'date_limite': (date.today() - timedelta(days=1)).isoformat(), 'cible_type': 'tous'})
verif('date limite passée : refusée', 'déjà passée'.encode() in r.data)
r = appel(admin, 'post', '/formation-conformite/campagne/nouvelle', data={
    'csrf_token': jeton(admin, '/formation-conformite/campagne/nouvelle'), 'module_id': str(MID), 'cible_type': 'roles'})
verif('cible « rôles » sans rôle coché : refusée', 'au moins une direction, un rôle ou une personne'.encode() in r.data)
r = appel(admin, 'get', f'/formation-conformite/campagne/{KID}')
verif('suivi de campagne : 2 personnes, 0 validé', r.status_code == 200 and b'Suivi par personne' in r.data and '0 %'.encode() in r.data)
r = appel(gest, 'get', f'/formation-conformite/campagne/{KID}')
verif('lecture seule : suivi visible sans bouton de relance', r.status_code == 200 and 'Relancer'.encode() not in r.data)
r = appel(gest, 'post', f'/formation-conformite/campagne/{KID}/action', data={'csrf_token': jeton(gest, f'/formation-conformite/campagne/{KID}'), 'action': 'relancer'})
verif('lecture seule : relance refusée', r.status_code == 403, r.status_code)
r = appel(admin_b, 'get', f'/formation-conformite/campagne/{KID}')
verif('autre organisation : campagne invisible', r.status_code in (403, 404), r.status_code)

print('--- 5. Mes formations (participant)')
t = appel(lect, 'get', '/dashboard').data.decode(errors='ignore')
verif('menu du participant : « Mes formations » avec 1 à faire', 'Mes formations' in t and 'aria-label="1 à suivre"' in t)
r = appel(lect, 'get', '/formation-conformite/mes-formations')
verif('« Mes formations » : la campagne et le bouton Commencer', r.status_code == 200 and b'LCB-FT 2026' in r.data and b'Commencer' in r.data, r.status_code)
r = appel(lect, 'get', f'/formation-conformite/suivre/{AID_OP}')
verif('formation d’une autre personne : inaccessible', r.status_code == 404, r.status_code)
r = appel(lect, 'get', f'/formation-conformite/suivre/{AID}')
t = r.data.decode(errors='ignore')
with A.app.app_context():
    verif('ouvrir la formation : statut « Commencé »', db.session.get(M.AffectationFormationConformite, AID).statut == 'en_cours')
verif('quiz affiché sans les bonnes réponses', r.status_code == 200 and 'Valider mes réponses' in t and 'bonne réponse' not in t
      and 'cellule de renseignement' not in t)
r = appel(lect, 'post', f'/formation-conformite/suivre/{AID}', data={'csrf_token': jeton(lect, f'/formation-conformite/suivre/{AID}'), 'q0': '0'})
verif('réponse manquante : demandée avant de noter', 'Répondez à toutes les questions'.encode() in r.data)
r = appel(lect, 'post', f'/formation-conformite/suivre/{AID}', data={'csrf_token': jeton(lect, f'/formation-conformite/suivre/{AID}'),
                                                                     'q0': '0', 'q1': '0'})
t = r.data.decode(errors='ignore')
with A.app.app_context():
    a = db.session.get(M.AffectationFormationConformite, AID)
    verif('50 % pour un minimum de 100 % : non validé, tentative comptée', a.statut == 'en_cours' and a.tentatives == 1 and a.dernier_score == 50)
verif('résultat : « Pas encore validée », question à revoir signalée, réponses toujours cachées',
      'Presque : encore un effort' in t and 'À revoir' in t and 'bonne réponse' not in t)
r = appel(lect, 'post', f'/formation-conformite/suivre/{AID}', data={'csrf_token': jeton(lect, f'/formation-conformite/suivre/{AID}'),
                                                                     'q0': '0', 'q1': ['0', '1']})
t = r.data.decode(errors='ignore')
with A.app.app_context():
    a = db.session.get(M.AffectationFormationConformite, AID)
    verif('100 % : validé, horodaté, version du module notée', a.statut == 'reussi' and a.reussi_le is not None and a.meilleur_score == 100
          and a.version_module == 1 and a.tentatives == 2 and len(a.historique) == 2)
verif('après validation : bonnes réponses et explications visibles', 'formation validée' in t.lower() and 'bonne réponse' in t
      and 'cellule de renseignement' in t)
r = appel(admin, 'get', f'/formation-conformite/campagne/{KID}')
verif('suivi : 1 validé sur 2 (50 %)', '1 (50 %)'.encode() in r.data)
with A.app.app_context():
    avant = M.Notification.query.filter_by(entite_type='formation_campagne').count()
r = appel(admin, 'post', f'/formation-conformite/campagne/{KID}/action', data={'csrf_token': jeton(admin, f'/formation-conformite/campagne/{KID}'), 'action': 'relancer'})
with A.app.app_context():
    apres = M.Notification.query.filter_by(entite_type='formation_campagne').count()
    verif('relance : seulement la personne qui n’a pas validé', apres - avant == 1 and db.session.get(M.CampagneFormationConformite, KID).derniere_relance)

print('--- 6. Export, versions, clôture')
r = appel(admin, 'get', f'/formation-conformite/campagne/{KID}/export.xlsx')
ok = r.status_code == 200 and r.data[:2] == b'PK'
if ok:
    from openpyxl import load_workbook
    ws = load_workbook(io.BytesIO(r.data)).active
    valeurs = [[c.value for c in ligne] for ligne in ws.iter_rows()]
    ok = any(v and v[0] == 'Taux de réalisation' and v[1] == '50 %' for v in valeurs) and any('Validé' in [str(x) for x in v] for v in valeurs)
verif('export Excel : taux, statut et dates par personne', ok, r.status_code)
r = appel(admin, 'post', f'/formation-conformite/module/{MID}', data={
    'csrf_token': jeton(admin, f'/formation-conformite/module/{MID}'), 'titre': 'LCB-FT : les bases', 'categorie': 'lcb_ft',
    'duree_minutes': '20', 'score_min': '100', 'contenu': 'Contenu mis à jour', 'questions_json': json.dumps(QUESTIONS), 'action': 'enregistrer'})
with A.app.app_context():
    verif('modifier un module publié : version 2, la validation passée garde la version 1',
          db.session.get(M.ModuleFormationConformite, MID).version == 2
          and db.session.get(M.AffectationFormationConformite, AID).version_module == 1)
r = appel(admin, 'post', f'/formation-conformite/module/{MID}/etat', data={'csrf_token': jeton(admin, f'/formation-conformite/module/{MID}'), 'action': 'supprimer'})
with A.app.app_context():
    verif('module utilisé par une campagne : suppression refusée (preuves conservées)', db.session.get(M.ModuleFormationConformite, MID) is not None)
r = appel(admin, 'post', f'/formation-conformite/campagne/{KID}/action', data={'csrf_token': jeton(admin, f'/formation-conformite/campagne/{KID}'), 'action': 'clore'})
r2 = appel(oper, 'get', f'/formation-conformite/suivre/{AID_OP}')
r3 = appel(lect, 'get', f'/formation-conformite/suivre/{AID}')
verif('campagne close : la personne non validée ne peut plus la suivre, la personne validée garde sa preuve',
      r2.status_code == 404 and r3.status_code == 200 and b'Formation valid' in r3.data, (r2.status_code, r3.status_code))
r = appel(oper, 'get', '/dashboard')
verif('campagne close : plus de « Mes formations » pour la personne non validée', 'Mes formations'.encode() not in r.data)

print('--- 7. Module sans quiz : « J’ai lu et compris »')
r = appel(admin, 'post', '/formation-conformite/module/nouveau', data={
    'csrf_token': jeton(admin, '/formation-conformite/module/nouveau'), 'titre': 'Charte éthique', 'categorie': 'ethique',
    'contenu': 'Lisez la charte.', 'questions_json': '[]', 'action': 'publier'})
with A.app.app_context():
    mid2 = M.ModuleFormationConformite.query.filter_by(client_id=1, titre='Charte éthique').first().id
r = appel(admin, 'post', '/formation-conformite/campagne/nouvelle', data={
    'csrf_token': jeton(admin, '/formation-conformite/campagne/nouvelle'), 'module_id': str(mid2), 'cible_type': 'roles',
    'cible_roles': ['utilisateur']})
with A.app.app_context():
    c2 = M.CampagneFormationConformite.query.filter_by(client_id=1, module_id=mid2).first()
    a2 = M.AffectationFormationConformite.query.filter_by(campagne_id=c2.id, user_id=ids['operateur']).first()
    nb = M.AffectationFormationConformite.query.filter_by(campagne_id=c2.id).count()
    vis_b = M.AffectationFormationConformite.query.filter_by(campagne_id=c2.id, user_id=ids['admin_b']).count()
verif('cible « rôle utilisateur » : uniquement des personnes de l’organisation', nb >= 2 and vis_b == 0 and a2 is not None, nb)
r = appel(oper, 'get', f'/formation-conformite/suivre/{a2.id}')
verif('bouton « J’ai lu et compris »', r.status_code == 200 and 'J&#39;ai lu et compris'.encode() in r.data or 'J\'ai lu et compris'.encode() in r.data)
r = appel(oper, 'post', f'/formation-conformite/suivre/{a2.id}/sans-quiz', data={'csrf_token': jeton(oper, f'/formation-conformite/suivre/{a2.id}')})
with A.app.app_context():
    verif('lecture validée et horodatée', db.session.get(M.AffectationFormationConformite, a2.id).statut == 'reussi')

print('--- 8. Super admin et journal')
r = appel(sa, 'get', '/formation-conformite/?client_id=1')
verif('super admin : gestion de l’organisation consultée', r.status_code == 200 and b'LCB-FT 2026' in r.data, r.status_code)
with A.app.app_context():
    actions = {j.action for j in M.JournalActiviteClient.query.filter(M.JournalActiviteClient.action.like('formation_%'))}
    verif('journal : création, campagne, quiz, relance, export, clôture', {'formation_module_enregistre', 'formation_campagne_lancee', 'formation_quiz',
          'formation_campagne_relance', 'formation_campagne_export', 'formation_campagne_close'} <= actions, sorted(actions))

print(f'\n{sum(res)}/{len(res)} vérifications réussies')
