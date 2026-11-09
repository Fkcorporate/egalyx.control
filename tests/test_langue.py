"""Bascule français / anglais (egalyx/langue.py)."""
import os
import sys

import pytest
from flask import jsonify

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)
sys.path.insert(0, os.path.join(RACINE, 'tests', 'stubs'))

import models  # noqa: E402,F401  (double)
from egalyx import langue  # noqa: E402

PAGE = ('<!DOCTYPE html><html lang="fr"><head><title>Tableau de bord</title></head><body>'
        '<h1>Tableau de bord</h1><p>  Risques critiques : </p><input placeholder="Rechercher">'
        '<button type="submit" value="Enregistrer">Annuler</button>'
        '<script>var x = "Tableau de bord";</script><div translate="no"><b>Tableau de bord</b></div>'
        '<p>Build the team</p><p>Plans d&#39;action</p><p>12 risque(s)</p><p>Texte libre inconnu</p>'
        '</body></html>')


@pytest.fixture()
def app(monkeypatch):
    monkeypatch.setenv('EGALYX_2FA_OBLIGATOIRE_ADMINS', '0')
    from test_v4_parcours import fabriquer_app
    a = fabriquer_app()
    a.add_url_rule('/page', 'page_test', lambda: PAGE)
    a.add_url_rule('/api/msg', 'api_msg', lambda: jsonify(success=False, error='Accès refusé'))
    langue.enregistrer(a)
    return a


def test_dictionnaire_charge():
    nb_en, nb_fr = langue.charger()
    assert nb_en > 9000 and nb_fr > 400
    for ligne in open(os.path.join(langue.DOSSIER, 'fr_en.tsv'), encoding='utf-8'):
        if ligne.startswith('#'):
            continue
        a, b = ligne.rstrip('\n').split('\t')
        assert a.count('{}') == b.count('{}'), a


def test_traduction_exacte_jamais_partielle(app):
    with app.test_request_context():
        assert langue.traduire('Tableau de bord', 'en') == 'Dashboard'
        assert langue.traduire('TABLEAU DE BORD', 'en') == 'DASHBOARD'
        assert langue.traduire('3. Risque :', 'en') == '3. Risk:'
        assert langue.traduire('12 risque(s)', 'en') == '12 risk(s)'
        assert langue.traduire('Risque inventé par un client', 'en') == 'Risque inventé par un client'   # rien de partiel
        assert langue.traduire('Build the team', 'fr') == "Constituer l'équipe"                       # restes d'anglais
        assert langue.traduire('Tableau de bord', 'fr') == 'Tableau de bord'


def test_bascule_et_retour_sur_la_page(app):
    c = app.test_client()
    r = c.get('/langue/en?suivant=/page%3Flang%3Dfr%26x%3D1')
    assert r.status_code == 302 and r.headers['Location'].endswith('/page?x=1')
    assert 'lang=en' in r.headers.get('Set-Cookie', '')
    html = c.get('/page').text
    assert '<html lang="en">' in html and '<h1>Dashboard</h1>' in html
    assert '  Critical risks: ' in html and 'placeholder="Search"' in html
    assert 'value="Save"' in html and '>Cancel</button>' in html
    assert 'var x = "Tableau de bord";' in html and '<b>Tableau de bord</b>' in html     # script et translate="no"
    assert 'Action plans' in html and '12 risk(s)' in html and 'Texte libre inconnu' in html
    assert 'dictionnaire-en.js' in html
    # persistance : un nouveau navigateur avec le cookie seulement
    c2 = app.test_client()
    c2.set_cookie('lang', 'en')
    assert '<h1>Dashboard</h1>' in c2.get('/page').text
    # retour au français
    c.get('/langue/fr')
    html = c.get('/page').text
    assert '<html lang="fr">' in html and '<h1>Tableau de bord</h1>' in html
    assert "Constituer l&#39;équipe" in html or "Constituer l'équipe" in html


def test_retour_externe_refuse(app):
    c = app.test_client()
    r = c.get('/langue/en?suivant=https://pirate.example/x')
    assert r.headers['Location'] in ('/', 'http://localhost/')
    r = c.get('/langue/en?suivant=//pirate.example/x')
    assert 'pirate' not in r.headers['Location']
    r = c.get('/langue/xx')
    assert 'lang=fr' in r.headers.get('Set-Cookie', '')


def test_json_et_dictionnaire_navigateur(app):
    c = app.test_client()
    c.get('/langue/en')
    assert c.get('/api/msg').get_json()['error'] == 'Access denied'
    js = c.get('/langue/dictionnaire-en.js?v=1')
    assert js.status_code == 200 and 'EGALYX_DICO' in js.text and '"Tableau de bord":"Dashboard"' in js.text
    assert 'immutable' in js.headers['Cache-Control']
    assert c.get('/langue/dictionnaire-de.js').status_code == 404


def test_contexte_t(app):
    from flask import render_template_string
    c = app.test_client()
    c.get('/langue/en')
    with app.test_request_context('/', headers={'Cookie': 'lang=en'}):
        app.preprocess_request()
        assert render_template_string('{{ t("Annuler") }}|{{ current_lang }}') == 'Cancel|en'


def test_bouton_langue_dans_base():
    src = open(os.path.join(RACINE, 'templates', 'base.html'), encoding='utf-8').read()
    assert 'langue.changer' in src and "searchParams.set('lang'" not in src
    assert 'id="languageWidget" translate="no"' in src
