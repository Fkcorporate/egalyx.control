"""Modèle de lettre de mission : titre de l'en-tête affiché ou non.

Revision ID: egalyx_0010_lm_afficher_titre
Revises: egalyx_0009_appreciation_c2n
Idempotente : egalyx/base_donnees.py ajoute aussi cette colonne au démarrage.
"""
import sqlalchemy as sa
from alembic import op

revision = 'egalyx_0010_lm_afficher_titre'
down_revision = 'egalyx_0009_appreciation_c2n'
branch_labels = None
depends_on = None


def _table():
    return 'modeles_lettre_mission'


def upgrade():
    if 'afficher_titre' not in {c['name'] for c in sa.inspect(op.get_bind()).get_columns(_table())}:
        op.add_column(_table(), sa.Column('afficher_titre', sa.Boolean(), nullable=True, server_default=sa.true()))


def downgrade():
    if 'afficher_titre' in {c['name'] for c in sa.inspect(op.get_bind()).get_columns(_table())}:
        op.drop_column(_table(), 'afficher_titre')
