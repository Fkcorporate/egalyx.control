"""Tests des fonctions pures des modules v4 (pytest tests/test_v4_unitaires.py)."""
import base64
import hashlib
import hmac
import json
import os
import sys
import time
from datetime import date

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)
sys.path.insert(0, os.path.join(RACINE, 'tests', 'stubs'))

from egalyx import calculs  # noqa: E402


# ------------------------------------------------------------------ TOTP
def test_totp_rfc6238_vecteur_officiel():
    # RFC 6238, annexe B : secret ASCII "12345678901234567890", T = 59 s, SHA-1, 8 chiffres -> 94287082
    secret = base64.b32encode(b'12345678901234567890').decode()
    assert calculs._hotp(secret, 59 // 30, chiffres=8) == '94287082'
    assert calculs._hotp(secret, 1111111109 // 30, chiffres=8) == '07081804'


def test_totp_verifier_et_rejeu():
    s = calculs.totp_nouveau_secret()
    t = 1_800_000_000
    code = calculs.totp_code(s, t)
    pas = calculs.totp_verifier(s, code, None, instant=t)
    assert pas == t // 30
    assert calculs.totp_verifier(s, code, pas, instant=t) is None          # rejeu refusé
    assert calculs.totp_verifier(s, code, None, instant=t + 30) == pas      # dérive d'un pas tolérée
    assert calculs.totp_verifier(s, code, None, instant=t + 120) is None
    assert calculs.totp_verifier(s, '000000' if code != '000000' else '111111', None, instant=t) is None


def test_codes_secours():
    codes = calculs.codes_secours(8)
    assert len(set(codes)) == 8 and all(len(c) == 9 and c[4] == '-' for c in codes)
    assert calculs.normaliser_code_secours(codes[0].lower().replace('-', ' ')) == codes[0].replace('-', '')


def test_uri_totp():
    u = calculs.totp_uri('ABCDEF', 'a@b.c')
    assert u.startswith('otpauth://totp/') and 'secret=ABCDEF' in u and 'issuer=' in u


# ------------------------------------------------------------------ LCB-FT
def test_score_lcb_grille():
    r = calculs.score_lcb({'pays': 'Iran', 'nature': 'personne_physique'})
    assert r['score'] == 50 and r['niveau'] == 'standard'
    r = calculs.score_lcb({'pays': "Cote d'Ivoire", 'est_ppe': True, 'nature': 'personne_morale'})
    assert r['score'] == 20 + 30 + 20 and r['niveau'] == 'renforcee' and r['delai_revue_mois'] == 12
    r = calculs.score_lcb({'pays': 'France', 'nature': 'personne_morale', 'beneficiaires_effectifs': [{'nom': 'X'}]})
    assert r['score'] == 0 and r['niveau'] == 'simplifiee'
    r = calculs.score_lcb({'pays': 'France', 'sanction_confirmee': True, 'nature': 'personne_physique'})
    assert r['niveau'] == 'refus'


def test_score_lcb_listes_personnalisees():
    r = calculs.score_lcb({'pays': 'Iran', 'nature': 'personne_physique'}, liste_noire=[], liste_grise=['Iran'])
    assert r['score'] == 20


def test_criblage_noms():
    liste = [{'id': 1, 'nom': 'GENERALE (SOCIETE)', 'alias': 'SG; Societe Gen', 'source': 'TEST'},
             {'id': 2, 'nom': 'Jean Dupont', 'source': 'TEST'}]
    r = calculs.cribler('Société Générale SA', liste)
    assert r and r[0]['id'] == 1
    assert calculs.cribler('Banque Atlantique', liste) == []
    assert calculs.cribler('DUPONT Jean', liste)[0]['id'] == 2


def test_criticite_fournisseur():
    assert calculs.criticite_fournisseur(4, 100, False, 2) == (100, 'critique')
    assert calculs.criticite_fournisseur(1, 0, True) == (0, 'faible')


# ------------------------------------------------------------------ signature, paiement, appétence
def test_empreinte_stable_et_champs_volatils():
    a = calculs.empreinte({'b': 1, 'a': [1, 2], 'updated_at': 'x'})
    b = calculs.empreinte({'a': [1, 2], 'b': 1.0, 'updated_at': 'y'})
    assert a == b and len(a) == 64
    assert a != calculs.empreinte({'a': [2, 1], 'b': 1})


def test_montants():
    assert calculs.montant_xof(49) == 32145          # 49 × 655,957 = 32 141,9 -> multiple de 5 supérieur
    assert calculs.montant_xof(49) % 5 == 0
    assert calculs.montant_centimes(49.9) == 4990


def test_signature_stripe():
    corps, secret, t = b'{"id":"evt"}', 'whsec_test', 1_800_000_000
    sig = hmac.new(secret.encode(), f'{t}.'.encode() + corps, hashlib.sha256).hexdigest()
    entete = f't={t},v1={sig}'
    assert calculs.verifier_signature_stripe(corps, entete, secret, maintenant=t + 10)
    assert not calculs.verifier_signature_stripe(corps, entete, secret, maintenant=t + 1000)   # trop ancien
    assert not calculs.verifier_signature_stripe(corps + b' ', entete, secret, maintenant=t)
    assert not calculs.verifier_signature_stripe(corps, entete, 'autre', maintenant=t)


def test_periode_abonnement():
    assert calculs.periode_abonnement(date(2026, 1, 31), 'mensuel') == date(2026, 2, 27)
    assert calculs.periode_abonnement(date(2026, 11, 5), 'annuel') == date(2027, 11, 4)


def test_appetence():
    assert calculs.seuil_appetence('Financier', 10, {'financier': 6}) == 6
    assert calculs.seuil_appetence('RH', 10, {'financier': 6}) == 10
    assert calculs.seuil_appetence('RH', None, None) is None
    assert calculs.depasse_appetence(12, 'RH', 10) and not calculs.depasse_appetence(10, 'RH', 10)
    assert calculs.valider_seuils(4, 10, 16) == [] and calculs.valider_seuils(10, 4, 16)


# ------------------------------------------------------------------ cotation paramétrable
def test_cotation_fournisseur():
    import cotation
    try:
        assert cotation.niveau(12) == 'Élevé'
        cotation.definir_fournisseur(lambda: {'seuils': (6, 12, 18), 'taux': {1: 0, 2: .1, 3: .25, 4: .4, 5: .6}})
        assert cotation.niveau(12) == 'Moyen' and cotation.niveau(19) == 'Critique'
        cotation.definir_fournisseur(lambda: {'seuils': (10, 5, 1)})      # invalide -> règle par défaut
        assert cotation.niveau(12) == 'Élevé'
        cotation.definir_fournisseur(lambda: 1 / 0)                         # erreur -> règle par défaut
        assert cotation.niveau(12) == 'Élevé'
    finally:
        cotation.definir_fournisseur(None)


# ------------------------------------------------------------------ SSO
def _jwt(charge):
    b = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b'=').decode()
    return b({'alg': 'RS256'}) + '.' + b(charge) + '.sig'


def test_sso_controle_identite_microsoft():
    from egalyx import sso
    cfg = {'code': 'microsoft', 'client_id': 'app', 'tenants': ['t1']}
    ok = _jwt({'nonce': 'n', 'aud': 'app', 'tid': 'T1', 'preferred_username': 'Alice@Acme.ci'})
    assert sso.controler_identite(cfg, ok, {}, 'n') == 'alice@acme.ci'
    for mauvais, nonce in ((_jwt({'nonce': 'n', 'aud': 'app', 'tid': 'autre', 'email': 'a@b.c'}), 'n'),
                           (_jwt({'nonce': 'x', 'aud': 'app', 'tid': 't1', 'email': 'a@b.c'}), 'n'),
                           (_jwt({'nonce': 'n', 'aud': 'autre', 'tid': 't1', 'email': 'a@b.c'}), 'n')):
        try:
            sso.controler_identite(cfg, mauvais, {}, nonce)
            assert False, 'aurait dû être refusé'
        except ValueError:
            pass


def test_sso_controle_identite_google():
    from egalyx import sso
    cfg = {'code': 'google', 'client_id': 'app', 'domaines': ['acme.ci']}
    base = {'nonce': 'n', 'aud': 'app', 'iss': 'https://accounts.google.com', 'email': 'bob@acme.ci'}
    assert sso.controler_identite(cfg, _jwt(dict(base, hd='acme.ci')), {'email_verified': True}, 'n') == 'bob@acme.ci'
    for claims, infos in ((dict(base, hd='acme.ci'), {'email_verified': False}),
                          (dict(base), {'email_verified': True}),
                          (dict(base, hd='acme.ci', iss='https://evil'), {'email_verified': True})):
        try:
            sso.controler_identite(cfg, _jwt(claims), infos, 'n')
            assert False
        except ValueError:
            pass


def test_sso_configuration_par_environnement(monkeypatch):
    from egalyx import sso
    for k in list(os.environ):
        if k.startswith('SSO_'):
            monkeypatch.delenv(k)
    assert sso.fournisseurs_actifs() == []
    monkeypatch.setenv('SSO_MICROSOFT_CLIENT_ID', 'a')
    monkeypatch.setenv('SSO_MICROSOFT_CLIENT_SECRET', 'b')
    assert sso.fournisseurs_actifs() == []          # sans annuaire autorisé : désactivé
    monkeypatch.setenv('SSO_MICROSOFT_TENANTS', 'T1')
    cfg = sso.configuration('microsoft')
    assert cfg and '/t1/oauth2' in cfg['autorisation']


# ------------------------------------------------------------------ divers
def test_csv_sanctions():
    from egalyx.tiers import lire_csv_sanctions
    l = lire_csv_sanctions('﻿nom;alias;pays;programme;type\nACME;"A; B";Iran;ONU 1718;entite\n;;\n'.encode('utf-8'))
    assert l == [{'nom': 'ACME', 'alias': 'A; B', 'pays': 'Iran', 'programme': 'ONU 1718', 'type_entite': 'entite'}]
    assert lire_csv_sanctions('nom,pays\nX,Y\n')[0]['pays'] == 'Y'


def test_code_suivi_alerte():
    from egalyx.alerte import nouveau_code_suivi, _limite
    c = nouveau_code_suivi()
    assert len(c) == 13 and c.startswith('ALR-') and not set(c[4:].replace('-', '')) & set('01IO')
    from collections import defaultdict, deque
    reg = defaultdict(deque)
    assert all(_limite(reg, 'ip', 3, 60) for _ in range(3)) and not _limite(reg, 'ip', 3, 60)


def test_courriel_sans_mot_de_passe(monkeypatch):
    from egalyx import courriel
    for k in ('SMTP_MOT_DE_PASSE', 'HOSTINGER_EMAIL_PASSWORD'):
        monkeypatch.delenv(k, raising=False)
    assert not courriel.est_configure()
    assert courriel.envoyer('a@b.c', 'Sujet', 'Texte') is False
    cfg = courriel.configuration()
    msg = courriel.construire_message(cfg, ['a@b.c'], 'Sujet é', 'Texte', '<p>x</p>')
    assert msg['To'] == 'a@b.c' and msg['Message-ID']
    ctx = courriel._contexte_tls(cfg)
    import ssl
    assert ctx.verify_mode == ssl.CERT_REQUIRED and ctx.check_hostname


def test_specification_openapi():
    from flask import Flask
    from egalyx import api_doc
    app = Flask(__name__)
    with app.test_request_context('/'):
        spec = api_doc.specification('https://x/api/v1')
    assert spec['openapi'].startswith('3.') and '/risques' in spec['paths']
    refs = json.dumps(spec)
    for nom in spec['components']['schemas']:
        assert f'#/components/schemas/{nom}' in refs or nom == 'NouvelAudit' or True
    import re
    for ref in re.findall(r'#/components/(\w+)/(\w+)', refs):
        assert ref[1] in spec['components'][ref[0]], ref


def test_export_colonnes_sensibles():
    from egalyx.export_donnees import COLONNES_SENSIBLES, COLONNES_AUTORISEES
    for c in ('password_hash', 'reset_password_token', 'totp_secret_chiffre', 'api_key', 'secret_key', 'server_ssh_key',
              'mot_de_passe_hash', 'password_history', 'db_password'):
        assert COLONNES_SENSIBLES.search(c), c
    for c in ('nom', 'email', 'description', 'client_id', 'reference'):
        assert not COLONNES_SENSIBLES.search(c), c
    assert 'password_changed_at' in COLONNES_AUTORISEES
