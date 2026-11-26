"""Analyse des données d'audit (lot 1 : achats, fournisseurs, paiements) — egalyx/analyse_donnees.py.

Tables analyses_donnees et analyses_donnees_jeux.
Idempotente : ne crée que ce qui manque (les tables sont aussi créées au démarrage).

Revision ID: egalyx_0013_analyse_donnees
Revises: egalyx_0012_redaction_rapport
Create Date: 2026-11-26 15:00:00
"""
import sqlalchemy as sa
from alembic import op

revision = 'egalyx_0013_analyse_donnees'
down_revision = 'egalyx_0012_redaction_rapport'
branch_labels = None
depends_on = None


def upgrade():
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if 'analyses_donnees' not in tables:
        op.create_table(
            'analyses_donnees',
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('client_id', sa.Integer, sa.ForeignKey('clients.id'), nullable=False, index=True),
            sa.Column('audit_id', sa.Integer, sa.ForeignKey('audits.id'), nullable=False, index=True),
            sa.Column('reference', sa.String(40)),
            sa.Column('titre', sa.String(200), nullable=False),
            sa.Column('devise', sa.String(10)),
            sa.Column('tests_choisis', sa.JSON),
            sa.Column('parametres', sa.JSON),
            sa.Column('resultats', sa.JSON),
            sa.Column('execution', sa.JSON),
            sa.Column('synthese', sa.JSON),
            sa.Column('liens', sa.JSON),
            sa.Column('created_by', sa.Integer, sa.ForeignKey('user.id')),
            sa.Column('created_at', sa.DateTime),
            sa.Column('updated_at', sa.DateTime),
        )
    if 'analyses_donnees_jeux' not in tables:
        op.create_table(
            'analyses_donnees_jeux',
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('analyse_id', sa.Integer, sa.ForeignKey('analyses_donnees.id'), nullable=False, index=True),
            sa.Column('client_id', sa.Integer, sa.ForeignKey('clients.id'), nullable=False, index=True),
            sa.Column('type_jeu', sa.String(30), nullable=False),
            sa.Column('nom_fichier', sa.String(255)),
            sa.Column('empreinte', sa.String(64)),
            sa.Column('taille', sa.Integer),
            sa.Column('format', sa.String(20)),
            sa.Column('feuille', sa.String(100)),
            sa.Column('entetes', sa.JSON),
            sa.Column('correspondance', sa.JSON),
            sa.Column('qualite', sa.JSON),
            sa.Column('nb_lignes', sa.Integer),
            sa.Column('statut', sa.String(20)),
            sa.Column('chemin_brut', sa.String(400)),
            sa.Column('chemin_normalise', sa.String(400)),
            sa.Column('chiffre', sa.Boolean),
            sa.Column('importe_par', sa.Integer, sa.ForeignKey('user.id')),
            sa.Column('importe_le', sa.DateTime),
            sa.Column('expire_le', sa.DateTime),
            sa.Column('supprime_le', sa.DateTime),
        )


def downgrade():
    raise RuntimeError("La révision 0013 ne se défait pas (perte des analyses de données et de leurs résultats) : "
                       "restaurez une sauvegarde de la base si nécessaire.")
