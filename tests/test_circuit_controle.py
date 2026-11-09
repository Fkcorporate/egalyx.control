"""Circuit unique campagne de contrôle ↔ contrôle interne N2 (egalyx/circuit_controle.py)."""
import os
import sys
import types

import pytest
from flask import Flask

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)
sys.path.insert(0, os.path.join(RACINE, 'tests', 'stubs'))

from faux_orm import Champ, FauxDB, Modele  # noqa: E402
from egalyx import circuit_controle as cc  # noqa: E402


class User(Modele):
    is_active = Champ(True)
    is_client_admin = Champ(False)
    is_operateur = Champ(False)
    role = Champ('utilisateur')
    droits = Champ(set)
    is_authenticated = True

    def has_permission(self, p):
        return self.is_client_admin or p in self.droits

    def peut_valider_planification(self, pl):
        if pl.controleur_id == self.id:
            return False
        return pl.validateur_requis_id == self.id or self.role in ('responsable_qualite', 'manager') or self._is_admin_c2n()

    def _is_admin_c2n(self):
        return self.role in ('super_admin', 'admin') or self.is_client_admin


class Notification(Modele):
    pass


class ExecutionControle(Modele):
    def calculer_taux(self):
        self.taux_conformite = round(100 * (self.nb_conformes or 0) / self.volume_controle, 1) if self.volume_controle else 0


class _Plans:
    def __init__(self, n):
        self.n = n

    def count(self):
        return self.n


class NonConformiteC2N(Modele):
    plans_action = _Plans(0)

    @staticmethod
    def generer_reference_unique(client_id):
        return f"NC-{len(NonConformiteC2N._registre) + 1:05d}"


class AnomalieDetectee(Modele):
    campagne_id = Champ()
    client_id = Champ()
    statut = Champ('a_traiter')
    non_conformite_id = Champ()


class CampagneControle(Modele):
    planification_c2n_id = Champ()
    client_id = Champ()
    statut = Champ('en_cours')
    is_archived = Champ(False)
    historique_actions = Champ(list)
    valideur_id = Champ()
    evaluateur_id = Champ()
    execution_c2n_id = Champ()
    soumis_par_id = Champ()


class PlanificationControle(Modele):
    """Mêmes règles que le vrai modèle (valider / rejeter / rouvrir)."""
    statut = Champ('en_cours')
    historique_actions = Champ(list)
    soumis_par_id = Champ()
    validateur_requis_id = Champ()
    controleur_id = Champ()
    version = Champ(1)

    def _ajouter_historique(self, action, uid, details, ancien=None, nouveau=None):
        self.historique_actions = list(self.historique_actions) + [{'action': action, 'utilisateur_id': uid}]

    def valider(self, user, commentaire=None):
        if self.statut != 'soumis':
            return False, "pas soumise"
        if self.controleur_id == user.id or not user.peut_valider_planification(self):
            return False, "pas les droits"
        self.statut, self.valide_par_id = 'valide', user.id
        self._ajouter_historique('validation', user.id, commentaire)
        return True, "ok"

    def rejeter(self, user, raison):
        if self.statut != 'soumis' or not user.peut_valider_planification(self):
            return False, "non"
        self.statut = 'rejete'
        self._ajouter_historique('rejet', user.id, raison)
        return True, "ok"

    def rouvrir(self, user, raison=None):
        if self.statut not in ('valide', 'rejete'):
            return False, "non"
        if sum(1 for h in self.historique_actions if h['action'] == 'reouverture') >= 3:
            return False, "Limite de 3 réouvertures atteinte."
        self.statut = 'a_faire'
        self._ajouter_historique('reouverture', user.id, raison)
        return True, "ok"


class _Session(type(FauxDB().session)):
    def delete(self, o):
        type(o)._registre.remove(o)


