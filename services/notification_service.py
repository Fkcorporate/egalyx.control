# services/notification_service.py
from datetime import datetime, timedelta
from flask import current_app
from models import db, Notification, User, Audit, Constatation, Recommandation, PlanAction, KRI, MesureKRI

class NotificationService:
    
    @staticmethod
    def create(destinataire_id, type_notif, titre, message, **kwargs):
        """
        Créer une notification intelligente
        """
        # Vérifier les préférences utilisateur
        user = User.query.get(destinataire_id)
        if not user:
            current_app.logger.error(f"Utilisateur {destinataire_id} non trouvé")
            return None
        
        # Vérifier si l'utilisateur a mis en pause les notifications
        prefs = user.preferences_notifications
        pause_until = prefs.get('pause_until')
        if pause_until:
            try:
                pause_date = datetime.fromisoformat(pause_until)
                if datetime.utcnow() < pause_date:
                    current_app.logger.info(f"Notifications en pause pour l'utilisateur {destinataire_id}")
                    return None
            except (ValueError, TypeError):
                pass
        
        # Vérifier la préférence web
        if not user.get_notification_preference('web', type_notif):
            current_app.logger.info(f"Notification web désactivée pour {type_notif}")
            # On crée quand même la notification, mais on pourra la filtrer côté client
        
        # Déterminer l'urgence automatiquement
        urgence = kwargs.get('urgence', Notification.URGENCE_NORMAL)
        if type_notif in [Notification.TYPE_ECHEANCE, Notification.TYPE_RETARD, Notification.TYPE_KRI_ALERTE]:
            urgence = Notification.URGENCE_IMPORTANT
        elif 'urgent' in titre.lower() or 'critique' in titre.lower():
            urgence = Notification.URGENCE_URGENT
        
        # Déterminer la date d'expiration
        expires_at = None
        if type_notif == Notification.TYPE_ECHEANCE:
            expires_at = datetime.utcnow() + timedelta(days=7)
        elif type_notif == Notification.TYPE_RETARD:
            expires_at = datetime.utcnow() + timedelta(days=14)
        else:
            expires_at = datetime.utcnow() + timedelta(days=30)
        
        try:
            notification = Notification(
                destinataire_id=destinataire_id,
                type_notification=type_notif,
                titre=titre,
                message=message,
                urgence=urgence,
                entite_type=kwargs.get('entite_type'),
                entite_id=kwargs.get('entite_id'),
                actions_possibles=kwargs.get('actions', []),
                donnees_supplementaires=kwargs.get('donnees', {}),  # Renommé
                expires_at=expires_at,
                created_at=datetime.utcnow()
            )
            
            db.session.add(notification)
            db.session.flush()
            
            db.session.commit()
            
            current_app.logger.info(f"✅ Notification créée: {notification.id} pour utilisateur {destinataire_id}")
            return notification
            
        except Exception as e:
            current_app.logger.error(f"❌ Erreur création notification: {e}")
            db.session.rollback()
            return None
    
    @staticmethod
    def notify_constatation_created(constatation, createur_id):
        """Notifier la création d'une constatation"""
        if not hasattr(constatation, 'audit'):
            return
        
        audit = constatation.audit
        
        # Liste des destinataires
        destinataires = set()
        
        # Responsable de l'audit
        if audit.responsable_id and audit.responsable_id != createur_id:
            destinataires.add(audit.responsable_id)
        
        # Équipe d'audit
        if audit.equipe_audit_ids:
            try:
                equipe_ids = [int(id.strip()) for id in audit.equipe_audit_ids.split(',') if id.strip()]
                for user_id in equipe_ids:
                    if user_id != createur_id:
                        destinataires.add(user_id)
            except:
                pass
        
        # Notifier chaque destinataire
        for user_id in destinataires:
            actions = [
                {'url': f'/audit/constatation/{constatation.id}', 'label': 'Voir la constatation', 'icon': 'eye'},
                {'url': f'/audit/{audit.id}', 'label': "Voir l'audit", 'icon': 'clipboard-list'}
            ]
            
            NotificationService.create(
                destinataire_id=user_id,
                type_notif=Notification.TYPE_CONSTATATION,
                titre=f'Nouvelle constatation: {constatation.reference}',
                message=constatation.description[:150] + ('...' if len(constatation.description) > 150 else ''),
                entite_type='constatation',
                entite_id=constatation.id,
                actions=actions,
                donnees={
                    'audit_id': audit.id,
                    'audit_titre': audit.titre,
                    'createur_id': createur_id,
                    'gravite': constatation.gravite if hasattr(constatation, 'gravite') else None
                }
            )
    
    @staticmethod
    def notify_plan_echeance(plan):
        """Notifier les échéances de plans d'action"""
        if not plan.responsable_id or not hasattr(plan, 'date_fin_prevue') or not plan.date_fin_prevue:
            return
        
        jours_restants = (plan.date_fin_prevue - datetime.utcnow().date()).days
        
        if jours_restants == 7:
            type_notif = Notification.TYPE_ECHEANCE
            urgence = Notification.URGENCE_NORMAL
            message = f"Le plan d'action '{plan.nom}' arrive à échéance dans 7 jours"
        elif jours_restants == 3:
            type_notif = Notification.TYPE_ECHEANCE
            urgence = Notification.URGENCE_IMPORTANT
            message = f"Le plan d'action '{plan.nom}' arrive à échéance dans 3 jours"
        elif jours_restants == 1:
            type_notif = Notification.TYPE_ECHEANCE
            urgence = Notification.URGENCE_IMPORTANT
            message = f"Le plan d'action '{plan.nom}' arrive à échéance demain"
        elif jours_restants < 0:
            type_notif = Notification.TYPE_RETARD
            urgence = Notification.URGENCE_URGENT
            message = f"Le plan d'action '{plan.nom}' est en retard de {abs(jours_restants)} jour(s)"
        else:
            return
        
        actions = [
            {'url': f'/audit/plan-action/{plan.id}', 'label': 'Voir le plan', 'icon': 'eye'},
            {'url': f'/audit/plan-action/{plan.id}/edit', 'label': 'Modifier', 'icon': 'edit'}
        ]
        
        NotificationService.create(
            destinataire_id=plan.responsable_id,
            type_notif=type_notif,
            titre=f"Échéance: {plan.nom}",
            message=message,
            urgence=urgence,
            entite_type='plan_action',
            entite_id=plan.id,
            actions=actions,
            donnees={
                'date_echeance': plan.date_fin_prevue.isoformat(),
                'jours_restants': jours_restants,
                'audit_id': plan.audit_id if hasattr(plan, 'audit_id') else None
            }
        )
    
    @staticmethod
    def notify_kri_alert(kri, derniere_mesure):
        """Notifier une alerte KRI"""
        if not kri.responsable_mesure_id or not derniere_mesure:
            return
        
        # Vérifier si KRI a la méthode get_etat_alerte
        if not hasattr(kri, 'get_etat_alerte'):
            return
        
        etat = kri.get_etat_alerte(derniere_mesure.valeur)
        
        if etat in ['critique', 'alerte']:
            actions = [
                {'url': f'/kri/{kri.id}', 'label': 'Voir le KRI', 'icon': 'chart-line'},
                {'url': f'/kri/{kri.id}/mesures/nouvelle', 'label': 'Ajouter mesure', 'icon': 'plus'}
            ]
            
            NotificationService.create(
                destinataire_id=kri.responsable_mesure_id,
                type_notif=Notification.TYPE_KRI_ALERTE,
                titre=f"Alerte {kri.get_type_display() if hasattr(kri, 'get_type_display') else 'KRI'}: {kri.nom}",
                message=f"Valeur: {derniere_mesure.valeur} {kri.unite_mesure if hasattr(kri, 'unite_mesure') else ''} - État: {etat}",
                urgence=Notification.URGENCE_IMPORTANT if etat == 'alerte' else Notification.URGENCE_URGENT,
                entite_type='kri',
                entite_id=kri.id,
                actions=actions,
                donnees={
                    'valeur': derniere_mesure.valeur,
                    'etat': etat,
                    'seuil_alerte': kri.seuil_alerte if hasattr(kri, 'seuil_alerte') else None,
                    'seuil_critique': kri.seuil_critique if hasattr(kri, 'seuil_critique') else None,
                    'date_mesure': derniere_mesure.date_mesure.isoformat() if hasattr(derniere_mesure, 'date_mesure') else None
                }
            )
    
    @staticmethod
    def get_notifications_non_lues(user_id):
        """Obtenir les notifications non lues d'un utilisateur"""
        return Notification.query.filter_by(
            destinataire_id=user_id, 
            est_lue=False
        ).order_by(
            Notification.created_at.desc()
        ).limit(20).all()
    
    @staticmethod
    def get_count_notifications_non_lues(user_id):
        """Compter les notifications non lues"""
        return Notification.query.filter_by(
            destinataire_id=user_id, 
            est_lue=False
        ).count()
    
    @staticmethod
    def cleanup_expired_notifications():
        """Nettoyer les notifications expirées"""
        try:
            deleted = Notification.query.filter(
                Notification.expires_at < datetime.utcnow()
            ).delete()
            
            db.session.commit()
            current_app.logger.info(f"🧹 Nettoyage: {deleted} notifications expirées supprimées")
            return deleted
            
        except Exception as e:
            current_app.logger.error(f"❌ Erreur nettoyage notifications: {e}")
            db.session.rollback()
            return 0
