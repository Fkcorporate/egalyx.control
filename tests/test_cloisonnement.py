"""Cloisonnement entre organisations et droits d'écriture (egalyx/cloisonnement.py), avec des doubles."""
import os
import sys
from types import SimpleNamespace as N

import pytest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)
sys.path.insert(0, os.path.join(RACINE, 'tests', 'stubs'))

import models  # noqa: E402  (double)
from flask import Flask, jsonify  # noqa: E402


# ------------------------------------------------------------- mini « SQLAlchemy » : tables et clés étrangères
class FK:
    def __init__(self, colonne, table_cible):
        self.parent = N(key=colonne)
        self.column = N(table=N(name=table_cible))


class Obj:
    """Objet de base : client_id facultatif, clés étrangères déclarées dans __table__."""
    def __init__(self, **kw):
        self.__dict__.update(kw)


def modele(nom, table, fks=()):
    return type(nom, (Obj,), {'__tablename__': table, '__table__': N(foreign_keys=[FK(c, t) for c, t in fks])})


Audit = modele('Audit', 'audits')
Constatation = modele('Constatation', 'constatations', [('audit_id', 'audits')])
Processus = modele('Processus', 'processus')
EtapeProcessus = modele('EtapeProcessus', 'etape_processus', [('processus_id', 'processus')])
BASE = {}


class Session:
    def get(self, m, i):
        return BASE.get((m.__name__, i))


FAUX_DB = N(session=Session())
PAR_NOM = {c.__name__: c for c in (Audit, Constatation, Processus, EtapeProcessus)}
PAR_TABLE = {c.__tablename__: c for c in PAR_NOM.values()}


@pytest.fixture()
def app(monkeypatch):
    from egalyx import cloisonnement, modules_client
    monkeypatch.setattr(cloisonnement, '_modeles', lambda: (None, FAUX_DB, PAR_NOM, PAR_TABLE))
    monkeypatch.setitem(cloisonnement.CARTE, 'voir_audit', {'audit_id': 'Audit'})
    monkeypatch.setitem(cloisonnement.CARTE, 'modifier_constatation', {'constatation_id': 'Constatation'})
    monkeypatch.setitem(cloisonnement.CARTE, 'supprimer_etape', {'etape_id': 'EtapeProcessus'})
    monkeypatch.setitem(modules_client.MODULE_DU_MODELE, 'Constatation', 'audit')
    monkeypatch.setitem(modules_client.MODULE_DU_MODELE, 'EtapeProcessus', 'processus')
    BASE.clear()
    BASE[('Audit', 1)] = Audit(id=1, client_id=10, responsable_id=None, created_by=None, equipe_audit_ids='7, 8')
    BASE[('Audit', 2)] = Audit(id=2, client_id=20, responsable_id=None, created_by=None, equipe_audit_ids='')
    BASE[('Constatation', 5)] = Constatation(id=5, client_id=None, audit_id=1, audit=BASE[('Audit', 1)])   # ancienne ligne sans client
    BASE[('Constatation', 6)] = Constatation(id=6, client_id=None, audit_id=2, audit=BASE[('Audit', 2)])
    BASE[('Processus', 3)] = Processus(id=3, client_id=20)
    BASE[('EtapeProcessus', 9)] = EtapeProcessus(id=9, processus_id=3, client_id=None)
    a = Flask(__name__); a.secret_key = 'x'
    a.add_url_rule('/dashboard', 'dashboard', lambda: 'tableau')
    a.add_url_rule('/audit/<int:audit_id>', 'voir_audit', lambda audit_id: 'audit')
    a.add_url_rule('/constatation/<int:constatation_id>/modifier', 'modifier_constatation',
                   lambda constatation_id: jsonify(ok=True), methods=['POST'])
    a.add_url_rule('/api/etape/<int:etape_id>', 'supprimer_etape', lambda etape_id: jsonify(ok=True), methods=['DELETE'])

    @a.route('/_c/<int:uid>')
    def _c(uid):
        from flask_login import login_user
        login_user(models.User.query.get(uid)); return 'ok'
    cloisonnement.enregistrer(a)
    models.User._registre.clear(); models.Client._registre.clear()
    return a


def utilisateur(id, client_id, role='utilisateur', droits=None):
    u = models.User(id=id, username=f'u{id}', email=f'{id}@x', role=role, client_id=client_id, droits=droits)
    models.db.session.add(u)
    return u


