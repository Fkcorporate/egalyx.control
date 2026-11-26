"""Rédaction du rapport d'audit propre à la mission : résumé exécutif et conclusion (egalyx/ia_audit.py).

Revision ID: egalyx_0012_redaction_rapport
Revises: egalyx_0011_fonction_audit
Idempotente : egalyx/base_donnees.py ajoute aussi cette colonne au démarrage.
"""
import sqlalchemy as sa
from alembic import op

revision = 'egalyx_0012_redaction_rapport'
down_revision = 'egalyx_0011_fonction_audit'
branch_labels = None
depends_on = None


def upgrade():
    if 'redaction_rapport' not in {c['name'] for c in sa.inspect(op.get_bind()).get_columns('audits')}:
        op.add_column('audits', sa.Column('redaction_rapport', sa.JSON(), nullable=True))


def downgrade():
    if 'redaction_rapport' in {c['name'] for c in sa.inspect(op.get_bind()).get_columns('audits')}:
        op.drop_column('audits', 'redaction_rapport')
