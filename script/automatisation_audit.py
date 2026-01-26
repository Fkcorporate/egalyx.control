#!/usr/bin/env python3
"""
Script d'automatisation des statuts d'audit
À exécuter via une tâche cron ou un scheduler
"""

from app import app, db
from models import Audit, Constatation, PlanAction
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def automatiser_statuts_audits():
    """Automatise les mises à jour de statut des audits"""
    with app.app_context():
        audits = Audit.query.filter_by(is_archived=False).all()
        
        for audit in audits:
            try:
                # Vérifier si toutes les constatations sont clôturées
                constatations_non_closes = Constatation.query.filter_by(
                    audit_id=audit.id,
                    statut='clos',
                    is_archived=False
                ).count()
                
                total_constatations = Constatation.query.filter_by(
                    audit_id=audit.id,
                    is_archived=False
                ).count()
                
                if total_constatations > 0 and constatations_non_closes == total_constatations:
                    audit.statut = 'clos'
                    audit.sous_statut = 'cloture'
                    logger.info(f"Audit {audit.reference} automatiquement clos")
                
                # Mettre à jour le sous-statut en fonction de l'avancement
                if audit.statut != 'clos':
                    if audit.progression_globale < 25:
                        audit.sous_statut = 'planification'
                    elif audit.progression_globale < 50:
                        audit.sous_statut = 'collecte'
                    elif audit.progression_globale < 75:
                        audit.sous_statut = 'analyse'
                    elif audit.progression_globale < 90:
                        audit.sous_statut = 'redaction'
                    elif audit.progression_globale < 100:
                        audit.sous_statut = 'validation'
                
                audit.updated_at = datetime.utcnow()
                db.session.commit()
                
            except Exception as e:
                logger.error(f"Erreur sur audit {audit.reference}: {e}")
                db.session.rollback()

def verifier_echeances_et_alertes():
    """Vérifie les échéances et génère des alertes"""
    with app.app_context():
        aujourdhui = datetime.utcnow().date()
        
        # Vérifier les plans d'action
        plans = PlanAction.query.filter_by(is_archived=False).all()
        
        for plan in plans:
            try:
                # Alerte 7 jours avant échéance
                if plan.date_fin_prevue:
                    jours_restants = (plan.date_fin_prevue - aujourdhui).days
                    
                    if 0 < jours_restants <= 7:
                        # Créer alerte
                        from utils import creer_notification
                        creer_notification(
                            type_notification='echeance_proche',
                            titre=f"Échéance proche pour {plan.nom}",
                            message=f"Le plan {plan.nom} arrive à échéance dans {jours_restants} jours",
                            destinataire_id=plan.responsable_id,
                            entite_type='plan_action',
                            entite_id=plan.id
                        )
                        logger.info(f"Alerte échéance pour plan {plan.nom}")
                    
                    # Alerte retard
                    elif jours_restants < 0 and plan.statut != 'termine':
                        plan.est_en_retard = True
                        
                        # Vérifier si une alerte existe déjà
                        from models import Notification
                        existing_alert = Notification.query.filter_by(
                            type_notification='retard',
                            entite_id=plan.id,
                            est_lue=False
                        ).first()
                        
                        if not existing_alert:
                            creer_notification(
                                type_notification='retard',
                                titre=f"Retard sur {plan.nom}",
                                message=f"Le plan {plan.nom} est en retard de {abs(jours_restants)} jours",
                                destinataire_id=plan.responsable_id,
                                entite_type='plan_action',
                                entite_id=plan.id
                            )
                            logger.info(f"Alerte retard pour plan {plan.nom}")
                
                db.session.commit()
                
            except Exception as e:
                logger.error(f"Erreur sur plan {plan.id}: {e}")
                db.session.rollback()

if __name__ == "__main__":
    logger.info("Démarrage de l'automatisation...")
    automatiser_statuts_audits()
    verifier_echeances_et_alertes()
    logger.info("Automatisation terminée")