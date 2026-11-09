"""
Parcours complets des modules v4 avec le vrai code des routes et des gabarits,
sur une base en mémoire (doubles de models.py et de Flask-Login).
    python3 -m pytest -q tests/test_v4_parcours.py
"""
import hashlib
import hmac
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, date

import pytest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)
sys.path.insert(0, os.path.join(RACINE, 'tests', 'stubs'))   # doubles de models et flask_login prioritaires

from flask import Flask, jsonify  # noqa: E402
from jinja2 import ChainableUndefined  # noqa: E402

MODULES_EGALYX = {'securite_compte', 'sso', 'parametres_risque', 'alerte', 'alertes', 'tiers', 'signature', 'paiement',
                  'export_donnees', 'api_doc', 'organigramme_editeur', 'sauvegardes', 'demo', 'rapport_comite',
                  'bibliotheque', 'recherche', 'ma_semaine'}
import models  # noqa: E402  (double)
from egalyx import calculs  # noqa: E402


class Souple(ChainableUndefined):
    def __str__(self): return ''
    def __iter__(self): return iter(())
    def __len__(self): return 0
    def __bool__(self): return False
    def __eq__(self, o): return isinstance(o, Souple) or o is None
    def __hash__(self): return 0
    def __call__(self, *a, **k): return self


def fabriquer_app():
    from egalyx import double_auth, sso, alerte, paiement, api_doc, export_donnees
    app = Flask(__name__, template_folder=os.path.join(RACINE, 'templates'))
    app.secret_key = 'test'
    app.config['TESTING'] = True
    app.jinja_env.undefined = Souple
    app.jinja_env.add_extension('jinja2.ext.do'); app.jinja_env.add_extension('jinja2.ext.loopcontrols')
    from flask_login import current_user
    app.jinja_env.globals.update(csrf_token=lambda: 'jeton', t=lambda s, *a, **k: s, url_exists=lambda e: e in app.view_functions,
                                 should_display_module=lambda *a: False, current_user=current_user)
    app.url_build_error_handlers.append(lambda err, ep, vals: (_ for _ in ()).throw(err) if ep.split('.')[0] in MODULES_EGALYX else '/#' + ep)
    for nom in ('dashboard', 'home', 'login', 'login_fullscreen', 'profil_utilisateur'):
        app.add_url_rule('/' + nom, nom, lambda: 'page')

    @app.route('/_connexion/<int:uid>')
    def _connexion(uid):
        from flask_login import login_user
        login_user(models.User.query.get(uid))
        return 'ok'

    @app.route('/logout')
    def logout():
        from flask_login import logout_user
        logout_user()
        return 'au revoir'

    @app.route('/api/test')
    def api_test():
        return jsonify(ok=True)

    double_auth.enregistrer(app); sso.enregistrer(app); alerte.enregistrer(app); paiement.enregistrer(app)
    api_doc.enregistrer(app); export_donnees.enregistrer(app)
    return app


@pytest.fixture()
def contexte(monkeypatch):
    for m in (models.User, models.Client, models.Signalement, models.MessageSignalement, models.JournalActiviteClient,
              models.FormuleAbonnement, models.AbonnementClient, models.PaiementEnLigne):
        m._registre.clear()
    monkeypatch.delenv('SMTP_MOT_DE_PASSE', raising=False)
    monkeypatch.delenv('HOSTINGER_EMAIL_PASSWORD', raising=False)
    db = models.db
    acme = models.Client(nom='ACME CI', reference='ACME', contact_email='dg@acme.ci'); db.session.add(acme)
    autre = models.Client(nom='Autre', reference='AUTRE'); db.session.add(autre)
    admin = models.User(username='admin', email='admin@acme.ci', role='admin', client_id=acme.id, is_client_admin=True)
    conf = models.User(username='conformite', email='conf@acme.ci', role='compliance', client_id=acme.id)
    simple = models.User(username='paul', email='paul@acme.ci', role='utilisateur', client_id=acme.id,
                         droits={'can_view_dashboard', 'can_view_action_plans'})
    conf_autre = models.User(username='conf2', email='c@autre', role='compliance', client_id=autre.id)
    sa = models.User(username='sa', email='sa@egalyx', role='super_admin', client_id=None)
    for u in (admin, conf, simple, conf_autre, sa):
        db.session.add(u)
    app = fabriquer_app()
    return app, app.test_client(), {'acme': acme, 'autre': autre, 'admin': admin, 'conf': conf, 'simple': simple,
                                    'conf_autre': conf_autre, 'sa': sa}


