"""Statuts : une seule écriture par objet (19/11/2026).

Convertit les variantes enregistrées (« terminee » pour un plan d'audit, « à_améliorer » pour un dispositif,
« close » pour une non-conformité du contrôle N2…) vers le vocabulaire de chaque objet : egalyx/statuts.py.
Idempotente. Ne se défait pas (les anciennes variantes n'avaient pas de sens propre).

Revision ID: egalyx_0003_statuts
Revises: egalyx_0002_localisation_lettres
Create Date: 2026-11-19 12:00:00
"""
from alembic import op

revision = 'egalyx_0003_statuts'
down_revision = 'egalyx_0002_localisation_lettres'
branch_labels = None
depends_on = None


def upgrade():
    from egalyx.statuts import convertir_base
    convertir_base(op.get_bind())


def downgrade():
    pass    # rien à défaire : les valeurs converties sont les valeurs normales
