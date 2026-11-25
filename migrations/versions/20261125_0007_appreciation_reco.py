"""Appréciation des recommandations d'audit (niveau + commentaire).

Revision ID: egalyx_0007_appreciation_reco
Revises: egalyx_0006_pied_lettre
Idempotente : egalyx/base_donnees.py ajoute aussi ces colonnes au démarrage.
"""
import sqlalchemy as sa
from alembic import op

revision = 'egalyx_0007_appreciation_reco'
down_revision = 'egalyx_0006_pied_lettre'
branch_labels = None
depends_on = None

COLONNES = [('appreciation', sa.String(30)), ('appreciation_commentaire', sa.Text()),
            ('appreciation_le', sa.DateTime()), ('appreciation_par_id', sa.Integer())]


def upgrade():
    existantes = {c['name'] for c in sa.inspect(op.get_bind()).get_columns('recommandations')}
    for nom, type_ in COLONNES:
        if nom not in existantes:
            op.add_column('recommandations', sa.Column(nom, type_, nullable=True))


def downgrade():
    existantes = {c['name'] for c in sa.inspect(op.get_bind()).get_columns('recommandations')}
    for nom, _ in COLONNES:
        if nom in existantes:
            op.drop_column('recommandations', nom)