# =========================================================== double authentification
def test_2fa_activation_obligatoire_puis_verification(contexte):
    app, c, d = contexte
    admin = d['admin']
    c.get(f"/_connexion/{admin.id}")
    r = c.get('/dashboard')
    assert r.status_code == 302 and r.location.endswith('/compte/securite/2fa/activer')
    assert c.get('/api/test', headers={'Accept': 'application/json'}).status_code == 403

    r = c.get('/compte/securite/2fa/activer')
    assert r.status_code == 200 and 'qrcode' in r.text
    with c.session_transaction() as s:
        secret = s['2fa_secret_provisoire']
    assert secret.replace(' ', '')[:4] in r.text.replace(' ', '')
    assert c.post('/compte/securite/2fa/activer', data={'code': '000000' if calculs.totp_code(secret) != '000000' else '111111'}).status_code == 200
    assert not admin.totp_actif
    code_activation = calculs.totp_code(secret)
    r = c.post('/compte/securite/2fa/activer', data={'code': code_activation})
    assert r.status_code == 302 and admin.totp_actif and admin.totp_secret_chiffre.startswith('enc1:')
    assert secret not in admin.totp_secret_chiffre
    page = c.get('/compte/securite/2fa/codes-secours').text
    codes = re.findall(r'<div>([A-Z0-9]{4}-[A-Z0-9]{4})</div>', page)
    assert len(codes) == 8 and len(admin.totp_codes_secours) == 8
    assert all(codes[0].replace('-', '') not in h for h in admin.totp_codes_secours)    # seules les empreintes
    assert c.get('/compte/securite/2fa/codes-secours').status_code == 302               # affichés une seule fois
    assert c.get('/dashboard').status_code == 200

    # Nouvelle connexion : vérification exigée, même code refusé (rejeu), code de secours à usage unique
    c.get('/logout'); c.get(f"/_connexion/{admin.id}")
    r = c.get('/dashboard')
    assert r.status_code == 302 and '/2fa/verification' in r.location
    assert c.get('/api/test', headers={'Accept': 'application/json'}).status_code == 401
    assert c.post('/compte/securite/2fa/verification', data={'code': code_activation}).status_code == 200  # rejeu du même code
    r = c.post('/compte/securite/2fa/verification', data={'code': codes[0].lower()})
    assert r.status_code == 302 and r.location.endswith('/dashboard') and len(admin.totp_codes_secours) == 7
    c.get('/logout'); c.get(f"/_connexion/{admin.id}")
    assert c.post('/compte/securite/2fa/verification', data={'code': codes[0]}).status_code == 200      # déjà utilisé


def test_2fa_echecs_repetes_deconnectent(contexte):
    app, c, d = contexte
    u = d['simple']
    u.totp_actif = True
    u.totp_secret_chiffre = models.chiffrer_secret(calculs.totp_nouveau_secret())
    c.get(f"/_connexion/{u.id}")
    for i in range(4):
        assert c.post('/compte/securite/2fa/verification', data={'code': '123456'}).status_code == 200
    r = c.post('/compte/securite/2fa/verification', data={'code': '123456'})
    assert r.status_code == 302 and r.location.endswith('/login')
    with c.session_transaction() as s:
        assert '_uid' not in s


def test_2fa_facultative_pour_utilisateur_et_reinitialisation_admin(contexte, monkeypatch):
    app, c, d = contexte
    c.get(f"/_connexion/{d['simple'].id}")
    assert c.get('/dashboard').status_code == 200
    assert c.get('/compte/securite/').status_code == 200
    # Réinitialisation par l'administrateur de la même organisation (2FA admin désactivée pour ce test)
    monkeypatch.setenv('EGALYX_2FA_OBLIGATOIRE_ADMINS', '0')
    d['simple'].totp_actif = True
    c.get('/logout'); c.get(f"/_connexion/{d['admin'].id}")
    c.post(f"/compte/securite/2fa/reinitialiser/{d['simple'].id}")
    assert d['simple'].totp_actif is False
    d['conf_autre'].totp_actif = True
    c.post(f"/compte/securite/2fa/reinitialiser/{d['conf_autre'].id}")          # autre organisation : refusé
    assert d['conf_autre'].totp_actif is True