def test_isolation_entre_organisations(app):
    utilisateur(1, 10, 'admin')
    c = app.test_client(); c.get('/_c/1')
    assert c.get('/audit/1').status_code == 200
    assert c.get('/audit/2').status_code == 404                                   # audit d'une autre organisation
    assert c.post('/constatation/6/modifier').status_code == 404                  # rattachée via son audit
    assert c.delete('/api/etape/9').status_code == 404                            # étape -> processus -> organisation
    assert c.delete('/api/etape/9').get_json() == {'success': False, 'error': 'Introuvable'}
    assert c.get('/audit/999').status_code == 200                                 # objet inconnu : la route décide


def test_super_admin_non_cloisonne(app):
    utilisateur(2, None, 'super_admin')
    c = app.test_client(); c.get('/_c/2')
    assert c.get('/audit/2').status_code == 200


def test_droits_ecriture(app):
    utilisateur(3, 10, 'utilisateur', droits={'can_view_dashboard'})            # sans permission d'audit
    utilisateur(7, 10, 'utilisateur', droits={'can_view_dashboard'})            # membre de l'équipe de l'audit 1
    utilisateur(4, 10, 'auditeur', droits={'can_manage_audit'})
    utilisateur(5, 10, 'operateur', droits=set()).is_operateur = True
    # Opérateur sans droit, hors de ses pages « operateur_… » : refusé (avant : laissé passer — trou trouvé en recette)
    for uid, attendu in ((3, 403), (7, 200), (4, 200), (5, 403)):
        c = app.test_client(); c.get(f'/_c/{uid}')
        r = c.post('/constatation/5/modifier', headers={'Accept': 'application/json'})
        assert r.status_code == attendu, uid
    c = app.test_client(); c.get('/_c/3')
    assert c.get('/audit/1').status_code == 200                                    # la lecture reste possible


def test_desactivation_d_urgence(app, monkeypatch):
    utilisateur(1, 10, 'admin')
    monkeypatch.setenv('EGALYX_CLOISONNEMENT', '0')
    c = app.test_client(); c.get('/_c/1')
    assert c.get('/audit/2').status_code == 200


def test_carte_generee_couvre_les_routes_signalees():
    from egalyx.cloisonnement_carte import CARTE
    for route in ('upload_multiple_preuves_constatation', 'ajouter_constatation', 'gerer_equipe_audit', 'api_supprimer_etape',
                  'changer_campagne_cartographie', 'export_rapport_audit_word', 'api_associer_risque_element'):
        assert route in CARTE, route


# ------------------------------------------------------------- questionnaires publics
def test_regle_questionnaires_publics():
    from datetime import datetime, timedelta
    from egalyx.questionnaires_publics import autorise
    maintenant = datetime(2026, 11, 5)
    anonyme = N(is_authenticated=False)
    interne = N(is_authenticated=True, role='utilisateur', client_id=10)
    autre = N(is_authenticated=True, role='utilisateur', client_id=20)
    q = lambda **k: N(**dict(dict(est_actif=True, est_public=False, date_debut=None, date_fin=None, client_id=10), **k))
    assert not autorise(None, anonyme, maintenant)
    assert autorise(q(est_public=True), anonyme, maintenant)
    assert not autorise(q(), anonyme, maintenant)                        # interne : pas de réponse anonyme
    assert autorise(q(), interne, maintenant) and not autorise(q(), autre, maintenant)
    assert not autorise(q(est_public=True, est_actif=False), anonyme, maintenant)
    assert not autorise(q(est_public=True, date_fin=maintenant - timedelta(days=1)), anonyme, maintenant)
    assert not autorise(q(est_public=True, date_debut=maintenant + timedelta(days=1)), anonyme, maintenant)


def test_routes_operationnelles_reconnues_par_module():
    from egalyx.modules_client import module_de_la_requete
    for chemin, attendu in (('/api/kri/synchroniser', 'kri'), ('/organismes/nouveau', 'veille'), ('/api/pca/suggerer-action', 'pca'),
                            ('/plans-action/independant/nouveau', 'plans_action'), ('/api/qualite/generer-objectifs', 'qualite'),
                            ('/api/incidents', 'incidents'), ('/tableau-de-bord', None)):
        assert module_de_la_requete('route_inconnue', chemin) == attendu, chemin
