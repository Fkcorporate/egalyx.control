"""Recommandations du contrôle interne N2 : appréciation (niveau + commentaire).

Revision ID: egalyx_0009_appreciation_c2n
Revises: egalyx_0008_externe_entite
Idempotente : egalyx/base_donnees.py ajoute aussi ces colonnes au démarrage.
"""
import sqlalchemy as sa
from alembic import op

revision = 'egalyx_0009_appreciation_c2n'
down_revision = 'egalyx_0008_externe_entite'
branch_labels = None
depends_on = None

COLONNES = [('appreciation', sa.String(30)), ('appreciation_commentaire', sa.Text()),
            ('appreciation_le', sa.DateTime()), ('appreciation_par_id', sa.Integer())]


def _table():
    return 'recommandations_c2n'


def upgrade():
    existantes = {c['name'] for c in sa.inspect(op.get_bind()).get_columns(_table())}
    for nom, type_ in COLONNES:
        if nom not in existantes:
            op.add_column(_table(), sa.Column(nom, type_, nullable=True))


def downgrade():
    existantes = {c['name'] for c in sa.inspect(op.get_bind()).get_columns(_table())}
    for nom, _ in COLONNES:
        if nom in existantes:
            op.drop_column(_table(), nom)
