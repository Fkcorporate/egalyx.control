"""Recommandations externes : entité saisie à la main + appréciation (niveau + commentaire).

Revision ID: egalyx_0008_externe_entite
Revises: egalyx_0007_appreciation_reco
Idempotente : egalyx/base_donnees.py ajoute aussi ces colonnes au démarrage.
"""
import sqlalchemy as sa
from alembic import op

revision = 'egalyx_0008_externe_entite'
down_revision = 'egalyx_0007_appreciation_reco'
branch_labels = None
depends_on = None

COLONNES = [('entite_type', sa.String(30)), ('entite_nom', sa.String(200)),
            ('appreciation', sa.String(30)), ('appreciation_commentaire', sa.Text()),
            ('appreciation_le', sa.DateTime()), ('appreciation_par_id', sa.Integer())]


def upgrade():
    existantes = {c['name'] for c in sa.inspect(op.get_bind()).get_columns('recommandations_externes')}
    for nom, type_ in COLONNES:
        if nom not in existantes:
            op.add_column('recommandations_externes', sa.Column(nom, type_, nullable=True))


def downgrade():
    existantes = {c['name'] for c in sa.inspect(op.get_bind()).get_columns('recommandations_externes')}
    for nom, _ in COLONNES:
        if nom in existantes:
            op.drop_column('recommandations_externes', nom)
