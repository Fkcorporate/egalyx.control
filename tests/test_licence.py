"""egalyx/licence.py : clé de licence on-premise (signature, échéance, grâce, pause, page /licence)."""
import base64
import json
from datetime import date, timedelta

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from test_v4_parcours import contexte  # noqa: F401,E402


def _b64(o):
    return base64.urlsafe_b64encode(o).decode().rstrip('=')


PRIV = Ed25519PrivateKey.generate()
PUB = _b64(PRIV.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw))


def _cle(jours, client='SODEMI', priv=PRIV):
    corps = _b64(json.dumps({'client': client, 'fin': (date.today() + timedelta(days=jours)).isoformat(),
                             'utilisateurs': 25}).encode())
    return f'EGX1-{corps}.{_b64(priv.sign(corps.encode()))}'


@pytest.fixture()
def lic(contexte, monkeypatch, tmp_path):  # noqa: F811
    app, c, d = contexte
    from egalyx import licence, licence_cle
    monkeypatch.setattr(licence_cle, 'CLE_PUBLIQUE', PUB)
    monkeypatch.setenv('EGALYX_DONNEES', str(tmp_path))
    monkeypatch.delenv('EGALYX_LICENCE', raising=False)
    monkeypatch.setenv('EGALYX_2FA_OBLIGATOIRE_ADMINS', '0')
    if '/health' not in [r.rule for r in app.url_map.iter_rules()]:
        app.add_url_rule('/health', 'health', lambda: 'ok')
    licence.enregistrer(app)
    monkeypatch.setattr(licence, 'LIBRES', licence.LIBRES + ('/_connexion',))   # connexion de test = /login
    licence._cache['etat'] = None
    return app, c, d, licence, monkeypatch


def _statut(licence, cle, mp):
    mp.setenv('EGALYX_LICENCE_REQUISE', '1')
    mp.setenv('EGALYX_LICENCE', cle)
    return licence.etat(force=True)['statut']


def test_statuts(lic):
    app, c, d, licence, mp = lic
    assert _statut(licence, _cle(200), mp) == 'valide'
    assert _statut(licence, _cle(10), mp) == 'bientot'
    assert _statut(licence, _cle(-3), mp) == 'grace'
    assert _statut(licence, _cle(-20), mp) == 'expiree'
    assert _statut(licence, _cle(200, priv=Ed25519PrivateKey.generate()), mp) == 'invalide'   # pas signée par Egalyx
    falsifiee = _cle(10).replace('EGX1-', 'EGX1-x', 1)
    assert _statut(licence, falsifiee, mp) == 'invalide'


def test_rien_ne_change_sans_licence_requise(lic):
    app, c, d, licence, mp = lic
    mp.delenv('EGALYX_LICENCE_REQUISE', raising=False)
    mp.setenv('EGALYX_LICENCE', _cle(-100))                  # même expirée : ignorée (Render)
    licence._cache['etat'] = None
    c.get(f"/_connexion/{d['conf'].id}")
    assert c.get('/health').status_code == 200
    assert c.get('/licence').status_code == 404              # page réservée au super admin


def test_pause_puis_nouvelle_cle(lic):
    app, c, d, licence, mp = lic
    _statut(licence, _cle(-30), mp)
    mp.delenv('EGALYX_LICENCE')                             # la clé expirée vient du fichier
    (__import__('pathlib').Path(licence._fichier())).write_text(_cle(-30))
    licence._cache['etat'] = None
    c.get(f"/_connexion/{d['conf'].id}")
    r = c.get('/dashboard')
    assert r.status_code == 503 and 'en pause' in r.get_data(as_text=True)
    assert c.get('/health').status_code == 200
    c.get(f"/_connexion/{d['sa'].id}")
    assert c.get('/dashboard').headers['Location'].endswith('/licence')
    app.config['WTF_CSRF_ENABLED'] = False
    r = c.post('/licence', data={'cle': _cle(365)}, follow_redirects=True)
    assert 'Licence installée' in r.get_data(as_text=True)
    assert licence.etat()['statut'] == 'valide'
    r = c.post('/licence', data={'cle': 'EGX1-nimportequoi.abc'}, follow_redirects=True)
    assert 'Clé refusée' in r.get_data(as_text=True)
    assert licence.etat(force=True)['statut'] == 'valide'     # la bonne clé reste en place


def test_outil_egalyx(tmp_path, monkeypatch):
    import subprocess, sys, shutil, pathlib
    racine = pathlib.Path(__file__).resolve().parent.parent
    copie = tmp_path / 'p'
    (copie / 'egalyx').mkdir(parents=True)
    (copie / 'outils').mkdir()
    shutil.copy(racine / 'outils' / 'licence_egalyx.py', copie / 'outils')
    shutil.copy(racine / 'egalyx' / 'licence.py', copie / 'egalyx')
    (copie / 'egalyx' / '__init__.py').write_text('')
    env = dict(__import__('os').environ, EGALYX_DOSSIER_LICENCE=str(tmp_path / 'secret'))
    outil = [sys.executable, str(copie / 'outils' / 'licence_egalyx.py')]
    assert subprocess.run(outil + ['initialiser'], env=env, capture_output=True).returncode == 0
    assert "CLE_PUBLIQUE = '" in (copie / 'egalyx' / 'licence_cle.py').read_text()
    r = subprocess.run(outil + ['emettre', '--client', 'FER', '--fin', '2028-06-30', '--utilisateurs', '12'],
                       env=env, capture_output=True, text=True)
    cle = r.stdout.strip()
    assert cle.startswith('EGX1-')
    r = subprocess.run(outil + ['lire', cle], env=env, capture_output=True, text=True)
    assert 'Valide' in r.stdout and 'FER' in r.stdout and '30/06/2028' in r.stdout
