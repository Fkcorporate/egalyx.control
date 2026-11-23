"""Lettre de mission : position du pied de page (gauche, centre, droite) — 23/11/2026.

Idempotente : la colonne est aussi ajoutée au démarrage par egalyx/base_donnees.py si elle manque.

Revision ID: egalyx_0006_pied_lettre
Revises: egalyx_0005_satisfaction_audit
Create Date: 2026-11-23 21:30:00
"""
import sqlalchemy as sa
from alembic import op

revision = 'egalyx_0006_pied_lettre'
down_revision = 'egalyx_0005_satisfaction_audit'
branch_labels = None
depends_on = None


def upgrade():
    insp = sa.inspect(op.get_bind())
    if 'modeles_lettre_mission' in insp.get_table_names():
        if 'pied_position' not in {c['name'] for c in insp.get_columns('modeles_lettre_mission')}:
            op.add_column('modeles_lettre_mission', sa.Column('pied_position', sa.String(10), nullable=True, server_default='centre'))


def downgrade():
    op.drop_column('modeles_lettre_mission', 'pied_position')
