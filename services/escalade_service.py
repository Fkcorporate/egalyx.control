# services/escalade_service.py
from datetime import datetime, timedelta
from flask import current_app
from models import db, Incident, Notification, User, IncidentHistorique

class EscaladeService:
    """Service de gestion des escalades d'incidents - Version EXCELLENTE"""
    
    @staticmethod
    def verifier_et_escalader_auto():
        """Vérifie TOUS les incidents et escalade automatiquement si nécessaire"""
        with current_app.app_context():
            maintenant = datetime.utcnow()
            incidents = Incident.query.filter(
                Incident.statut.in_(['ouvert', 'en_cours']),
                Incident.is_archived == False
            ).all()
            
            escalades_declenchees = 0
            for incident in incidents:
                if incident.niveau_escalade >= 3:
                    continue
                
                # Vérifier escalade niveau 2
                if incident.niveau_escalade == 1:
                    date_limite = incident.created_at + timedelta(hours=incident.delai_escalade_niveau2)
                    if maintenant > date_limite and not incident.notification_envoyee_niveau2:
                        if EscaladeService.escalader(incident, auto=True, raison=f"Délai dépassé ({incident.delai_escalade_niveau2}h sans résolution)"):
                            escalades_declenchees += 1
                            print(f"⚠️ Escalade auto niveau 2 pour {incident.reference}")
                
                # Vérifier escalade niveau 3
                elif incident.niveau_escalade == 2:
                    date_limite = incident.escalation_date + timedelta(hours=incident.delai_escalade_niveau3)
                    if maintenant > date_limite and not incident.notification_envoyee_niveau3:
                        if EscaladeService.escalader(incident, auto=True, raison=f"Nouveau délai dépassé ({incident.delai_escalade_niveau3}h sans résolution)"):
                            escalades_declenchees += 1
                            print(f"⚠️ Escalade auto niveau 3 pour {incident.reference}")
            
            db.session.commit()
            return escalades_declenchees
    
    @staticmethod
    def escalader(incident, auto=False, raison=None, user_id=None):
        """Escalade un incident au niveau supérieur"""
        if incident.niveau_escalade >= 3:
            return False
        
        ancien_niveau = incident.niveau_escalade
        incident.niveau_escalade += 1
        incident.escalation_date = datetime.utcnow()
        incident.escalation_auto = auto
        incident.raison_escalade = raison
        incident.updated_at = datetime.utcnow()
        
        # Mettre à jour les notifications envoyées
        if incident.niveau_escalade == 2:
            incident.notification_envoyee_niveau2 = True
        elif incident.niveau_escalade == 3:
            incident.notification_envoyee_niveau3 = True
        
        # Changer le responsable selon le niveau
        nouveau_responsable = None
        if incident.niveau_escalade == 2 and incident.superviseur_id:
            nouveau_responsable = incident.superviseur_id
        elif incident.niveau_escalade == 3 and incident.directeur_id:
            nouveau_responsable = incident.directeur_id
        
        ancien_responsable = incident.responsable_resolution_id
        
        if nouveau_responsable:
            incident.responsable_resolution_id = nouveau_responsable
        
        # Journaliser l'historique
        historique = IncidentHistorique(
            incident_id=incident.id,
            action=f'escalade_niveau_{incident.niveau_escalade}',
            details=f"Escalade {'automatique' if auto else 'manuelle'}: {raison or 'Non spécifiée'}",
            utilisateur_id=user_id,
            created_at=datetime.utcnow()
        )
        db.session.add(historique)
        
        # Créer les notifications
        EscaladeService._creer_notifications_escalade(incident, ancien_responsable, nouveau_responsable, auto)
        
        db.session.commit()
        return True
    
    @staticmethod
    def retro_escalader(incident, niveau_cible=1, raison=None):
        """Redescend un incident à un niveau inférieur"""
        if niveau_cible >= incident.niveau_escalade:
            return False
        
        ancien_niveau = incident.niveau_escalade
        incident.niveau_escalade = niveau_cible
        incident.raison_escalade = raison
        incident.updated_at = datetime.utcnow()
        
        # Remettre le responsable approprié
        if niveau_cible == 1:
            # Garder le responsable actuel
            pass
        elif niveau_cible == 2:
            incident.responsable_resolution_id = incident.superviseur_id
        
        # Journaliser
        historique = IncidentHistorique(
            incident_id=incident.id,
            action=f'retro_escalade_niveau_{niveau_cible}',
            details=f"Rétro-escalade: {raison}",
            utilisateur_id=None,
            created_at=datetime.utcnow()
        )
        db.session.add(historique)
        
        db.session.commit()
        return True
    
    @staticmethod
    def _creer_notifications_escalade(incident, ancien_responsable_id, nouveau_responsable_id, auto):
        """Crée les notifications pour l'escalade"""
        
        # Niveau d'urgence
        urgence = 'urgent' if incident.niveau_escalade >= 2 else 'important'
        
        # Message personnalisé
        raison = incident.raison_escalade or "Délai dépassé" if auto else "Escalade manuelle"
        
        if incident.niveau_escalade == 2:
            message = f"L'incident {incident.reference} a été escaladé au niveau 2 (Superviseur). Raison: {raison}"
        else:
            message = f"L'incident {incident.reference} a été escaladé au niveau 3 (Direction). Raison: {raison}"
        
        # Notification pour le nouveau responsable
        if nouveau_responsable_id:
            notification = Notification(
                type_notification='escalade',
                titre=f"⚠️ Incident escaladé - Niveau {incident.niveau_escalade}",
                message=message,
                destinataire_id=nouveau_responsable_id,
                entite_type='incident',
                entite_id=incident.id,
                urgence=urgence,
                donnees_supplementaires={
                    'incident_reference': incident.reference,
                    'ancien_niveau': incident.niveau_escalade - 1,
                    'nouveau_niveau': incident.niveau_escalade,
                    'auto': auto,
                    'raison': raison
                },
                created_at=datetime.utcnow(),
                client_id=incident.client_id
            )
            db.session.add(notification)
        
        # Notification pour l'ancien responsable
        if ancien_responsable_id and ancien_responsable_id != nouveau_responsable_id:
            notification_ancien = Notification(
                type_notification='info',
                titre=f"Incident {incident.reference} - Changement de responsable",
                message=f"L'incident {incident.reference} a été transféré au niveau {incident.niveau_escalade}. Vous n'êtes plus responsable.",
                destinataire_id=ancien_responsable_id,
                entite_type='incident',
                entite_id=incident.id,
                urgence='normal',
                created_at=datetime.utcnow(),
                client_id=incident.client_id
            )
            db.session.add(notification_ancien)
        
        # Notification d'alerte pour les admins (escalade auto uniquement)
        if auto:
            from models import User
            admins = User.query.filter_by(role='admin', is_active=True).all()
            for admin in admins:
                notification_admin = Notification(
                    type_notification='warning',
                    titre=f"🚨 Escalade automatique - {incident.reference}",
                    message=f"L'incident {incident.reference} a été automatiquement escaladé au niveau {incident.niveau_escalade}. Raison: {raison}",
                    destinataire_id=admin.id,
                    entite_type='incident',
                    entite_id=incident.id,
                    urgence='urgent',
                    created_at=datetime.utcnow(),
                    client_id=incident.client_id
                )
                db.session.add(notification_admin)
    
    @staticmethod
    def get_incidents_escalades(user_id, client_id=None):
        """Récupère les incidents escaladés dont l'utilisateur est responsable"""
        query = Incident.query.filter(
            Incident.niveau_escalade >= 2,
            Incident.statut.in_(['ouvert', 'en_cours']),
            Incident.responsable_resolution_id == user_id,
            Incident.is_archived == False
        )
        if client_id:
            query = query.filter(Incident.client_id == client_id)
        
        return query.order_by(Incident.escalation_date.desc()).all()
    
    @staticmethod
    def get_stats_escalade(client_id=None):
        """Statistiques d'escalade"""
        query = Incident.query.filter(Incident.is_archived == False)
        if client_id:
            query = query.filter(Incident.client_id == client_id)
        
        total = query.count()
        stats = {
            'total_escalades': query.filter(Incident.niveau_escalade > 1).count(),
            'niveau_2': query.filter(Incident.niveau_escalade == 2).count(),
            'niveau_3': query.filter(Incident.niveau_escalade == 3).count(),
            'escalades_auto': query.filter(Incident.escalation_auto == True).count(),
            'taux_escalade': 0
        }
        
        if total > 0:
            stats['taux_escalade'] = round((stats['total_escalades'] / total) * 100, 1)
        
        return stats
