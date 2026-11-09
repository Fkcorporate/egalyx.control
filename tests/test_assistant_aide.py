"""Assistant (moteur local d'app.py) branché sur le centre d'aide et le support.

app.py n'est pas importable ici (pas de SQLAlchemy) : on extrait le moteur local du fichier
et on l'exécute avec des doubles pour ses quelques dépendances externes.
"""
import os
import re
import sys

import pytest
from flask import Flask, session

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)
sys.path.insert(0, os.path.join(RACINE, 'tests', 'stubs'))


class Utilisateur:
    is_authenticated = True
    username = 'awa'
    email = 'awa@exemple.ci'
    role = 'utilisateur'
    is_client_admin = False
    can_manage_users = False

    def __init__(self, droits=None):
        self.droits = droits

    def has_permission(self, p):
        return self.droits is None or p in self.droits


def charger_moteur(utilisateur, tickets):
    src = open(os.path.join(RACINE, 'app.py'), encoding='utf-8').read()
    debut = src.index('import unicodedata as _assistant_ud')
    fin = src.index('# IA externe OPTIONNELLE')
    code = src[debut:src.rindex('\n# ---', debut, fin)]

    def creer_ticket(sujet, description, confirme=False):
        assert confirme
        tickets.append((sujet, description))
        return {'statut': 'cree', 'reference': f'TKT-2026-{len(tickets):04d}'}

    from flask import request, url_for
    ns = {
        '__name__': 'moteur_test', 'current_user': utilisateur, 'session': session, 'request': request, 'url_for': url_for,
        'ASSISTANT_MODULES': [], '_assistant_a_acces': lambda u, perms: True,
        '_assistant_creer_ticket_support': creer_ticket,
        '_assistant_executer': lambda nom, args: {'total': 0, 'elements': [], 'acces_refuse': True},
        '_assistant_modules_accessibles': lambda u: [], 'db': None,
    }
    exec(compile(code, 'app.py[moteur]', 'exec'), ns)
    return ns


@pytest.fixture()
def env():
    from egalyx import aide
    app = Flask(__name__, template_folder=os.path.join(RACINE, 'templates'))
    app.secret_key = 'test'
    for ep in ('nouveau_ticket_support', 'liste_tickets_support', 'liste_incidents', 'liste_cartographies',
               'nouvelle_cartographie', 'profil_utilisateur', 'forgot_password', 'dashboard'):
        app.add_url_rule('/' + ep, ep, lambda: 'page')
    aide.enregistrer(app)
    tickets = []
    u = Utilisateur(droits={'can_manage_incidents', 'can_manage_risks'})
    ns = charger_moteur(u, tickets)

    def demander(question):
        rep = ns['assistant_moteur_local'](question)
        if rep is None:                       # même repli que la route /assistant/message
            rep = ns['_assistant_proposer_ticket'](question)
        return rep
    with app.test_request_context('/dashboard'):
        yield demander, tickets


@pytest.mark.parametrize('question,fiche', [
    ("j'ai perdu mon téléphone pour la double authentification", 'double_auth_perdu'),
    ('comment déclarer un incident', 'incident_declarer'),
    ('je ne vois pas le module audit', 'module_absent'),
    ("pourquoi je n'arrive pas à me connecter", 'compte_bloque'),
    ("j'ai besoin d'aide pour payer par Orange Money", 'paiement'),
    ('comment imprimer en PDF', 'imprimer'),
])
def test_reponses_du_centre_aide(env, question, fiche):
    demander, _ = env
    rep = demander(question)
    assert rep['intention'] == 'base_connaissances' and rep['article'] == fiche, rep
    assert rep['texte'].startswith('**')


def test_question_inconnue_puis_envoi_au_support(env):
    demander, tickets = env
    rep = demander('le bouton vert de la page 3 clignote bizarrement depuis hier soir')
    assert rep['intention'] == 'incompris'
    assert rep['suggestions'][0] == 'Oui, envoyer ma question au support'
    rep = demander('Oui, envoyer ma question au support')
    assert rep['intention'] == 'ticket_cree' and 'TKT-2026-0001' in rep['texte']
    assert tickets[0][0].startswith('le bouton vert') and 'awa' in tickets[0][1]
    assert demander('Oui, envoyer ma question au support')['intention'] == 'ticket_vide'    # pas de double envoi


def test_ticket_explicite_et_annulation(env):
    demander, tickets = env
    rep = demander("crée un ticket : l'export Excel des incidents est vide")
    assert rep['intention'] == 'ticket_confirmation' and "l'export Excel" in rep['texte']
    assert demander('non')['intention'] == 'ticket_annule' and not tickets
    demander("envoie au support : impossible d'ajouter une pièce jointe")
    assert demander('oui')['intention'] == 'ticket_cree' and "pièce jointe" in tickets[0][0]


def test_parler_a_un_humain(env):
    demander, _ = env
    rep = demander('je veux parler à un conseiller')
    assert rep['suggestions'] == ['Oui, envoyer ma question au support']


def test_salutation_et_aide_inchangees(env):
    demander, _ = env
    assert demander('bonjour')['intention'] == 'salut'
    assert demander('aide')['intention'] == 'aide'


def test_ia_externe_suit_l_interrupteur():
    src = open(os.path.join(RACINE, 'app.py'), encoding='utf-8').read()
    corps = re.search(r'def _assistant_ia_externe_active\(\):\n(.*?)\n\n\n', src, re.S).group(1)
    assert 'ia_autorisee' in corps
    from egalyx import ia
    assert not {'assistant_message', 'assistant_historique', 'assistant_effacer'} & set(ia.ENDPOINTS_IA)
    assert '/assistant/' not in ia.MOTIFS_ADRESSES
