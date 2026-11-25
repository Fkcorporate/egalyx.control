"""egalyx/securite.py : outils de débogage fermés en production, limite de connexion par adresse IP, en-têtes."""
import pytest

from test_v4_parcours import contexte  # noqa: F401,E402


@pytest.fixture()
def app_prod(contexte, monkeypatch):  # noqa: F811
    app, c, d = contexte
    monkeypatch.setenv('EGALYX_2FA_OBLIGATOIRE_ADMINS', '0')
    from egalyx import securite
    securite._essais.clear()
    securite.enregistrer(app)
    app.add_url_rule('/debug/essai', 'debug_essai', lambda: 'outil')
    app.add_url_rule('/api/feuille-travail/test/<int:i>', 'ft_test', lambda i: 'test d audit')   # fonction normale
    from flask import redirect, request
    # connexion d'essai : mot de passe « bon » → redirection (réussite), sinon page réaffichée (échec)
    app.add_url_rule('/login', 'login_essai', lambda: redirect('/') if request.form.get('mdp') == 'bon' else 'page de connexion',
                     methods=['GET', 'POST'])
    monkeypatch.setattr(app, 'testing', False)                 # se comporter comme en production
    return app, c, d


def test_outils_debug_fermes_sauf_super_admin(app_prod):
    app, c, d = app_prod
    assert c.get('/debug/essai').status_code == 404                    # visiteur
    c.get(f"/_connexion/{d['conf'].id}")
    assert c.get('/debug/essai').status_code == 404                    # utilisateur connecté
    assert c.get('/api/feuille-travail/test/3').status_code == 200     # les vraies fonctions restent ouvertes
    c.get(f"/_connexion/{d['sa'].id}")
    assert c.get('/debug/essai').status_code == 200                    # super admin


def test_limite_de_connexion_par_adresse(app_prod):
    app, c, d = app_prod
    ip1 = {'X-Forwarded-For': '203.0.113.7, 10.0.0.1'}
    for _ in range(60):                                        # tout un bureau se connecte : jamais bloqué
        assert c.post('/login', data={'mdp': 'bon'}, headers=ip1).status_code == 302
    for _ in range(20):                                        # 20 échecs
        assert c.post('/login', data={'mdp': 'faux'}, headers=ip1).status_code == 200
    r = c.post('/login', data={'mdp': 'bon'}, headers=ip1)
    assert r.status_code == 429 and 'Trop de tentatives' in r.text and r.headers.get('Retry-After')
    assert c.post('/login', data={'mdp': 'bon'}, headers={'X-Forwarded-For': '198.51.100.4'}).status_code == 302   # autre visiteur
    assert c.get('/login', headers=ip1).status_code == 200                                     # la page reste visible


def test_entetes(app_prod):
    app, c, d = app_prod
    from egalyx.securite import _LOGIN
    assert '/auth/login_fullscreen' in _LOGIN                  # la vraie page de connexion de l'application
    r = c.get('/login')
    csp = r.headers.get('Content-Security-Policy', '')
    assert "frame-ancestors 'self'" in csp and "object-src 'none'" in csp and "base-uri 'self'" in csp
    assert 'Permissions-Policy' in r.headers and 'X-XSS-Protection' not in r.headers
