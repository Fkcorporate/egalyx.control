"""Interrupteur IA (egalyx/ia.py) et palette de maîtrise."""
import os
import sys
import types

import pytest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)
sys.path.insert(0, os.path.join(RACINE, 'tests', 'stubs'))

import models  # noqa: E402  (double)


@pytest.fixture()
def app(tmp_path, monkeypatch):
    from test_v4_parcours import fabriquer_app
    from egalyx import ia, modules_client
    monkeypatch.delenv('EGALYX_IA', raising=False)
    monkeypatch.setenv('EGALYX_2FA_OBLIGATOIRE_ADMINS', '0')
    a = fabriquer_app()
    a.instance_path = str(tmp_path)
    ia._cache['mtime'] = None
    a.add_url_rule('/cartographie/<int:id>/analyse-ia-ultra', 'analyse_ia_ultra', lambda id: 'analyse')
    a.add_url_rule('/assistant/message', 'assistant_message', lambda: {'ok': True}, methods=['POST'])
    a.add_url_rule('/incident/nouveau', 'nouvel_incident', lambda: 'incident')
    a.add_url_rule('/super_admin_clients', 'super_admin_clients', lambda: 'x')
    modules_client.enregistrer(a)
    ia.enregistrer(a)
    a.jinja_env.globals['should_display_module'] = lambda p: True
    models.User._registre.clear(); models.Client._registre.clear()
    models.db.session.add(models.Client(id=1, nom='ACME', reference='ACME'))
    models.db.session.add(models.User(id=1, username='sa', email='s', role='super_admin'))
    models.db.session.add(models.User(id=2, username='ana', email='a', role='admin', client_id=1, is_client_admin=True,
                                      droits={'can_use_ia_analysis', 'can_view_dashboard'}))
    models.db.session.add(models.User(id=3, username='paul', email='p', role='utilisateur', client_id=1, droits={'can_view_dashboard'}))
    return a


def connecte(app, uid):
    c = app.test_client(); c.get(f'/_connexion/{uid}'); return c


def test_trois_conditions(app):
    from egalyx import ia
    ana, paul = connecte(app, 2), connecte(app, 3)
    assert ana.get('/cartographie/4/analyse-ia-ultra').status_code == 200
    assert paul.get('/cartographie/4/analyse-ia-ultra').status_code == 302            # pas la permission
    assert paul.post('/assistant/message', json={}).status_code == 200                # l'assistant n'est pas une fonction IA
    models.Client.query.get(1).modules_actifs = {'cartographie': True, 'ia': False}   # module IA retiré au client
    assert ana.get('/cartographie/4/analyse-ia-ultra').status_code == 302
    models.Client.query.get(1).modules_actifs = None
    with app.app_context():
        ia.ecrire_reglage('ia_active', False)                                         # coupure plateforme
    assert ana.get('/cartographie/4/analyse-ia-ultra').status_code == 302
    assert ana.post('/assistant/message', json={}).status_code == 200                 # reste disponible (centre d'aide)
    assert ana.get('/incident/nouveau').status_code == 200                            # les actions normales restent


def test_page_super_admin_et_variable(app, monkeypatch):
    from egalyx import ia
    sa = connecte(app, 1)
    r = sa.get('/super-admin/ia/')
    assert r.status_code == 200 and 'activée' in r.text
    sa.post('/super-admin/ia/', data={'ia_active': '0'})
    with app.app_context():
        assert not ia.ia_plateforme_active()
    sa.post('/super-admin/ia/', data={'ia_active': '1'})
    with app.app_context():
        assert ia.ia_plateforme_active()
    monkeypatch.setenv('EGALYX_IA', '0')
    with app.app_context():
        assert not ia.ia_plateforme_active()
    assert connecte(app, 2).get('/super-admin/ia/').status_code == 404              # réservé au super admin


def test_services_neutralises(app, monkeypatch):
    from egalyx import ia
    mod = types.ModuleType('services.incident_ia_service')

    class IncidentIAService:
        @staticmethod
        def analyser_incident(incident):
            return 'analyse'

        @classmethod
        def suggerer(cls, x):
            return 'suggestion'
    mod.IncidentIAService = IncidentIAService
    monkeypatch.setitem(sys.modules, 'services', types.ModuleType('services'))
    monkeypatch.setitem(sys.modules, 'services.incident_ia_service', mod)
    faux_app = types.ModuleType('faux_app')
    faux_app._assistant_client_openai = lambda: 'client'
    faits = ia.neutraliser_services(faux_app)
    assert 'IncidentIAService.analyser_incident' in faits and '_assistant_client_openai' in faits
    with app.app_context():
        assert IncidentIAService.analyser_incident(1) == 'analyse'                   # tâche de fond : IA active
    with app.test_request_context('/'):
        with pytest.raises(ia.IADesactivee):
            IncidentIAService.analyser_incident(1)                                    # visiteur non connecté : refusé
        ia.ecrire_reglage('ia_active', False)
        with pytest.raises(ia.IADesactivee):
            IncidentIAService.analyser_incident(1)
        with pytest.raises(ia.IADesactivee):
            IncidentIAService.suggerer(1)
        with pytest.raises(ia.IADesactivee):
            faux_app._assistant_client_openai()
    assert len(ia.neutraliser_services(faux_app)) == len(faits)                      # idempotent


def test_pages_sans_ia(app):
    from flask import render_template, session
    from egalyx import ia
    with app.test_request_context('/'):
        session['_uid'] = 2
        avec = render_template('base.html')
        ia.ecrire_reglage('ia_active', False)
        sans = render_template('base.html')
    assert 'id="egChatBtn"' in avec and 'eg-ia-masque' not in avec
    assert 'id="egChatBtn"' in sans and 'eg-ia-masque' in sans and 'analyse-ia' in sans   # assistant toujours là
    assert "'/assistant/'" not in sans


def test_couleurs_maitrise():
    import cotation
    assert cotation.couleur_maitrise(1) == '#dc2626'          # Insuffisant : rouge
    assert cotation.couleur_maitrise(5) == '#16a34a'          # Excellent : vert
    assert cotation.couleur_maitrise('3') == cotation.COULEURS_MAITRISE[3] and cotation.couleur_maitrise(None) == '#94a3b8'
    src = open(os.path.join(RACINE, 'templates', 'cartographie', 'evaluation_triphase.html'), encoding='utf-8').read()
    assert "get_niveau_couleur('maitrise', maitrise_order)" not in src
