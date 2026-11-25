"""egalyx/cloisonnement_listes.py : une liste ne montre que l'organisation de l'utilisateur (vraie base SQLite en mémoire)."""
import types

import pytest

flask_sqlalchemy = pytest.importorskip('flask_sqlalchemy')
sqlalchemy = pytest.importorskip('sqlalchemy')

from flask import Flask  # noqa: E402


@pytest.fixture()
def env(monkeypatch):
    from egalyx import cloisonnement_listes as cl
    app = Flask('t')
    app.config.update(SQLALCHEMY_DATABASE_URI='sqlite://', SECRET_KEY='x')
    db = flask_sqlalchemy.SQLAlchemy(app)

    class Client(db.Model):
        id = db.Column(db.Integer, primary_key=True)

    class Membre(db.Model):
        id = db.Column(db.Integer, primary_key=True)
        username = db.Column(db.String(40), unique=True)
        client_id = db.Column(db.Integer)

    class Doc(db.Model):
        id = db.Column(db.Integer, primary_key=True)
        nom = db.Column(db.String(40))
        client_id = db.Column(db.Integer)
        auteur_id = db.Column(db.Integer, db.ForeignKey('membre.id'))
        auteur = db.relationship(Membre)

    class Modele(db.Model):
        id = db.Column(db.Integer, primary_key=True)
        client_id = db.Column(db.Integer)
        is_public = db.Column(db.Boolean, default=False)

    utilisateur = types.SimpleNamespace(is_authenticated=True, role='admin', client_id=1)
    monkeypatch.setattr(cl, 'current_user', utilisateur)
    monkeypatch.delenv('EGALYX_CLOISONNEMENT_LISTES', raising=False)
    cl.enregistrer(app)

    @app.route('/docs')
    def docs():
        return ','.join(sorted(d.nom for d in Doc.query.all()))

    with app.app_context():
        db.create_all()
        db.session.add_all([Membre(id=1, username='alice', client_id=1), Membre(id=2, username='bob', client_id=2),
                            Membre(id=9, username='egalyx', client_id=None),
                            Doc(id=1, nom='a1', client_id=1, auteur_id=2), Doc(id=2, nom='b1', client_id=2),
                            Doc(id=3, nom='commun', client_id=None),
                            Modele(id=1, client_id=2, is_public=True), Modele(id=2, client_id=2, is_public=False)])
        db.session.commit()
        yield app, db, utilisateur, Doc, Membre, Modele


def _dans_une_page(app, fn):
    with app.test_request_context('/'):
        app.preprocess_request()
        return fn()


def test_liste_limitee_a_l_organisation(env):
    app, db, u, Doc, Membre, Modele = env
    assert app.test_client().get('/docs').get_data(as_text=True) == 'a1,commun'
    assert _dans_une_page(app, lambda: Doc.query.count()) == 2
    assert _dans_une_page(app, lambda: db.session.query(db.func.count(Doc.id)).scalar()) == 2
    assert _dans_une_page(app, lambda: sorted(m.username for m in Membre.query.all())) == ['alice', 'egalyx']
    assert _dans_une_page(app, lambda: [m.id for m in Modele.query.all()]) == [1]        # public : partagé


def test_recherches_ciblees_et_relations_inchangees(env):
    app, db, u, Doc, Membre, Modele = env
    # « ce nom d'utilisateur existe déjà ? » doit voir toute la table
    assert _dans_une_page(app, lambda: Membre.query.filter_by(username='bob').first()) is not None
    # par identifiant : c'est egalyx/cloisonnement.py qui contrôle
    assert _dans_une_page(app, lambda: db.session.get(Doc, 2)) is not None
    # relation d'un élément autorisé : chargée normalement
    assert _dans_une_page(app, lambda: Doc.query.filter_by(nom='a1').first().auteur.username) == 'bob'
    # mais « tous sauf celui-ci » reste filtré
    assert _dans_une_page(app, lambda: sorted(d.nom for d in Doc.query.filter(Doc.id != 1).all())) == ['commun']


def test_super_admin_hors_page_et_desactivation(env, monkeypatch):
    app, db, u, Doc, Membre, Modele = env
    assert Doc.query.count() == 3                                        # hors requête (tâche planifiée)
    u.role = 'super_admin'
    assert _dans_une_page(app, lambda: Doc.query.count()) == 3
    u.role = 'admin'
    monkeypatch.setenv('EGALYX_CLOISONNEMENT_LISTES', '0')
    assert _dans_une_page(app, lambda: Doc.query.count()) == 3
    monkeypatch.delenv('EGALYX_CLOISONNEMENT_LISTES')
    from egalyx.cloisonnement_listes import sans_cloisonnement

    def voulu():
        with sans_cloisonnement():
            return Doc.query.count()
    assert _dans_une_page(app, voulu) == 3
