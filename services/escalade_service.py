# services/escalade_service.py
from datetime import datetime, timedelta
from flask import current_app

# Import correct de db depuis votre application
from models import db, Incident, Notification, User, IncidentHistorique

class EscaladeService:
    """Service de gestion des escalades d'incidents"""
    
    @staticmethod
    def verifier_et_escalader_auto(incident):
        """
        Vérifie si l'incident doit être escaladé automatiquement
        Retourne True si escalade effectuée
        """
        if incident.statut in ['ferme', 'resolu', 'rejete']:
            return False
        
        if incident.niveau_escalade >= 3:
            return False
        
        maintenant = datetime.utcnow()
        
        # Vérifier escalade niveau 2
        if incident.niveau_escalade == 1:
            delai = getattr(incident, 'delai_escalade_niveau2', 48)
            date_limite = incident.created_at + timedelta(hours=delai)
            
            if maintenant > date_limite and not getattr(incident, 'notification_envoyee_niveau2', False):
                return EscaladeService.escalader(incident, auto=True, raison=f"Délai dépassé ({delai}h sans résolution)")
        
        # Vérifier escalade niveau 3 - CORRIGÉ: utiliser escalation_date au lieu de escalade_date
        elif incident.niveau_escalade == 2:
            delai = getattr(incident, 'delai_escalade_niveau3', 72)
            date_limite = incident.escalation_date + timedelta(hours=delai) if incident.escalation_date else incident.created_at + timedelta(hours=delai)
            
            if maintenant > date_limite and not getattr(incident, 'notification_envoyee_niveau3', False):
                return EscaladeService.escalader(incident, auto=True, raison=f"Nouveau délai dépassé ({delai}h sans résolution)")
        
        return False
    
    @staticmethod
    def escalader(incident, auto=False, raison=None):
        """
        Escalade un incident au niveau supérieur
        Retourne True si succès
        """
        if incident.niveau_escalade >= 3:
            return False
        
        ancien_niveau = incident.niveau_escalade
        incident.niveau_escalade += 1
        # CORRIGÉ: utiliser escalation_date au lieu de escalade_date
        incident.escalation_date = datetime.utcnow()
        incident.escalation_auto = auto
        incident.raison_escalade = raison
        incident.updated_at = datetime.utcnow()
        
        # Mettre à jour la date de dernière action si l'attribut existe
        if hasattr(incident, 'derniere_action_date'):
            incident.derniere_action_date = datetime.utcnow()
        
        # Mettre à jour le responsable selon le niveau
        nouveau_responsable = None
        if incident.niveau_escalade == 2 and incident.superviseur_id:
            nouveau_responsable = incident.superviseur_id
            if hasattr(incident, 'notification_envoyee_niveau2'):
                incident.notification_envoyee_niveau2 = True
        elif incident.niveau_escalade == 3 and incident.directeur_id:
            nouveau_responsable = incident.directeur_id
            if hasattr(incident, 'notification_envoyee_niveau3'):
                incident.notification_envoyee_niveau3 = True
        
        if nouveau_responsable:
            ancien_responsable = incident.responsable_resolution_id
            incident.responsable_resolution_id = nouveau_responsable
            
            # Journaliser le changement
            historique = IncidentHistorique(
                incident_id=incident.id,
                action=f'escalade_niveau_{incident.niveau_escalade}',
                details=f"Escalade {'automatique' if auto else 'manuelle'}: {raison}",
                utilisateur_id=None,
                created_at=datetime.utcnow()
            )
            db.session.add(historique)
            
            # Créer une notification
            EscaladeService._creer_notification_escalade(incident, ancien_responsable, nouveau_responsable)
        
        db.session.commit()
        return True
    
    @staticmethod
    def retro_escalader(incident, niveau_cible=1, raison=None):
        """
        Redescend un incident à un niveau inférieur (quand résolu partiellement)
        """
        if niveau_cible >= incident.niveau_escalade:
            return False
        
        ancien_niveau = incident.niveau_escalade
        incident.niveau_escalade = niveau_cible
        incident.raison_escalade = raison
        incident.updated_at = datetime.utcnow()
        
        # Remettre le responsable approprié
        if niveau_cible == 1:
            # Garder le responsable actuel (ne pas changer)
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
    def _creer_notification_escalade(incident, ancien_responsable_id, nouveau_responsable_id):
        """Crée une notification pour le nouveau responsable"""
        from models import Notification
        
        # Niveau d'urgence
        urgence = 'urgent' if incident.niveau_escalade >= 2 else 'important'
        
        # Message personnalisé
        if incident.niveau_escalade == 2:
            message = f"L'incident {incident.reference} a été escaladé au niveau 2 (Superviseur). Raison: {incident.raison_escalade or 'Délai dépassé'}"
        else:
            message = f"L'incident {incident.reference} a été escaladé au niveau 3 (Direction). Raison: {incident.raison_escalade or 'Urgence critique'}"
        
        notification = Notification(
            type_notification='escalade',
            titre=f"Incident escaladé - Niveau {incident.niveau_escalade}",
            message=message,
            destinataire_id=nouveau_responsable_id,
            entite_type='incident',
            entite_id=incident.id,
            urgence=urgence,
            donnees_supplementaires={
                'incident_reference': incident.reference,
                'ancien_niveau': incident.niveau_escalade - 1,
                'nouveau_niveau': incident.niveau_escalade,
                'ancien_responsable_id': ancien_responsable_id,
                'nouveau_responsable_id': nouveau_responsable_id,
                'auto': incident.escalation_auto,
                'raison': incident.raison_escalade
            },
            created_at=datetime.utcnow(),
            client_id=incident.client_id
        )
        db.session.add(notification)
        
        # Aussi notifier l'ancien responsable qu'il n'est plus responsable
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
    
    @staticmethod
    def get_incidents_escalades(user_id, client_id=None):
        """Récupère les incidents escaladés dont l'utilisateur est responsable"""
        query = Incident.query.filter(
            Incident.niveau_escalade >= 2,
            Incident.statut.in_(['ouvert', 'en_cours']),
            Incident.responsable_resolution_id == user_id
        )
        
        if client_id:
            query = query.filter(Incident.client_id == client_id)
        
        # CORRIGÉ: utiliser escalation_date au lieu de escalade_date
        return query.order_by(Incident.escalation_date.desc()).all()
    
    @staticmethod
    def get_stats_escalade(client_id=None):
        """Statistiques d'escalade"""
        query = Incident.query
        
        if client_id:
            query = query.filter(Incident.client_id == client_id)
        
        stats = {
            'total_escalades': query.filter(Incident.niveau_escalade > 1).count(),
            'niveau_2': query.filter(Incident.niveau_escalade == 2).count(),
            'niveau_3': query.filter(Incident.niveau_escalade == 3).count(),
            'escalades_auto': query.filter(Incident.escalation_auto == True).count(),
            'taux_escalade': 0
        }
        
        total = query.count()
        if total > 0:
            stats['taux_escalade'] = round((stats['total_escalades'] / total) * 100, 1)
        
        return stats
