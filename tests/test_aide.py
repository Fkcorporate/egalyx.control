"""Centre d'aide (egalyx/aide.py, egalyx/aide_contenu.py) : contenu, recherche, droits, pages."""
import os
import re
import sys

import pytest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)
sys.path.insert(0, os.path.join(RACINE, 'tests', 'stubs'))

import models  # noqa: E402  (double)
from egalyx import aide, aide_contenu  # noqa: E402

# Question telle qu'un client la poserait → fiche attendue
QUESTIONS = [
    ("j'ai oublié mon mot de passe", 'mot_de_passe_oublie'),
    ('mdp oublié', 'mot_de_passe_oublie'),
    ('comment changer mon mot de passe', 'mot_de_passe_changer'),
    ('mon compte est bloqué', 'compte_bloque'),
    ("je n'arrive pas à me connecter", 'compte_bloque'),
    ('comment activer la double authentification', 'double_auth_activer'),
    ("j'ai changé de téléphone et mon code 2FA ne marche plus", 'double_auth_perdu'),
    ('codes de secours perdus', 'double_auth_perdu'),
    ('se connecter avec son compte Microsoft', 'sso'),
    ('je ne vois pas le module audit', 'module_absent'),
    ('accès refusé quand je modifie', 'acces_refuse'),
    ('page introuvable 404', 'introuvable'),
    ("j'ai une erreur 500", 'erreur_500'),
    ("l'application est très lente", 'lenteur'),
    ('je ne reçois pas les mails', 'email_non_recu'),
    ('comment ajouter un utilisateur', 'utilisateur_creer'),
    ('donner les droits sur un module à un collègue', 'permissions_modifier'),
    ('comment fonctionnent les permissions', 'roles'),
    ('créer une filiale', 'organisation'),
    ('changer les seuils de criticité', 'parametres_risque'),
    ('définir notre appétence au risque', 'parametres_risque'),
    ('que faire des risques hors appétence', 'appetence'),
    ('comment créer une cartographie', 'cartographie_creer'),
    ('importer des risques types pour une banque', 'bibliotheque'),
    ('évaluation triphasée', 'evaluation_triphasee'),
    ('différence entre risque brut et net', 'cotation'),
    ('pourquoi mon risque est critique', 'cotation'),
    ('ajouter un dispositif de maîtrise à un risque', 'dispositif_creer'),
    ('créer un KRI', 'kri_creer'),
    ('comment saisir une mesure de KRI', 'kri_mesure'),
    ('comment déclarer un incident', 'incident_declarer'),
    ("escalade d'un incident", 'incident_suivi'),
    ('comment dessiner un processus', 'logigramme'),
    ('lancer une campagne de contrôle', 'campagne'),
    ('valider une planification C2N', 'c2n_planification'),
    ('traiter une non-conformité', 'c2n_nc'),
    ('créer un questionnaire', 'questionnaires'),
    ("construire le programme d'audit annuel", 'programme_audit'),
    ("comment lancer une mission d'audit", 'audit_lancer'),
    ('saisir une constatation', 'constatation'),
    ("valider le rapport d'audit", 'rapport_audit'),
    ("mettre à jour l'avancement d'un plan d'action", 'plan_suivi'),
    ("créer un plan d'action", 'plan_creer'),
    ('ajouter un texte réglementaire', 'veille'),
    ('niveau de vigilance LCB-FT', 'tiers_creer'),
    ('cribler un client contre les listes de sanctions', 'tiers_criblage'),
    ('faire un signalement anonyme', 'alerte_deposer'),
    ('signer un document', 'signature'),
    ('créer un plan de continuité', 'pca_creer'),
    ('rapport pour le comité d’audit', 'rapport_comite'),
    ('exporter en Excel', 'export'),
    ('comment imprimer en PDF', 'imprimer'),
    ('les boutons IA ont disparu', 'ia_absente'),
    ('payer par Orange Money', 'paiement'),
    ('connecter notre ERP par API', 'api'),
    ('contacter le support', 'support'),
    ('où voir mes notifications', 'notifications'),
    ('qu est-ce qui m attend cette semaine', 'ma_semaine'),
    ('par où commencer', 'premiere_connexion'),
]


class U:
    def __init__(self, role='utilisateur', droits=None, admin=False, connecte=True):
        self.role, self.is_client_admin, self.is_authenticated = role, admin, connecte
        self.droits = droits
        self.username = 'u'

    def has_permission(self, p):
        return self.droits is None or p in self.droits


@pytest.fixture()
def app(monkeypatch):
    monkeypatch.setenv('EGALYX_2FA_OBLIGATOIRE_ADMINS', '0')
    from test_v4_parcours import fabriquer_app
    a = fabriquer_app()
    for ep in ('liste_cartographies', 'nouvelle_cartographie', 'liste_incidents', 'nouveau_ticket_support',
               'liste_tickets_support', 'client_admin_utilisateurs', 'forgot_password'):
        a.add_url_rule('/' + ep, ep, lambda: 'page')
    aide.enregistrer(a)
    models.User._registre.clear(); models.Client._registre.clear()
    models.db.session.add(models.Client(id=1, nom='ACME', reference='ACME'))
    models.db.session.add(models.User(id=1, username='sa', email='s', role='super_admin'))
    models.db.session.add(models.User(id=2, username='ana', email='a', role='admin', client_id=1, is_client_admin=True))
    models.db.session.add(models.User(id=3, username='paul', email='p', role='utilisateur', client_id=1, droits={'can_view_dashboard'}))
    return a


