"""Analyse de données, lot 3 : sources (connecteurs) et analyses programmées (audit continu).

Tables analyses_sources, analyses_programmees, analyses_programmees_executions.
Idempotente : ne crée que ce qui manque (les tables sont aussi créées au démarrage).

Revision ID: egalyx_0014_analyse_sources
Revises: egalyx_0013_analyse_donnees
Create Date: 2026-11-26 18:00:00
"""
import sqlalchemy as sa
from alembic import op

revision = 'egalyx_0014_analyse_sources'
down_revision = 'egalyx_0013_analyse_donnees'
branch_labels = None
depends_on = None


def upgrade():
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if 'analyses_sources' not in tables:
        op.create_table(
            'analyses_sources',
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('client_id', sa.Integer, sa.ForeignKey('clients.id'), nullable=False, index=True),
            sa.Column('nom', sa.String(150), nullable=False),
            sa.Column('connecteur', sa.String(40), nullable=False),
            sa.Column('parametres', sa.JSON),
            sa.Column('secrets', sa.JSON),
            sa.Column('actif', sa.Boolean),
            sa.Column('dernier_test_le', sa.DateTime),
            sa.Column('dernier_test_ok', sa.Boolean),
            sa.Column('dernier_message', sa.String(500)),
            sa.Column('created_by', sa.Integer, sa.ForeignKey('user.id')),
            sa.Column('created_at', sa.DateTime),
            sa.Column('updated_at', sa.DateTime),
        )
    if 'analyses_programmees' not in tables:
        op.create_table(
            'analyses_programmees',
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('client_id', sa.Integer, sa.ForeignKey('clients.id'), nullable=False, index=True),
            sa.Column('nom', sa.String(200), nullable=False),
            sa.Column('source_id', sa.Integer, sa.ForeignKey('analyses_sources.id'), nullable=False),
            sa.Column('jeux', sa.JSON),
            sa.Column('tests', sa.JSON),
            sa.Column('parametres', sa.JSON),
            sa.Column('periode', sa.String(30)),
            sa.Column('frequence', sa.String(20)),
            sa.Column('referentiel_id', sa.Integer, sa.ForeignKey('referentiel_controles.id')),
            sa.Column('controleur_id', sa.Integer, sa.ForeignKey('user.id')),
            sa.Column('kri_liens', sa.JSON),
            sa.Column('responsable_id', sa.Integer, sa.ForeignKey('user.id')),
            sa.Column('actif', sa.Boolean),
            sa.Column('etat', sa.JSON),
            sa.Column('prochaine_execution', sa.DateTime, index=True),
            sa.Column('derniere_execution', sa.DateTime),
            sa.Column('dernier_statut', sa.String(20)),
            sa.Column('dernier_message', sa.String(500)),
            sa.Column('created_by', sa.Integer, sa.ForeignKey('user.id')),
            sa.Column('created_at', sa.DateTime),
            sa.Column('updated_at', sa.DateTime),
        )
    if 'analyses_programmees_executions' not in tables:
        op.create_table(
            'analyses_programmees_executions',
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('programme_id', sa.Integer, sa.ForeignKey('analyses_programmees.id'), nullable=False, index=True),
            sa.Column('client_id', sa.Integer, sa.ForeignKey('clients.id'), nullable=False, index=True),
            sa.Column('debut', sa.DateTime),
            sa.Column('fin', sa.DateTime),
            sa.Column('declenchement', sa.String(20)),
            sa.Column('statut', sa.String(20)),
            sa.Column('message', sa.Text),
            sa.Column('periode_debut', sa.Date),
            sa.Column('periode_fin', sa.Date),
            sa.Column('jeux', sa.JSON),
            sa.Column('resultats', sa.JSON),
            sa.Column('nouvelles', sa.Integer),
            sa.Column('suites', sa.JSON),
            sa.Column('par_id', sa.Integer, sa.ForeignKey('user.id')),
        )


def downgrade():
    raise RuntimeError("La révision 0014 ne se défait pas (perte des sources et de l'historique des analyses programmées) : "
                       "restaurez une sauvegarde de la base si nécessaire.")
