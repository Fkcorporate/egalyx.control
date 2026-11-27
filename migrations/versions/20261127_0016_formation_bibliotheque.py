"""Formation à la conformité, lot 2 : bibliothèque Egalyx, relances automatiques, KRI.

Table formation_bibliotheque ; colonnes formation_modules.origine_version, formation_campagnes.relances_auto,
derniere_relance_auto, kri_id, derniere_mesure_kri. Idempotente.

Revision ID: egalyx_0016_formation_bibliotheque
Revises: egalyx_0015_formation_conformite
Create Date: 2026-11-27 09:00:00
"""
import sqlalchemy as sa
from alembic import op

revision = 'egalyx_0016_formation_bibliotheque'
down_revision = 'egalyx_0015_formation_conformite'
branch_labels = None
depends_on = None


def upgrade():
    insp = sa.inspect(op.get_bind())
    tables = set(insp.get_table_names())
    if 'formation_bibliotheque' not in tables:
        op.create_table(
            'formation_bibliotheque',
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('code', sa.String(60), nullable=False, unique=True),
            sa.Column('titre', sa.String(200), nullable=False),
            sa.Column('resume', sa.Text),
            sa.Column('contenu', sa.Text),
            sa.Column('video_url', sa.String(500)),
            sa.Column('categorie', sa.String(50)),
            sa.Column('duree_minutes', sa.Integer),
            sa.Column('score_min', sa.Integer),
            sa.Column('questions', sa.JSON),
            sa.Column('parcours', sa.String(40)),
            sa.Column('ordre', sa.Integer),
            sa.Column('profil', sa.String(20)),
            sa.Column('version', sa.Integer),
            sa.Column('statut', sa.String(20)),
            sa.Column('updated_by', sa.Integer, sa.ForeignKey('user.id')),
            sa.Column('updated_at', sa.DateTime),
        )
    ajouts = {
        'formation_modules': [('origine_version', sa.Integer)],
        'formation_campagnes': [('relances_auto', sa.Boolean), ('derniere_relance_auto', sa.String(40)),
                                ('kri_id', sa.Integer), ('derniere_mesure_kri', sa.Date)],
    }
    for table, cols in ajouts.items():
        if table not in tables:
            continue
        existantes = {c['name'] for c in insp.get_columns(table)}
        for nom, genre in cols:
            if nom not in existantes:
                op.add_column(table, sa.Column(nom, genre, nullable=True))


def downgrade():
    raise RuntimeError("La révision 0016 ne se défait pas (bibliothèque de formation et suivi des relances) : "
                       "restaurez une sauvegarde de la base si nécessaire.")