def test_contenu_coherent():
    ids = [a['id'] for a in aide_contenu.ARTICLES]
    assert len(ids) == len(set(ids)), 'identifiants en double'
    cats = {c[0] for c in aide_contenu.CATEGORIES}
    for a in aide_contenu.ARTICLES:
        assert a['cat'] in cats, a['id']
        assert a['pour'] in ('tous', 'admin', 'super_admin', 'public'), a['id']
        assert a['resume'] and a['mots'], a['id']
        assert '<' not in ''.join([a['titre'], a['resume']] + a['etapes'] + a['notes']), 'pas de HTML : ' + a['id']
    assert len(aide_contenu.ARTICLES) >= 70 and len(aide_contenu.GLOSSAIRE) >= 25
    for c in cats:
        assert any(a['cat'] == c for a in aide_contenu.ARTICLES), 'catégorie vide : ' + c


def test_endpoints_des_liens_existent():
    """Chaque lien de fiche vise une route réellement déclarée dans l'application."""
    src = open(os.path.join(RACINE, 'app.py'), encoding='utf-8').read()
    fonctions = set(re.findall(r'^def ([a-z_0-9]+)\(', src, re.M))
    blueprints = {}
    for f in os.listdir(os.path.join(RACINE, 'egalyx')):
        if f.endswith('.py'):
            t = open(os.path.join(RACINE, 'egalyx', f), encoding='utf-8').read()
            for nom in re.findall(r"Blueprint\('([a-z_]+)'", t):
                blueprints.setdefault(nom, set()).update(re.findall(r'^def ([a-z_0-9]+)\(', t, re.M))
                blueprints[nom].update(re.findall(r'^    def ([a-z_0-9]+)\(', t, re.M))
    externes = {'notifications.liste_notifications'}      # blueprint du projet hôte, déjà utilisé par base.html
    for a in aide_contenu.ARTICLES:
        for _lib, ep in a['liens']:
            if ep in externes:
                continue
            if '.' in ep:
                bp, vue = ep.split('.')
                assert vue in blueprints.get(bp, set()), f"{a['id']} : {ep}"
            else:
                assert ep in fonctions, f"{a['id']} : {ep}"


@pytest.mark.parametrize('question,attendu', QUESTIONS)
def test_questions_clients(app, question, attendu):
    with app.test_request_context():
        res = aide.chercher(question, U(droits=None, admin=True, role='admin'), n=3)
    assert res and res[0][1]['id'] == attendu, (question, [(s, a['id']) for s, a in res])
    assert res[0][0] >= aide.SEUIL_REPONSE


@pytest.mark.parametrize('question', ['quelle est la météo demain', 'recette du poulet yassa', 'qui a gagné le match'])
def test_hors_sujet_pas_de_reponse(app, question):
    with app.test_request_context():
        assert aide.repondre(question, U()) is None


def test_visibilite_et_droits(app):
    anonyme = U(connecte=False)
    paul = U(droits={'can_view_dashboard'})
    sa = U(role='super_admin')
    with app.test_request_context():
        assert all(a['pour'] == 'public' for _s, a in aide.chercher('mot de passe 2fa signalement', anonyme, n=10))
        assert not any(a['pour'] == 'super_admin' for _s, a in aide.chercher('créer un client modules', paul, n=10))
        assert aide.chercher('sauvegardes base de données', sa, n=1)[0][1]['id'] == 'sa_sauvegardes'
        rep = aide.repondre('comment déclarer un incident', paul)
        assert rep and '🔒' in rep['texte'] and not any('/liste_incidents' in a['url'] for a in rep['actions'])
        rep = aide.repondre('comment déclarer un incident', U(droits={'can_manage_incidents'}))
        assert '🔒' not in rep['texte'] and any(a['url'] == '/liste_incidents' for a in rep['actions'])
        rep = aide.repondre('comment ajouter un utilisateur', paul)
        assert 'administrateur' in rep['texte']


def test_reponse_assistant_format(app):
    with app.test_request_context():
        rep = aide.repondre("j'ai oublié mon mot de passe", U())
    assert rep['intention'] == 'base_connaissances' and rep['article'] == 'mot_de_passe_oublie'
    assert rep['texte'].startswith('**') and '\n1. ' in rep['texte']
    assert any(a['url'].startswith('/aide/fiche/') for a in rep['actions'])
    assert all(a['url'].startswith('/') for a in rep['actions'])


def test_pages(app):
    c = app.test_client()
    r = c.get('/aide/')                                           # visiteur : fiches publiques seulement
    assert r.status_code == 200 and 'oublié mon mot de passe' in r.text and 'Créer un utilisateur' not in r.text
    assert c.get('/aide/fiche/utilisateur_creer').status_code == 404
    assert c.get('/aide/fiche/mot_de_passe_oublie').status_code == 200
    c.get('/_connexion/3')
    r = c.get('/aide/?q=d%C3%A9clarer+un+incident')
    assert r.status_code == 200 and 'Déclarer un incident' in r.text
    r = c.get('/aide/fiche/incident_declarer')
    assert r.status_code == 200 and 'ad-verrou' in r.text           # paul n'a pas le module : la fiche le dit
    assert c.get('/aide/fiche/sa_demo').status_code == 404         # fiche super admin
    g = c.get('/aide/guide-complet')
    assert g.status_code == 200 and 'Glossaire' in g.text and 'Sahel Finance' not in g.text
    j = c.get('/aide/api/chercher?q=kri').get_json()
    assert j['resultats'] and j['resultats'][0]['url'].startswith('/aide/fiche/')
    c2 = app.test_client(); c2.get('/_connexion/1')
    assert 'Sahel Finance' in c2.get('/aide/guide-complet').text


def test_echappement(app):
    with app.test_request_context():
        from markupsafe import Markup
        assert aide._rendu('**gras** <script>') == Markup('<strong>gras</strong> &lt;script&gt;')