@pytest.fixture()
def env(monkeypatch):
    for m in (User, Notification, ExecutionControle, NonConformiteC2N, AnomalieDetectee, CampagneControle,
              PlanificationControle):
        m._registre.clear()
    db = FauxDB()
    db.session = _Session()
    faux = types.SimpleNamespace(
        db=db, User=User, Notification=Notification, ExecutionControle=ExecutionControle,
        NonConformiteC2N=NonConformiteC2N, AnomalieDetectee=AnomalieDetectee, CampagneControle=CampagneControle,
        PlanificationControle=PlanificationControle, marquer_json_modifie=lambda *a: None)
    monkeypatch.setattr(cc, '_m', lambda: faux)
    # méthodes d'origine (le test d'enveloppe les modifie)
    for nom in ('valider', 'rejeter', 'rouvrir'):
        monkeypatch.setattr(PlanificationControle, nom, PlanificationControle.__dict__[nom])
    app = Flask(__name__)
    app.add_url_rule('/o/<int:campagne_id>', 'operateur_detail_campagne', lambda campagne_id: '')
    app.add_url_rule('/c/<int:campagne_id>', 'detail_campagne_controle', lambda campagne_id: '')
    U = {}
    for uid, nom, kw in ((1, 'operateur', {'is_operateur': True}), (2, 'valideur', {}),
                         (3, 'gestionnaire', {'droits': {'can_manage_campaigns'}}), (4, 'auditeur', {'droits': {'can_manage_audit'}}),
                         (5, 'controleur', {}), (6, 'admin', {'role': 'admin'})):
        u = User(id=uid, username=nom, client_id=1, **kw)
        db.session.add(u)
        U[nom] = u
    pl = PlanificationControle(id=10, client_id=1, controleur_id=5, validateur_requis_id=2, reference='PL-1')
    db.session.add(pl)
    camp = CampagneControle(id=20, client_id=1, reference='CC-1', nom='Factures', createur_id=1, evaluateur_id=1,
                            planification_c2n_id=10, nb_dossiers_prevus=50, nb_dossiers_controles=40,
                            nb_conformes=37, nb_anomalies=3, commentaire_general='', conclusion='')
    db.session.add(camp)
    for i, st in enumerate(('a_traiter', 'confirmee', 'ecartee'), 1):
        db.session.add(AnomalieDetectee(id=100 + i, campagne_id=20, client_id=1, statut=st, motif=f'Motif {i}',
                                        nombre_ecarts=1, criticite='majeur', description=None))
    with app.test_request_context():
        yield types.SimpleNamespace(db=db, U=U, pl=pl, camp=camp)


def test_soumission_sans_non_conformite_et_execution_a_jour(env):
    ok, msg = cc.soumettre(env.camp, env.U['operateur'])
    assert ok and env.camp.statut == 'en_attente_validation' and env.pl.statut == 'soumis'
    assert not NonConformiteC2N._registre                                  # pas avant la validation
    ex = ExecutionControle.query.get(env.camp.execution_c2n_id)
    assert ex.volume_controle == 40 and ex.taux_conformite == 92.5 and env.pl.execution_id == ex.id
    assert env.camp.valideur_id == 2                                       # validateur de la planification
    assert [n.destinataire_id for n in Notification._registre] == [2]
    # correction puis resoumission : l'exécution est MISE À JOUR, pas recréée
    cc.rouvrir(env.camp, env.U['operateur'], 'oubli de 2 dossiers')
    env.camp.nb_dossiers_controles, env.camp.nb_conformes = 42, 39
    cc.soumettre(env.camp, env.U['operateur'])
    assert len(ExecutionControle._registre) == 1 and ExecutionControle._registre[0].volume_controle == 42


def test_qui_peut_decider(env):
    cc.soumettre(env.camp, env.U['operateur'])
    assert not cc.peut_decider(env.U['operateur'], env.camp)[0]            # auteur
    assert not cc.peut_decider(env.U['controleur'], env.camp)[0]           # contrôleur N2
    assert not cc.peut_decider(env.U['auditeur'], env.camp)[0]             # « gérer les audits » ne suffit plus
    assert cc.peut_decider(env.U['valideur'], env.camp)[0]
    assert cc.peut_decider(env.U['gestionnaire'], env.camp)[0]
    assert cc.peut_decider(env.U['admin'], env.camp)[0]


def test_validation_cree_les_nc_et_valide_la_planification(env):
    cc.soumettre(env.camp, env.U['operateur'])
    ok, msg = cc.valider(env.camp, env.U['valideur'], 'RAS')
    assert ok and env.camp.statut == 'termine' and env.pl.statut == 'valide'
    assert len(NonConformiteC2N._registre) == 2                            # écartée exclue
    assert {a.statut for a in AnomalieDetectee._registre} == {'convertie_en_nc', 'ecartee'}
    assert cc.valider(env.camp, env.U['valideur'])[0] is False             # une seule décision


def test_gestionnaire_sans_role_n2_valide_aussi_la_planification(env):
    cc.soumettre(env.camp, env.U['operateur'])
    ok, _ = cc.valider(env.camp, env.U['gestionnaire'])
    assert ok and env.pl.statut == 'valide'


def test_rejet_sans_nc_puis_resoumission(env):
    cc.soumettre(env.camp, env.U['operateur'])
    assert cc.rejeter(env.camp, env.U['valideur'], 'court')[0] is False   # raison trop courte
    ok, _ = cc.rejeter(env.camp, env.U['valideur'], 'Volumes incohérents avec le registre')
    assert ok and env.camp.statut == 'rejete' and env.pl.statut == 'rejete' and not NonConformiteC2N._registre
    assert env.camp.raison_rejet.startswith('Volumes')
    ok, _ = cc.soumettre(env.camp, env.U['operateur'])                     # resoumission directe après rejet
    assert ok and env.pl.statut == 'soumis'


