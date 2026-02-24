from datetime import datetime
from flask import current_app
from models import db, Notification, User

class NotificationService:
    """Service pour gérer les notifications avec vérification des préférences"""
    
    @staticmethod
    def create_notification(destinataire_id, type_notification, titre, message, 
                           entite_type=None, entite_id=None, urgence='normal',
                           actions_possibles=None, donnees_supplementaires=None):
        """
        Crée une notification en vérifiant les préférences de l'utilisateur
        """
        try:
            # Récupérer l'utilisateur
            user = User.query.get(destinataire_id)
            if not user:
                print(f"❌ Utilisateur {destinataire_id} non trouvé")
                return None
            
            # Vérifier les préférences WEB
            notification_type_key = type_notification
            
            # Mapping des types vers les clés de préférences
            preference_mapping = {
                'nouvelle_constatation': 'nouvelle_constatation',
                'nouvelle_recommandation': 'nouvelle_recommandation',
                'nouveau_plan': 'nouveau_plan',
                'echeance': 'echeance_7j',  # Utilise echeance_7j par défaut
                'retard': 'retard',
                'validation_requise': 'validation_requise',
                'kri_alerte': 'kri_alerte',
                'veille_nouvelle': 'veille_nouvelle',
                'audit_demarre': 'audit_demarre',
                'audit_termine': 'audit_termine',
                'risque_evalue': 'risque_evalue',
                'systeme': 'systeme',
                'info': 'info',
                'success': 'success',
                'warning': 'warning',
                'error': 'error'
            }
            
            preference_key = preference_mapping.get(notification_type_key, notification_type_key)
            
            # Vérifier si l'utilisateur a désactivé cette notification
            if not user.should_receive_notification(preference_key, 'web'):
                print(f"📭 Notification {type_notification} désactivée pour {user.username}")
                return None
            
            # Créer la notification
            notification = Notification(
                destinataire_id=destinataire_id,
                type_notification=type_notification,
                titre=titre,
                message=message,
                urgence=urgence,
                entite_type=entite_type,
                entite_id=entite_id,
                actions_possibles=actions_possibles or [],
                donnees_supplementaires=donnees_supplementaires or {},
                client_id=user.client_id
            )
            
            db.session.add(notification)
            db.session.commit()
            
            print(f"✅ Notification créée pour {user.username}: {titre}")
            return notification
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Erreur création notification: {e}")
            return None
    
    @staticmethod
    def notify_constatation_created(constatation_id, created_by_id):
        """Notifier la création d'une constatation"""
        from models import Constatation
        
        constatation = Constatation.query.get(constatation_id)
        if not constatation:
            return None
        
        audit = constatation.audit
        
        # Trouver qui notifier
        recipients = set()
        
        # 1. Responsable de l'audit
        if audit.responsable_id:
            recipients.add(audit.responsable_id)
        
        # 2. Membres de l'équipe d'audit
        if audit.equipe_audit_ids:
            try:
                equipe_ids = [int(id.strip()) for id in audit.equipe_audit_ids.split(',') if id.strip()]
                recipients.update(equipe_ids)
            except:
                pass
        
        # 3. Observateurs
        if audit.observateurs_ids:
            try:
                observateur_ids = [int(id.strip()) for id in audit.observateurs_ids.split(',') if id.strip()]
                recipients.update(observateur_ids)
            except:
                pass
        
        # Enlever le créateur de la liste
        recipients.discard(created_by_id)
        
        # Créer les notifications
        notifications = []
        for user_id in recipients:
            notification = NotificationService.create_notification(
                destinataire_id=user_id,
                type_notification='nouvelle_constatation',
                titre=f'Nouvelle constatation dans l\'audit {audit.reference}',
                message=f'Une nouvelle constatation a été créée dans l\'audit "{audit.titre}".',
                entite_type='constatation',
                entite_id=constatation_id,
                urgence='important' if constatation.gravite == 'critique' else 'normal'
            )
            if notification:
                notifications.append(notification)
        
        return notifications
    
    @staticmethod
    def notify_recommandation_created(recommandation_id, created_by_id):
        """Notifier la création d'une recommandation"""
        from models import Recommandation
        
        recommandation = Recommandation.query.get(recommandation_id)
        if not recommandation:
            return None
        
        audit = recommandation.audit
        
        # Trouver qui notifier
        recipients = set()
        
        # 1. Responsable de l'audit
        if audit.responsable_id:
            recipients.add(audit.responsable_id)
        
        # 2. Responsable de la recommandation
        if recommandation.responsable_id:
            recipients.add(recommandation.responsable_id)
        
        # Enlever le créateur
        recipients.discard(created_by_id)
        
        # Créer les notifications
        notifications = []
        for user_id in recipients:
            notification = NotificationService.create_notification(
                destinataire_id=user_id,
                type_notification='nouvelle_recommandation',
                titre=f'Nouvelle recommandation dans l\'audit {audit.reference}',
                message=f'Une nouvelle recommandation a été créée dans l\'audit "{audit.titre}".',
                entite_type='recommandation',
                entite_id=recommandation_id,
                urgence='important'
            )
            if notification:
                notifications.append(notification)
        
        return notifications
    
    @staticmethod
    def notify_plan_action_created(plan_id, created_by_id):
        """Notifier la création d'un plan d'action"""
        from models import PlanAction
        
        plan = PlanAction.query.get(plan_id)
        if not plan:
            return None
        
        audit = plan.audit
        
        # Trouver qui notifier
        recipients = set()
        
        # 1. Responsable du plan
        if plan.responsable_id:
            recipients.add(plan.responsable_id)
        
        # 2. Responsable de l'audit
        if audit.responsable_id:
            recipients.add(audit.responsable_id)
        
        # Enlever le créateur
        recipients.discard(created_by_id)
        
        # Créer les notifications
        notifications = []
        for user_id in recipients:
            notification = NotificationService.create_notification(
                destinataire_id=user_id,
                type_notification='nouveau_plan',
                titre=f'Nouveau plan d\'action dans l\'audit {audit.reference}',
                message=f'Un nouveau plan d\'action a été créé dans l\'audit "{audit.titre}".',
                entite_type='plan_action',
                entite_id=plan_id,
                urgence='important'
            )
            if notification:
                notifications.append(notification)
        
        return notifications
    
    @staticmethod
    def check_echeances():
        """Vérifier les échéances et créer des notifications"""
        from models import PlanAction, Recommandation
        
        aujourdhui = datetime.utcnow().date()
        
        # 1. Vérifier les plans d'action
        plans = PlanAction.query.filter_by(is_archived=False).all()
        
        for plan in plans:
            if plan.date_fin_prevue:
                jours_restants = (plan.date_fin_prevue - aujourdhui).days
                
                if 0 < jours_restants <= 7 and plan.statut not in ['termine', 'suspendu']:
                    # Notifier le responsable
                    if plan.responsable_id:
                        if jours_restants == 7:
                            preference_key = 'echeance_7j'
                        elif jours_restants == 3:
                            preference_key = 'echeance_3j'
                        elif jours_restants == 1:
                            preference_key = 'echeance_1j'
                        else:
                            preference_key = 'echeance'
                        
                        NotificationService.create_notification(
                            destinataire_id=plan.responsable_id,
                            type_notification='echeance',
                            titre=f'Échéance proche pour le plan "{plan.nom}"',
                            message=f'Le plan "{plan.nom}" arrive à échéance dans {jours_restants} jours.',
                            entite_type='plan_action',
                            entite_id=plan.id,
                            urgence='urgent' if jours_restants <= 3 else 'important'
                        )
        
        # 2. Vérifier les recommandations
        recommandations = Recommandation.query.filter_by(is_archived=False).all()
        
        for recommandation in recommandations:
            if recommandation.date_echeance:
                jours_restants = (recommandation.date_echeance - aujourdhui).days
                
                if 0 < jours_restants <= 7 and recommandation.statut != 'termine':
                    # Notifier le responsable
                    if recommandation.responsable_id:
                        NotificationService.create_notification(
                            destinataire_id=recommandation.responsable_id,
                            type_notification='echeance',
                            titre=f'Échéance proche pour la recommandation',
                            message=f'La recommandation arrive à échéance dans {jours_restants} jours.',
                            entite_type='recommandation',
                            entite_id=recommandation.id,
                            urgence='urgent' if jours_restants <= 3 else 'important'
                        )

    def verifier_et_notifier():
    """
    Vérification automatique et notifications
    À exécuter via cron job
    """
    dispositifs = DispositifMaitrise.query.filter_by(is_archived=False).all()
    
    alertes = []
    for d in dispositifs:
        criticite = d.get_matrice_criticite()
        
        # Alerte si vérification en retard
        if d.prochaine_verification and d.prochaine_verification < datetime.now().date():
            alertes.append({
                'type': 'RETARD_VERIFICATION',
                'dispositif': d.reference,
                'message': f"Vérification en retard de {(datetime.now().date() - d.prochaine_verification).days} jours",
                'responsable': d.responsable.email if d.responsable else None
            })
        
        # Alerte si efficacité critique
        if d.efficacite_reelle and d.efficacite_reelle < 2:
            alertes.append({
                'type': 'EFFICACITE_CRITIQUE',
                'dispositif': d.reference,
                'message': f"Efficacité critique: {d.efficacite_reelle}/5",
                'responsable': d.responsable.email if d.responsable else None
            })
        
        # Alerte si écart important
        if d.efficacite_reelle and d.efficacite_attendue:
            if d.efficacite_attendue - d.efficacite_reelle >= 2:
                alertes.append({
                    'type': 'ECART_CRITIQUE',
                    'dispositif': d.reference,
                    'message': f"Écart critique: {d.efficacite_reelle}/5 vs {d.efficacite_attendue}/5 attendu",
                    'responsable': d.responsable.email if d.responsable else None
                })
    
    return alertes
