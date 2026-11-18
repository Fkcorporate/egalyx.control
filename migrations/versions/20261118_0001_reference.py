"""Référence Egalyx (18/11/2026) : met n'importe quelle base au niveau des modèles.

Révision de départ de la chaîne de migrations. Elle :
  1. crée les tables qui manquent (base neuve : toutes) ;
  2. ajoute les colonnes qui manquent aux tables existantes (sans NOT NULL, avec la valeur par défaut
     simple du modèle) — la même règle que la mise à jour automatique au démarrage (egalyx/base_donnees.py).
Elle ne supprime et ne modifie jamais rien : on peut la passer sur une base en service.

Les évolutions suivantes du schéma se font par de nouvelles révisions :
  flask --app app db migrate -m "ce qui change"   (génère le fichier, à relire)
  flask --app app db upgrade

Revision ID: egalyx_0001_reference
Revises:
Create Date: 2026-11-18 20:00:00
"""
import logging

from alembic import op
from flask import current_app
from sqlalchemy import text

revision = 'egalyx_0001_reference'
down_revision = None
branch_labels = None
depends_on = None

journal = logging.getLogger('alembic.egalyx')


def upgrade():
    db = current_app.extensions['migrate'].db
    connexion = op.get_bind()
    avant = set(connexion.dialect.get_table_names(connexion))
    db.metadata.create_all(bind=connexion, checkfirst=True)
    apres = set(connexion.dialect.get_table_names(connexion))
    journal.info('Tables créées : %s', len(apres - avant))
    from egalyx.base_donnees import colonnes_manquantes
    instructions = colonnes_manquantes(db, connexion=connexion)
    for table, colonne, sql in instructions:
        connexion.execute(text(sql))
        journal.info('Colonne ajoutée : %s.%s', table, colonne)
    journal.info('Colonnes ajoutées : %s', len(instructions))


def downgrade():
    raise RuntimeError("La révision de référence ne se défait pas : restaurez une sauvegarde (flask sauvegarder).")
