"""Fonction d'audit interne : univers d'audit, évaluations qualité (normes IIA 2024), charte d'audit (20/11/2026).

  - tables entites_auditables, evaluations_qualite_audit, chartes_audit ;
  - audits.entite_auditable_id (lien d'un audit à une entité de l'univers).
Idempotente : ne fait rien de ce qui existe déjà (bases mises à niveau au démarrage).

Revision ID: egalyx_0011_fonction_audit
Revises: egalyx_0010_lm_afficher_titre
Create Date: 2026-11-25 23:00:00
(Réintégrée le 25/11/2026 : livrée le 20/11 en 0006, absente du dépôt ; renumérotée après 0010.)
"""
import sqlalchemy as sa
from alembic import op

revision = 'egalyx_0011_fonction_audit'
down_revision = 'egalyx_0010_lm_afficher_titre'
branch_labels = None
depends_on = None


def upgrade():
    insp = sa.inspect(op.get_bind())
    tables = set(insp.get_table_names())
    if 'entite_auditable_id' not in {c['name'] for c in insp.get_columns('audits')}:
        op.add_column('audits', sa.Column('entite_auditable_id', sa.Integer, nullable=True))
        op.create_index('ix_audits_entite_auditable_id', 'audits', ['entite_auditable_id'])
    if 'entites_auditables' not in tables:
        op.create_table(
            'entites_auditables',
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('client_id', sa.Integer, sa.ForeignKey('clients.id'), nullable=False, index=True),
            sa.Column('nom', sa.String(200), nullable=False),
            sa.Column('type_entite', sa.String(30)),
            sa.Column('processus_id', sa.Integer),
            sa.Column('direction_id', sa.Integer),
            sa.Column('responsable', sa.String(150)),
            sa.Column('niveau_risque', sa.String(10)),
            sa.Column('cycle_annees', sa.Integer),
            sa.Column('dernier_audit_manuel', sa.Date),
            sa.Column('commentaire', sa.Text),
            sa.Column('actif', sa.Boolean),
            sa.Column('created_at', sa.DateTime),
            sa.Column('updated_at', sa.DateTime),
        )
    if 'evaluations_qualite_audit' not in tables:
        op.create_table(
            'evaluations_qualite_audit',
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('client_id', sa.Integer, sa.ForeignKey('clients.id'), nullable=False, index=True),
            sa.Column('type_evaluation', sa.String(10), nullable=False),
            sa.Column('annee', sa.Integer, nullable=False),
            sa.Column('date_evaluation', sa.Date),
            sa.Column('evaluateur', sa.String(200)),
            sa.Column('reponses', sa.JSON),
            sa.Column('conclusion', sa.String(20)),
            sa.Column('synthese', sa.Text),
            sa.Column('statut', sa.String(10)),
            sa.Column('valide_le', sa.DateTime),
            sa.Column('valide_par_id', sa.Integer),
            sa.Column('created_by', sa.Integer),
            sa.Column('created_at', sa.DateTime),
            sa.Column('updated_at', sa.DateTime),
        )
    if 'chartes_audit' not in tables:
        op.create_table(
            'chartes_audit',
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('client_id', sa.Integer, sa.ForeignKey('clients.id'), nullable=False, index=True),
            sa.Column('version', sa.Integer, nullable=False),
            sa.Column('texte', sa.Text),
            sa.Column('statut', sa.String(12)),
            sa.Column('approuvee_le', sa.Date),
            sa.Column('approuvee_par', sa.String(200)),
            sa.Column('revue_prevue', sa.Date),
            sa.Column('created_by', sa.Integer),
            sa.Column('created_at', sa.DateTime),
            sa.Column('updated_at', sa.DateTime),
            sa.UniqueConstraint('client_id', 'version', name='uq_charte_audit_version'),
        )


def downgrade():
    raise RuntimeError("La révision 0011 ne se défait pas (perte de l'univers d'audit, des évaluations et des chartes) : "
                       "restaurez une sauvegarde de la base si nécessaire.")
