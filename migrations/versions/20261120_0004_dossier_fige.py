"""Dossier de mission figé après le rapport définitif ; réouverture motivée (20/11/2026).

  - audits.dossier_rouvert_le, dossier_rouvert_par_id, dossier_rouvert_motif (egalyx/dossier_fige.py).
Idempotente : ne fait rien de ce qui existe déjà (bases mises à niveau au démarrage).

Revision ID: egalyx_0004_dossier_fige
Revises: egalyx_0003_statuts
Create Date: 2026-11-20 17:00:00
"""
import sqlalchemy as sa
from alembic import op

revision = 'egalyx_0004_dossier_fige'
down_revision = 'egalyx_0003_statuts'
branch_labels = None
depends_on = None


def upgrade():
    presentes = {c['name'] for c in sa.inspect(op.get_bind()).get_columns('audits')}
    for nom, type_ in (('dossier_rouvert_le', sa.DateTime()), ('dossier_rouvert_par_id', sa.Integer()),
                       ('dossier_rouvert_motif', sa.String(500))):
        if nom not in presentes:
            op.add_column('audits', sa.Column(nom, type_, nullable=True))


def downgrade():
    for nom in ('dossier_rouvert_motif', 'dossier_rouvert_par_id', 'dossier_rouvert_le'):
        op.drop_column('audits', nom)
