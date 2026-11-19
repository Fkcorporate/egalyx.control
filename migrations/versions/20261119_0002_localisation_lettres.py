"""Heure et devise par organisation ; modèles d'en-tête des lettres de mission (19/11/2026).

  - clients.devise : code ISO de la devise de l'organisation (vide : devise de l'abonnement) ;
  - table modeles_lettre_mission : en-têtes et e-mails d'accompagnement par organisation.
Idempotente : ne fait rien de ce qui existe déjà (bases mises à niveau au démarrage).

Revision ID: egalyx_0002_localisation_lettres
Revises: egalyx_0001_reference
Create Date: 2026-11-19 09:00:00
"""
import sqlalchemy as sa
from alembic import op

revision = 'egalyx_0002_localisation_lettres'
down_revision = 'egalyx_0001_reference'
branch_labels = None
depends_on = None


def _colonnes(table):
    return {c['name'] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade():
    insp = sa.inspect(op.get_bind())
    if 'devise' not in _colonnes('clients'):
        op.add_column('clients', sa.Column('devise', sa.String(3), nullable=True))
    if 'modeles_lettre_mission' not in insp.get_table_names():
        op.create_table(
            'modeles_lettre_mission',
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('client_id', sa.Integer, sa.ForeignKey('clients.id'), nullable=False, index=True),
            sa.Column('nom', sa.String(120), nullable=False),
            sa.Column('est_defaut', sa.Boolean, default=False),
            sa.Column('actif', sa.Boolean, default=True),
            sa.Column('logo_url', sa.String(500)),
            sa.Column('logo_position', sa.String(10)),
            sa.Column('couleur', sa.String(20)),
            sa.Column('titre_entete', sa.String(200)),
            sa.Column('lignes_entete', sa.Text),
            sa.Column('mention_haut', sa.String(200)),
            sa.Column('pied_page', sa.Text),
            sa.Column('signature', sa.Text),
            sa.Column('objet_email', sa.String(250)),
            sa.Column('message_email', sa.Text),
            sa.Column('created_at', sa.DateTime),
            sa.Column('updated_at', sa.DateTime),
            sa.Column('modifie_par_id', sa.Integer, sa.ForeignKey('user.id'), nullable=True),
        )


def downgrade():
    # Défaire supprimerait les modèles de lettre et les devises choisies : on restaure une sauvegarde à la place.
    raise RuntimeError("La révision 0002 ne se défait pas (perte des modèles de lettre de mission et des devises) : "
                       "restaurez une sauvegarde de la base si nécessaire.")
