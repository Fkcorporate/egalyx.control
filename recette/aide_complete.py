"""Recette : le centre d'aide et l'assistant couvrent les fonctions de l'outil (dont celles de novembre 2026)."""
import os
os.environ['EGALYX_COLLECTE_AUTO'] = '0'
import sys
import socle
from socle import Muet, navigateur
res = []


def verif(nom, cond, detail=''):
    res.append(bool(cond)); print('OK   ' if cond else 'ÉCHEC', nom, detail)


with Muet():
    A, ids = socle.preparer()
app = A.app
from egalyx.aide_contenu import ARTICLES, article

print('--- Fiches')
ep = set(app.view_functions)
casses = [(a['id'], l[1]) for a in ARTICLES for l in a['liens'] if l[1] not in ep]
verif('tous les liens des fiches mènent à une page qui existe', not casses, casses)
ids_ = [a['id'] for a in ARTICLES]
verif('aucun identifiant de fiche en double', len(ids_) == len(set(ids_)))
NOUVELLES = ['plans_ou_trouver', 'plans_regles', 'plans_statuts', 'lettre_mission', 'heure_devise', 'listes_pages',
             'kri_archives', 'reevaluation', 'incident_supprimer', 'sa_reglages_organisation']
for i in NOUVELLES:
    verif(f'fiche « {i} » présente', article(i) is not None)
verif('la fiche « avancement » ne promet plus une clôture directe et renvoie aux règles',
      'automatiquement' in ' '.join(article('plan_suivi')['notes']))

print('--- Pages du centre d\'aide')
c = navigateur(A, ids['admin_a'])
for i in NOUVELLES:
    if i.startswith('sa_'):
        continue
    r = c.get(f'/aide/fiche/{i}')
    verif(f'/aide/fiche/{i} s\'affiche', r.status_code == 200, r.status_code)
verif('/aide s\'affiche', c.get('/aide/').status_code == 200)
r = c.get('/aide/fiche/sa_reglages_organisation')
verif('fiche super admin cachée à un administrateur client', r.status_code in (403, 404), r.status_code)
s = navigateur(A, ids['superadmin'])
verif('fiche super admin visible du super admin', s.get('/aide/fiche/sa_reglages_organisation').status_code == 200)

print('--- Assistant : questions d\'usage')
ATTENDU = {
    'admin_a': [('comment changer la devise de mon organisation', 'heure_devise'), ('régler le fuseau horaire', 'heure_devise'),
                ("l'heure affichée est fausse", 'heure_devise'), ('changer de monnaie FCFA', 'heure_devise'),
                ('afficher plus de lignes dans la liste', 'listes_pages'), ('restaurer des KRI archivés', 'kri_archives'),
                ('supprimer définitivement un incident', 'incident_supprimer'), ('régénérer une clé API', 'api')],
    'gestionnaire': [("mon plan d'action est terminé mais la recommandation n'est pas clôturée", 'plans_regles'),
                     ('demande de clôture recommandation', 'plans_regles'),
                     ("la progression du plan ne s'enregistre pas", 'plans_regles'),
                     ("pourquoi je ne peux pas bouger le curseur d'avancement", 'plans_regles'),
                     ("différence plan d'action audit et plan d'action risque", 'plans_ou_trouver'),
                     ("voir tous les plans d'action", 'plans_ou_trouver'),
                     ("statut d'une sous-action", 'plans_statuts'),
                     ("demande de réévaluation d'un risque", 'reevaluation'),
                     ('envoyer la lettre de mission', 'lettre_mission'),
                     ('à qui est envoyée la lettre de mission', 'lettre_mission')],
    'lecteur': [('envoyer la lettre de mission', 'lettre_mission')],
    'superadmin': [('heure et devise super admin', 'sa_reglages_organisation'),
                   ('modèle de lettre de mission par client', 'sa_reglages_organisation')],
}
for qui, qs in ATTENDU.items():
    n = navigateur(A, ids[qui])
    for q, fiche in qs:
        d = n.post('/assistant/message', json={'message': q}).get_json() or {}
        verif(f'[{qui}] « {q} » → {fiche}', d.get('article') == fiche, d.get('article') or d.get('intention'))

print('--- Assistant : les questions sur les données gardent leur réponse chiffrée')
n = navigateur(A, ids['gestionnaire'])
for q, intention in [("mes plans d'action", 'plans'), ('quels plans sont en retard', 'plans'),
                     ('mes recommandations', 'lister_recommandations'), ('mes tâches', 'mes_taches')]:
    d = n.post('/assistant/message', json={'message': q}).get_json() or {}
    verif(f'« {q} » → {intention}', d.get('intention') == intention, d.get('intention'))

print('--- Banque de questions (recette/banque_questions.py)')
import banque_questions as B
from egalyx import aide
from egalyx.aide_contenu import article
from models import User
from flask_login import login_user
for qui, serie, nom in [('admin_a', B.ADMIN, 'ADMIN'), ('operateur', B.OPERATEUR, 'OPERATEUR'), ('superadmin', B.SUPER_ADMIN, 'SUPER_ADMIN')]:
    with app.test_request_context('/'):
        u = A.db.session.get(User, ids[qui]); login_user(u)
        bons = sum(1 for q, att in serie if (lambda r: r and r[0][1]['id'] in att)(aide.chercher(q, u, 1)))
    verif(f'série {nom} : première fiche juste ≥ 97 %', bons >= 0.97 * len(serie), f'{bons}/{len(serie)}')
with app.test_request_context('/'):
    u = A.db.session.get(User, ids['admin_a']); login_user(u)
    neuves = B.CONTROLE + B.NEUVES
    dans3 = sum(1 for q, att in neuves if {a['id'] for s, a in aide.chercher(q, u, 3)} & set(att))
verif('questions jamais vues : la bonne fiche parmi les 3 proposées ≥ 85 %', dans3 >= 0.85 * len(neuves), f'{dans3}/{len(neuves)}')

print('--- Assistant de bout en bout sur des questions jamais vues')
A.ASSISTANT_LIMITE_MESSAGES = 10 ** 6
n = navigateur(A, ids['admin_a'])
juste = propose = faux = 0
for q, att in B.CONTROLE + B.NEUVES:
    d = n.post('/assistant/message', json={'message': q}).get_json() or {}
    if d.get('article'):
        juste += d['article'] in att; faux += d['article'] not in att
    elif d.get('intention') == 'incompris' and {article(x)['titre'] for x in att} & set(d.get('suggestions') or []):
        propose += 1
tot = len(B.CONTROLE + B.NEUVES)
verif('bonne fiche donnée ou proposée (« Vouliez-vous dire ») ≥ 80 %', juste + propose >= 0.80 * tot, f'{juste} + {propose} / {tot}')
verif('réponses fausses données avec assurance ≤ 8 %', faux <= 0.08 * tot, f'{faux}/{tot}')
for q, intention in [('dispositifs peu efficaces', 'lister_dispositifs'), ('combien de risques critiques', 'risques'),
                     ('incidents ouverts', 'incidents'), ('audits en cours', 'audits'), ('kri en alerte', 'kri'),
                     ('fais moi un point sur ma situation', 'synthese')]:
    d = n.post('/assistant/message', json={'message': q}).get_json() or {}
    verif(f'données : « {q} » → {intention}', d.get('intention') == intention, d.get('intention'))

print(f'\n{sum(res)}/{len(res)} vérifications réussies')
sys.exit(0 if all(res) else 1)
