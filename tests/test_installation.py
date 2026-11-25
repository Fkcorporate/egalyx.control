"""egalyx/installation.py : création du premier super administrateur et contrôle de l'installation (on-premise)."""
import pytest

from test_v4_parcours import contexte  # noqa: F401,E402


@pytest.fixture()
def app_cli(contexte):  # noqa: F811
    app, c, d = contexte
    from egalyx import installation
    installation.enregistrer(app)
    import models
    if not hasattr(models.User, 'set_password'):                 # double simplifié de models.User : règles du vrai modèle
        from werkzeug.security import check_password_hash, generate_password_hash

        def set_password(self, mdp, check_history=True):
            if len(mdp) < 12 or mdp.lower() == mdp or not any(ch.isdigit() for ch in mdp):
                raise ValueError('mot de passe trop faible')
            self.password_hash = generate_password_hash(mdp)
        models.User.set_password = set_password
        models.User.check_password = lambda self, mdp: check_password_hash(self.password_hash, mdp)
    return app, d


def test_creer_super_admin(app_cli):
    app, d = app_cli
    import models
    r = app.test_cli_runner().invoke(args=['creer-super-admin', '--identifiant', 'installateur', '--email', 'it@client.ci'],
                                     input='faible\nfaible\nEgalyx!Serveur2026\nEgalyx!Serveur2026\n')   # 1er refusé
    assert 'Refusé' in r.output
    assert r.exit_code == 0, r.output
    u = models.User.query.filter_by(username='installateur').first()
    assert u is not None and u.role == 'super_admin' and u.check_password('Egalyx!Serveur2026')
    # un second compte au même nom est refusé
    r2 = app.test_cli_runner().invoke(args=['creer-super-admin', '--identifiant', 'installateur', '--email', 'autre@client.ci'],
                                      input='Egalyx!Serveur2026\nEgalyx!Serveur2026\n')
    assert r2.exit_code == 2 and 'existe déjà' in r2.output


def test_verifier_installation_signale_les_manques(app_cli, monkeypatch):
    app, d = app_cli
    monkeypatch.delenv('EGALYX_PRODUCTION', raising=False)
    monkeypatch.delenv('RENDER', raising=False)
    r = app.test_cli_runner().invoke(args=['verifier-installation'])
    assert r.exit_code == 1                                   # hors production : point bloquant signalé
    assert 'Mode production INACTIF' in r.output and 'Base de données' in r.output and 'SECRET_KEY' in r.output