def test_rejet_retire_les_nc_de_l_ancien_circuit(env):
    cc.soumettre(env.camp, env.U['operateur'])
    a = AnomalieDetectee._registre[0]
    nc = NonConformiteC2N(client_id=1, statut='ouvert')                    # créée à la soumission (ancien code)
    env.db.session.add(nc)
    a.statut, a.non_conformite_id = 'convertie_en_nc', nc.id
    cc.rejeter(env.camp, env.U['valideur'], 'Recommencer le contrôle')
    assert not NonConformiteC2N._registre and a.statut == 'a_traiter'


def test_decision_prise_dans_le_n2_suit_la_campagne(env):
    cc._envelopper(PlanificationControle, 'valider', cc.apres_validation_n2, True)
    cc._envelopper(PlanificationControle, 'rejeter', cc.apres_rejet_n2, True)
    cc._envelopper(PlanificationControle, 'rouvrir', cc.apres_reouverture_n2, False)
    cc.soumettre(env.camp, env.U['operateur'])
    assert env.pl.valider(env.U['operateur'])[0] is False                  # auteur de la soumission
    ok, _ = env.pl.valider(env.U['valideur'], 'vu')                        # validé depuis « À valider » du N2
    assert ok and env.camp.statut == 'termine' and len(NonConformiteC2N._registre) == 2
    ok, _ = env.pl.rouvrir(env.U['admin'], 'erreur de saisie')             # rouvert dans le N2
    assert ok and env.camp.statut == 'en_cours' and env.pl.statut == 'en_cours'
    assert not NonConformiteC2N._registre                                  # NC ouvertes sans plan retirées


def test_reouvertures_limitees_a_3(env):
    for i in range(3):
        cc.soumettre(env.camp, env.U['operateur'])
        cc.rejeter(env.camp, env.U['valideur'], 'Encore une correction')
        assert cc.rouvrir(env.camp, env.U['operateur'], f'reprise {i}')[0]
    cc.soumettre(env.camp, env.U['operateur'])
    cc.rejeter(env.camp, env.U['valideur'], 'Toujours incorrect')
    ok, msg = cc.rouvrir(env.camp, env.U['operateur'], 'quatrième')
    assert not ok and '3' in msg
    # retirer une soumission n'est pas une réouverture
    camp2 = CampagneControle(id=21, client_id=1, reference='CC-2', nom='X', createur_id=1, evaluateur_id=1,
                             nb_dossiers_prevus=1, nb_dossiers_controles=1, nb_conformes=1, nb_anomalies=0,
                             commentaire_general='', conclusion='')
    env.db.session.add(camp2)
    cc.soumettre(camp2, env.U['operateur'])
    assert cc.rouvrir(camp2, env.U['operateur'], 'je retire')[0] and cc.nb_reouvertures(camp2) == 0


def test_campagne_validee_rouverte_par_gestionnaire_seulement(env):
    cc.soumettre(env.camp, env.U['operateur'])
    cc.valider(env.camp, env.U['valideur'])
    assert not cc.rouvrir(env.camp, env.U['operateur'], 'je veux corriger')[0]
    assert cc.rouvrir(env.camp, env.U['gestionnaire'], 'correction demandée')[0]


def test_campagne_sans_planification(env):
    env.camp.planification_c2n_id = None
    cc.soumettre(env.camp, env.U['operateur'])
    destinataires = {n.destinataire_id for n in Notification._registre}
    assert destinataires == {3, 6}                                         # gestionnaires, pas l'auteur
    ok, _ = cc.valider(env.camp, env.U['admin'])
    assert ok and len(NonConformiteC2N._registre) == 2
    assert ExecutionControle._registre                                     # exécution N2 tout de même créée


def test_branchement_dans_app():
    src = open(os.path.join(RACINE, 'app.py'), encoding='utf-8').read()
    for nom in ('def operateur_valider_campagne', 'def rejeter_campagne', 'def operateur_rouvrir_campagne',
                'def synchroniser_campagne_vers_c2n', 'def exporter_non_conformites_campagne'):
        corps = src[src.index(nom):src.index('\n@app.route', src.index(nom))]
        assert 'circuit_controle' in corps and "has_permission('can_manage_audit')" not in corps, nom
    i = src.index('def operateur_executer_campagne')
    corps = src[i:src.index('\n@app.route', i)]
    assert 'circuit_controle.soumettre' in corps and 'NonConformiteC2N(' not in corps
    for t in ('controle/detail_campagne.html', 'operateur/detail_campagne.html'):
        assert '_partials/circuit_campagne.html' in open(os.path.join(RACINE, 'templates', t), encoding='utf-8').read()
    modeles = open(os.path.join(RACINE, 'models.py'), encoding='utf-8').read()
    bloc = modeles[modeles.index('class CampagneControle'):modeles.index('class FichierCampagneControle')]
    for col in ('soumis_par_id', 'date_soumission', 'raison_rejet', 'historique_actions', 'valide_par_id'):
        assert f'    {col} = db.Column' in bloc, col
