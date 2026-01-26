# tasks/notifications.py
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
from models import db, PlanAction, Recommandation, KRI, MesureKRI, Notification
from services.notification_service import NotificationService
from flask import current_app

def check_echeances_et_alertes():
    """Vérifier les échéances et générer des alertes"""
    with current_app.app_context():
        try:
            print("🔔 Vérification des échéances et alertes...")
            aujourdhui = datetime.utcnow().date()
            
            # Vérifier les plans d'action
            plans = PlanAction.query.filter_by(is_archived=False).all()
            for plan in plans:
                NotificationService.notify_plan_echeance(plan)
            
            # Vérifier les recommandations
            recommandations = Recommandation.query.filter_by(is_archived=False).all()
            for reco in recommandations:
                if reco.date_echeance:
                    jours_restants = (reco.date_echeance - aujourdhui).days
                    
                    if jours_restants <= 3 and jours_restants >= 0:
                        urgence = 'urgent' if jours_restants <= 1 else 'important'
                        NotificationService.create(
                            destinataire_id=reco.responsable_id,
                            type_notif=Notification.TYPE_ECHEANCE,
                            titre=f"Échéance recommandation: {reco.reference}",
                            message=f"La recommandation arrive à échéance dans {jours_restants} jour(s)",
                            urgence=urgence,
                            entite_type='recommandation',
                            entite_id=reco.id
                        )
            
            # Vérifier les KRI (dernière mesure > seuil)
            kris = KRI.query.filter_by(est_actif=True).all()
            for kri in kris:
                derniere_mesure = kri.get_derniere_mesure()
                if derniere_mesure:
                    NotificationService.notify_kri_alert(kri, derniere_mesure)
            
            db.session.commit()
            print("✅ Vérification des échéances terminée")
            
        except Exception as e:
            print(f"❌ Erreur vérification échéances: {e}")
            db.session.rollback()

def cleanup_old_notifications():
    """Nettoyer les anciennes notifications"""
    with current_app.app_context():
        try:
            deleted = NotificationService.cleanup_expired_notifications()
            print(f"🧹 Nettoyage terminé: {deleted} notifications supprimées")
        except Exception as e:
            print(f"❌ Erreur nettoyage: {e}")

def init_notification_tasks(app):
    """Initialiser les tâches planifiées"""
    scheduler = BackgroundScheduler()
    
    # Vérifier les échéances toutes les heures
    scheduler.add_job(
        func=check_echeances_et_alertes,
        trigger='interval',
        hours=1,
        id='check_echeances',
        name='Vérification échéances et alertes',
        replace_existing=True
    )
    
    # Nettoyer les anciennes notifications tous les jours à minuit
    scheduler.add_job(
        func=cleanup_old_notifications,
        trigger='cron',
        hour=0,
        minute=0,
        id='cleanup_notifications',
        name='Nettoyage notifications anciennes',
        replace_existing=True
    )
    
    scheduler.start()
    print("✅ Tâches de notifications planifiées démarrées")
    return scheduler