# =========================================================== alerte interne
def test_alerte_parcours_complet(contexte, monkeypatch):
    app, c, d = contexte
    assert c.get('/alerte/INCONNU').status_code == 404
    r = c.get('/alerte/ACME')
    assert r.status_code == 200 and 'ACME CI' in r.text
    r = c.post('/alerte/ACME', data={'categorie': 'fraude', 'description': 'court', 'mot_de_passe': 'a', 'mot_de_passe2': 'a'})
    assert r.status_code == 200 and models.Signalement.query.count() == 0
    texte = 'Le responsable des achats valide des factures fictives depuis mars, montant estimé 40 millions FCFA.'
    r = c.post('/alerte/ACME', data={'categorie': 'fraude', 'description': texte, 'anonyme': '1', 'personnes': 'M. X',
                                     'mot_de_passe': 'motdepasse1', 'mot_de_passe2': 'motdepasse1', 'bonne_foi': '1'})
    assert r.status_code == 302
    s = models.Signalement.query.first()
    assert s and s._description.startswith('enc1:') and 'factures' not in s._description and s.description == texte
    page = c.get(r.location).text
    code = re.search(r'ALR-[A-Z0-9]{4}-[A-Z0-9]{4}', page).group(0)
    assert code == s.code_suivi
    assert c.get(r.location).status_code == 302                              # code affiché une seule fois

    # Robot : champ piège rempli -> rien n'est enregistré
    c.post('/alerte/ACME', data={'site_web': 'x', 'categorie': 'fraude', 'description': texte})
    assert models.Signalement.query.count() == 1

    # Suivi par le lanceur d'alerte
    c2 = app.test_client()
    assert 'Code de suivi ou mot de passe incorrect' in c2.post('/alerte/suivi', data={'action': 'connexion', 'code': code, 'mot_de_passe': 'faux'}).text
    c2.post('/alerte/suivi', data={'action': 'connexion', 'code': code.lower(), 'mot_de_passe': 'motdepasse1'})
    assert texte[:20] not in c2.get('/alerte/suivi').text            # le contenu initial n'est pas réaffiché
    c2.post('/alerte/suivi', data={'action': 'message', 'message': 'Pièce : facture n°12'})
    assert 'facture n°12' in c2.get('/alerte/suivi').text

    # Référent
    c.get(f"/_connexion/{d['conf'].id}")
    r = c.get('/conformite/alertes/')
    assert r.status_code == 200 and code in r.text and '/alerte/ACME' in r.text
    r = c.get(f'/conformite/alertes/{s.id}')
    assert r.status_code == 200 and 'factures fictives' in r.text and 'facture n°12' in r.text
    c.post(f'/conformite/alertes/{s.id}/action', data={'action': 'accuser'})
    assert s.date_accuse_reception and s.referent_id == d['conf'].id
    c.post(f'/conformite/alertes/{s.id}/action', data={'action': 'note', 'message': 'Vérifier les PO'})
    c.post(f'/conformite/alertes/{s.id}/action', data={'action': 'recevabilite', 'recevable': '1'})
    assert s.statut == 'en_instruction'
    suivi = c2.get('/alerte/suivi').text
    assert 'Vérifier les PO' not in suivi and 'recevable' in suivi             # note interne invisible du lanceur
    c.post(f'/conformite/alertes/{s.id}/action', data={'action': 'cloturer', 'issue': 'cloture_fonde', 'message': 'Mesures disciplinaires prises.'})
    assert s.est_cloture and s.date_retour_information
    assert 'clôturé' in c2.get('/alerte/suivi').text

    # Cloisonnement : autre organisation, utilisateur simple, super admin
    c.get('/logout'); c.get(f"/_connexion/{d['conf_autre'].id}")
    assert c.get(f'/conformite/alertes/{s.id}').status_code == 404
    c.get('/logout'); c.get(f"/_connexion/{d['simple'].id}")
    assert c.get(f'/conformite/alertes/{s.id}').status_code == 302
    journal = [j.action for j in models.JournalActiviteClient.query.all()]
    assert 'signalement_consulte' in journal and 'signalement_accuser' in journal


# =========================================================== paiement
def test_paiement_validation_prolonge_abonnement(contexte):
    app, c, d = contexte
    from egalyx import paiement
    f = models.FormuleAbonnement(nom='Pro', code='pro', prix_mensuel=49, prix_annuel=490); models.db.session.add(f)
    acme = d['acme']
    acme.date_expiration = datetime.combine(date.today() + timedelta(days=10), datetime.min.time())
    p = models.PaiementEnLigne(client_id=acme.id, formule_id=f.id, periode='annuel', montant=490, devise='EUR',
                               prestataire='stripe', reference='EGXTEST1'); models.db.session.add(p)
    with app.test_request_context('/'):
        assert paiement.valider(p, {'id': 'cs_1'}, 'cs_1') is True
        assert paiement.valider(p) is False                                      # idempotent
    ab = models.AbonnementClient.query.first()
    assert ab.date_debut == date.today() + timedelta(days=11)
    assert ab.date_fin == calculs.periode_abonnement(ab.date_debut, 'annuel')
    assert acme.formule_id == f.id and acme.date_expiration.date() == ab.date_fin and models.AbonnementClient.query.count() == 1


