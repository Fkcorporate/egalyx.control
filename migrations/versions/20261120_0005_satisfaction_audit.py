"""Questionnaire de satisfaction des audités en fin de mission (20/11/2026).

  - table satisfaction_audit (egalyx/satisfaction_audit.py).
Idempotente : ne fait rien de ce qui existe déjà (bases mises à niveau au démarrage).

Revision ID: egalyx_0005_satisfaction_audit
Revises: egalyx_0004_dossier_fige
Create Date: 2026-11-20 17:30:00
"""
import sqlalchemy as sa
from alembic import op

revision = 'egalyx_0005_satisfaction_audit'
down_revision = 'egalyx_0004_dossier_fige'
branch_labels = None
depends_on = None


def upgrade():
    if 'satisfaction_audit' in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        'satisfaction_audit',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('client_id', sa.Integer, sa.ForeignKey('clients.id'), nullable=False, index=True),
        sa.Column('audit_id', sa.Integer, sa.ForeignKey('audits.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('user_id', sa.Integer, sa.ForeignKey('user.id'), nullable=False),
        sa.Column('notes', sa.JSON),
        sa.Column('commentaire', sa.Text),
        sa.Column('repondu_le', sa.DateTime),
        sa.UniqueConstraint('audit_id', 'user_id', name='uq_satisfaction_audit_user'),
    )


def downgrade():
    raise RuntimeError("La révision 0005 ne se défait pas (perte des réponses de satisfaction) : "
                       "restaurez une sauvegarde de la base si nécessaire.")
