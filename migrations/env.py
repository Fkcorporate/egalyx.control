import logging
from logging.config import fileConfig

from flask import current_app

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
fileConfig(config.config_file_name)
logger = logging.getLogger('alembic.env')


def get_engine():
    try:
        # this works with Flask-SQLAlchemy<3 and Alchemical
        return current_app.extensions['migrate'].db.get_engine()
    except (TypeError, AttributeError):
        # this works with Flask-SQLAlchemy>=3
        return current_app.extensions['migrate'].db.engine


def get_engine_url():
    try:
        return get_engine().url.render_as_string(hide_password=False).replace(
            '%', '%%')
    except AttributeError:
        return str(get_engine().url).replace('%', '%%')


# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
config.set_main_option('sqlalchemy.url', get_engine_url())
target_db = current_app.extensions['migrate'].db

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def get_metadata():
    if hasattr(target_db, 'metadatas'):
        return target_db.metadatas[None]
    return target_db.metadata


def ne_garder_que_le_modele(objet, nom, type_, reflechi, compare_a):
    """Egalyx : l'auto-génération ne propose jamais de supprimer ce qui n'existe que dans la base.

    Des bases anciennes portent des tables ou colonnes ajoutées à la main par d'anciens scripts
    (ex. point_decision.client_id). Les supprimer automatiquement ferait perdre des données :
    une suppression s'écrit à la main dans une migration, en connaissance de cause.
    """
    if reflechi and compare_a is None:
        return False
    return True


def oublier_revisions_inconnues(connexion):
    """Egalyx : une base peut porter le numéro d'une ancienne révision qui n'existe plus
    (ex. « add_password_security », script archivé lors du ménage de novembre 2026).
    Alembic refuserait alors de démarrer (« Can't locate revision »). Ce numéro est oublié :
    la révision de référence, qui ne fait qu'ajouter ce qui manque, est ensuite appliquée."""
    from sqlalchemy import inspect, text
    from alembic.script import ScriptDirectory
    if not inspect(connexion).has_table('alembic_version'):
        connexion.commit()          # clôt la transaction ouverte par la lecture : Alembic gère ensuite la sienne
        return
    connues = {r.revision for r in ScriptDirectory.from_config(config).walk_revisions()}
    inconnues = [v for (v,) in connexion.execute(text('SELECT version_num FROM alembic_version')) if v not in connues]
    for v in inconnues:
        logger.warning("Révision « %s » inconnue (ancien script archivé) : oubliée, la référence va s'appliquer.", v)
        connexion.execute(text('DELETE FROM alembic_version WHERE version_num = :v'), {'v': v})
    connexion.commit()


def run_migrations_offline():
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url, target_metadata=get_metadata(), literal_binds=True,
        include_object=ne_garder_que_le_modele,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """

    # this callback is used to prevent an auto-migration from being generated
    # when there are no changes to the schema
    # reference: http://alembic.zzzcomputing.com/en/latest/cookbook.html
    def process_revision_directives(context, revision, directives):
        if getattr(config.cmd_opts, 'autogenerate', False):
            script = directives[0]
            if script.upgrade_ops.is_empty():
                directives[:] = []
                logger.info('No changes in schema detected.')

    conf_args = current_app.extensions['migrate'].configure_args
    if conf_args.get("process_revision_directives") is None:
        conf_args["process_revision_directives"] = process_revision_directives

    # SQLite ne sait pas modifier une colonne : Alembic recopie alors la table (mode « batch »)
    conf_args.setdefault('render_as_batch', get_engine().dialect.name == 'sqlite')

    connectable = get_engine()

    with connectable.connect() as connection:
        oublier_revisions_inconnues(connection)
        context.configure(
            connection=connection,
            target_metadata=get_metadata(),
            include_object=ne_garder_que_le_modele,
            **conf_args
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