def test_webhook_stripe_et_notification_cinetpay(contexte, monkeypatch):
    app, c, d = contexte
    from egalyx import paiement
    f = models.FormuleAbonnement(nom='Pro', code='pro', prix_mensuel=49, prix_annuel=490); models.db.session.add(f)
    p = models.PaiementEnLigne(client_id=d['acme'].id, formule_id=f.id, montant=49, devise='EUR', prestataire='stripe',
                               reference='EGXS', reference_prestataire='cs_9'); models.db.session.add(p)
    monkeypatch.setenv('STRIPE_WEBHOOK_SECRET', 'whsec'); monkeypatch.setenv('STRIPE_SECRET_KEY', 'sk')
    corps = json.dumps({'type': 'checkout.session.completed', 'data': {'object': {'id': 'cs_9', 'client_reference_id': 'EGXS'}}}).encode()
    assert c.post('/paiement/stripe/webhook', data=corps, headers={'Stripe-Signature': 't=1,v1=00'}).status_code == 400
    t = int(time.time())
    sig = hmac.new(b'whsec', f'{t}.'.encode() + corps, hashlib.sha256).hexdigest()
    # Le prestataire répond « payé » mais pour un autre montant : refusé
    monkeypatch.setattr(paiement, '_http', lambda *a, **k: {'id': 'cs_9', 'payment_status': 'paid', 'client_reference_id': 'EGXS', 'amount_total': 100, 'currency': 'eur'})
    c.post('/paiement/stripe/webhook', data=corps, headers={'Stripe-Signature': f't={t},v1={sig}'})
    assert p.statut == 'initie'
    monkeypatch.setattr(paiement, '_http', lambda *a, **k: {'id': 'cs_9', 'payment_status': 'paid', 'client_reference_id': 'EGXS', 'amount_total': 4900, 'currency': 'eur'})
    assert c.post('/paiement/stripe/webhook', data=corps, headers={'Stripe-Signature': f't={t},v1={sig}'}).status_code == 200
    assert p.statut == 'reussi'

    q = models.PaiementEnLigne(client_id=d['acme'].id, formule_id=f.id, montant=32145, devise='XOF', prestataire='cinetpay',
                               reference='EGXC'); models.db.session.add(q)
    monkeypatch.setenv('CINETPAY_SITE_ID', '123'); monkeypatch.setenv('CINETPAY_APIKEY', 'k')
    monkeypatch.setattr(paiement, '_http', lambda *a, **k: {'code': '00', 'data': {'status': 'ACCEPTED', 'amount': '32145', 'currency': 'XOF'}})
    assert c.post('/paiement/cinetpay/notification', data={'cpm_trans_id': 'EGXC', 'cpm_site_id': '999'}).status_code == 200
    assert q.statut == 'initie'                                   # site_id différent : ignoré
    c.post('/paiement/cinetpay/notification', data={'cpm_trans_id': 'EGXC', 'cpm_site_id': '123'})
    assert q.statut == 'reussi'


def test_page_abonnement(contexte, monkeypatch):
    app, c, d = contexte
    monkeypatch.setenv('EGALYX_2FA_OBLIGATOIRE_ADMINS', '0')
    monkeypatch.setenv('CINETPAY_SITE_ID', '1'); monkeypatch.setenv('CINETPAY_APIKEY', 'k')
    models.db.session.add(models.FormuleAbonnement(nom='Pro', code='pro', prix_mensuel=49, prix_annuel=490))
    c.get(f"/_connexion/{d['admin'].id}")
    r = c.get('/abonnement')
    assert r.status_code == 200 and '32 145 FCFA' in r.text and 'CinetPay' in r.text
    c.get('/logout'); c.get(f"/_connexion/{d['simple'].id}")
    assert c.get('/abonnement').status_code == 302                 # réservé aux administrateurs


def test_api_documentation(contexte):
    app, c, d = contexte
    spec = c.get('/api/v1/openapi.json').get_json()
    assert spec['info']['title'] and '/audits/{audit_id}' in spec['paths']
    c.get(f"/_connexion/{d['simple'].id}")
    assert c.get('/api/documentation').status_code == 403            # sans la permission « Gérer les clés API »
    d['simple'].droits = {'can_view_dashboard', 'can_manage_api'}
    r = c.get('/api/documentation')
    assert r.status_code == 200 and 'X-API-Key' in r.text and '/plans-action' in r.text
