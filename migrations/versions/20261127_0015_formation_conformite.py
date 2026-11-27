"""Formation à la conformité (e-learning) : modules, campagnes, affectations.

Tables formation_modules, formation_campagnes, formation_affectations.
Idempotente : ne crée que ce qui manque (les tables sont aussi créées au démarrage).

Revision ID: egalyx_0015_formation_conformite
Revises: egalyx_0014_analyse_sources
Create Date: 2026-11-27 03:00:00
"""
import sqlalchemy as sa
from alembic import op

revision = 'egalyx_0015_formation_conformite'
down_revision = 'egalyx_0014_analyse_sources'
branch_labels = None
depends_on = None


def upgrade():
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if 'formation_modules' not in tables:
        op.create_table(
            'formation_modules',
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('client_id', sa.Integer, sa.ForeignKey('clients.id'), nullable=False, index=True),
            sa.Column('titre', sa.String(200), nullable=False),
            sa.Column('resume', sa.Text),
            sa.Column('contenu', sa.Text),
            sa.Column('video_url', sa.String(500)),
            sa.Column('categorie', sa.String(50)),
            sa.Column('duree_minutes', sa.Integer),
            sa.Column('score_min', sa.Integer),
            sa.Column('questions', sa.JSON),
            sa.Column('statut', sa.String(20)),
            sa.Column('version', sa.Integer),
            sa.Column('origine', sa.String(60)),
            sa.Column('created_by', sa.Integer, sa.ForeignKey('user.id')),
            sa.Column('created_at', sa.DateTime),
            sa.Column('updated_at', sa.DateTime),
        )
    if 'formation_campagnes' not in tables:
        op.create_table(
            'formation_campagnes',
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('client_id', sa.Integer, sa.ForeignKey('clients.id'), nullable=False, index=True),
            sa.Column('module_id', sa.Integer, sa.ForeignKey('formation_modules.id'), nullable=False),
            sa.Column('titre', sa.String(200), nullable=False),
            sa.Column('message', sa.Text),
            sa.Column('date_limite', sa.Date),
            sa.Column('cible', sa.JSON),
            sa.Column('statut', sa.String(20)),
            sa.Column('derniere_relance', sa.DateTime),
            sa.Column('created_by', sa.Integer, sa.ForeignKey('user.id')),
            sa.Column('created_at', sa.DateTime),
        )
    if 'formation_affectations' not in tables:
        op.create_table(
            'formation_affectations',
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('client_id', sa.Integer, sa.ForeignKey('clients.id'), nullable=False, index=True),
            sa.Column('campagne_id', sa.Integer, sa.ForeignKey('formation_campagnes.id'), nullable=False, index=True),
            sa.Column('user_id', sa.Integer, sa.ForeignKey('user.id'), nullable=False, index=True),
            sa.Column('statut', sa.String(20)),
            sa.Column('tentatives', sa.Integer),
            sa.Column('meilleur_score', sa.Integer),
            sa.Column('dernier_score', sa.Integer),
            sa.Column('debut_le', sa.DateTime),
            sa.Column('reussi_le', sa.DateTime),
            sa.Column('version_module', sa.Integer),
            sa.Column('historique', sa.JSON),
            sa.Column('created_at', sa.DateTime),
            sa.UniqueConstraint('campagne_id', 'user_id', name='uq_formation_affectation'),
        )


def downgrade():
    raise RuntimeError("La révision 0015 ne se défait pas (perte des formations suivies et des preuves de formation) : "
                       "restaurez une sauvegarde de la base si nécessaire.")
