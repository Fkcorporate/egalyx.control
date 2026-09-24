# services/veille_notification_service.py
"""
Service de notifications pour le module Veille Réglementaire.
Envoie des notifications aux approbateurs lors des transitions du workflow.
"""

from datetime import datetime
from models import db, Notification, User


class VeilleNotificationService:
    """Service centralisé pour les notifications de veille"""
    
    # ============================================
    # NOTIFICATION : VEILLE ENVOYÉE EN RELECTURE
    # ============================================
    @staticmethod
    def notifier_relecture(workflow, veille, envoyeur):
        """
        Notifie l'approbateur N1 que la veille est à valider.
        Appelé quand le créateur clique sur "Envoyer en relecture".
        """
        destinataires = []
        
        # 1. Approbateur désigné N1
        if workflow.approbateur_niveau1_id:
            user = User.query.get(workflow.approbateur_niveau1_id)
            if user and user.is_active:
                destinataires.append(user)
        else:
            # 2. Sinon : tous les managers du client
            managers = User.query.filter(
                User.client_id == veille.client_id,
                User.is_active == True,
                User.role.in_(['manager', 'responsable_qualite'])
            ).all()
            destinataires.extend(managers)
        
        # 3. Créer les notifications
        for user in destinataires:
            VeilleNotificationService._creer_notification(
                destinataire=user,
                type_notif='veille_a_valider',
                titre=f"🔍 Veille à valider : {veille.titre[:60]}",
                message=(
                    f"{envoyeur.username} a envoyé la veille "
                    f"'{veille.titre}' en relecture. "
                    f"Vous devez l'approuver ou la rejeter."
                ),
                urgence='important',
                entite_type='veille',
                entite_id=veille.id,
                client_id=veille.client_id,
                actions=[
                    {'label': 'Voir la veille', 'url': f'/veille/{veille.id}'},
                ]
            )
        
        return len(destinataires)
    
    # ============================================
    # NOTIFICATION : VEILLE APPROUVÉE N1
    # ============================================
    @staticmethod
    def notifier_approbation_n1(workflow, veille, approbateur):
        """
        Notifie l'approbateur N2 que la veille est à approuver définitivement.
        Appelé quand l'approbateur N1 approuve.
        """
        destinataires = []
        
        # 1. Approbateur désigné N2
        if workflow.approbateur_niveau2_id:
            user = User.query.get(workflow.approbateur_niveau2_id)
            if user and user.is_active:
                destinataires.append(user)
        else:
            # 2. Sinon : tous les directeurs/admins du client
            directeurs = User.query.filter(
                User.client_id == veille.client_id,
                User.is_active == True,
                User.role.in_(['admin', 'directeur'])
            ).all()
            destinataires.extend(directeurs)
        
        # 3. Créer les notifications
        for user in destinataires:
            VeilleNotificationService._creer_notification(
                destinataire=user,
                type_notif='veille_a_approuver',
                titre=f"✅ Veille à approuver : {veille.titre[:60]}",
                message=(
                    f"{approbateur.username} a approuvé au niveau 1 la veille "
                    f"'{veille.titre}'. Elle attend votre validation finale."
                ),
                urgence='important',
                entite_type='veille',
                entite_id=veille.id,
                client_id=veille.client_id,
                actions=[
                    {'label': 'Voir la veille', 'url': f'/veille/{veille.id}'},
                ]
            )
        
        return len(destinataires)
    
    # ============================================
    # NOTIFICATION : VEILLE APPROUVÉE N2
    # ============================================
    @staticmethod
    def notifier_approbation_n2(workflow, veille, approbateur):
        """
        Notifie le créateur + les abonnés que la veille est en vigueur.
        Appelé quand l'approbateur N2 approuve.
        """
        destinataires = []
        
        # 1. Créateur de la veille
        if veille.created_by:
            user = User.query.get(veille.created_by)
            if user and user.is_active:
                destinataires.append(user)
        
        # 2. Abonnés à la veille (futur)
        # TODO: Ajouter les abonnés
        
        # 3. Dédupliquer
        destinataires = list({u.id: u for u in destinataires}.values())
        
        # 4. Créer les notifications
        for user in destinataires:
            VeilleNotificationService._creer_notification(
                destinataire=user,
                type_notif='veille_en_vigueur',
                titre=f"🟢 Veille approuvée : {veille.titre[:60]}",
                message=(
                    f"La veille '{veille.titre}' a été approuvée définitivement "
                    f"par {approbateur.username} et est maintenant en vigueur."
                ),
                urgence='normal',
                entite_type='veille',
                entite_id=veille.id,
                client_id=veille.client_id,
                actions=[
                    {'label': 'Voir la veille', 'url': f'/veille/{veille.id}'},
                ]
            )
        
        return len(destinataires)
    
    # ============================================
    # NOTIFICATION : VEILLE REJETÉE
    # ============================================
    @staticmethod
    def notifier_rejet(workflow, veille, rejeteur, raison):
        """
        Notifie le créateur que la veille a été rejetée.
        Appelé quand un approbateur rejette.
        """
        destinataires = []
        
        # 1. Créateur de la veille
        if veille.created_by:
            user = User.query.get(veille.created_by)
            if user and user.is_active:
                destinataires.append(user)
        
        # 2. Créer les notifications
        for user in destinataires:
            VeilleNotificationService._creer_notification(
                destinataire=user,
                type_notif='veille_rejetee',
                titre=f"❌ Veille rejetée : {veille.titre[:60]}",
                message=(
                    f"{rejeteur.username} a rejeté la veille '{veille.titre}'.\n\n"
                    f"Raison : {raison}"
                ),
                urgence='urgent',
                entite_type='veille',
                entite_id=veille.id,
                client_id=veille.client_id,
                actions=[
                    {'label': 'Corriger la veille', 'url': f'/veille/modifier/{veille.id}'},
                ]
            )
        
        return len(destinataires)
    
    # ============================================
    # MÉTHODE INTERNE : CRÉER UNE NOTIFICATION
    # ============================================
    @staticmethod
    def _creer_notification(destinataire, type_notif, titre, message, 
                            urgence, entite_type, entite_id, client_id, actions=None):
        """Crée une notification en base de données"""
        try:
            notif = Notification(
                destinataire_id=destinataire.id,
                type_notification=type_notif,
                titre=titre,
                message=message,
                urgence=urgence,
                entite_type=entite_type,
                entite_id=entite_id,
                client_id=client_id,
                actions_possibles=actions or [],
                donnees_supplementaires={},
            )
            db.session.add(notif)
            print(f"📬 Notification créée pour {destinataire.username}")
        except Exception as e:
            print(f"⚠️ Erreur création notification : {e}")

    # Dans veille_notification_service.py

    @staticmethod
    def _envoyer_email(destinataire, sujet, corps):
        """Envoie un email (nécessite Flask-Mail configuré)"""
        try:
            from flask_mail import Message
            from app import mail
            
            msg = Message(
                subject=sujet,
                recipients=[destinataire.email],
                body=corps
            )
            mail.send(msg)
            print(f"📧 Email envoyé à {destinataire.email}")
        except Exception as e:
            print(f"⚠️ Erreur email : {e}")

    @staticmethod
    def notifier_aux_favoris(veille, type_notif, titre, message):
        """
        Notifie uniquement les utilisateurs ayant mis la veille en favori.
        
        Args:
            veille: Objet VeilleReglementaire
            type_notif: Type de notification (ex: 'veille_favori_en_vigueur')
            titre: Titre de la notification
            message: Message de la notification
        
        Returns:
            int: Nombre de notifications créées
        """
        try:
            from models import VeilleFavori
            
            # Récupérer les favoris de cette veille
            favoris = VeilleFavori.query.filter_by(veille_id=veille.id).all()
            
            if not favoris:
                print(f"ℹ️ Aucun favori pour la veille #{veille.id}")
                return 0
            
            nb_notifs = 0
            destinataires_vus = set()  # Éviter les doublons
            
            for favori in favoris:
                user = User.query.get(favori.utilisateur_id)
                
                # Vérifications
                if not user:
                    continue
                if not user.is_active:
                    continue
                if user.id in destinataires_vus:
                    continue
                if user.id == veille.created_by:
                    # Éviter de notifier 2 fois le créateur
                    # (il reçoit déjà une notif globale)
                    pass  # On peut quand même le notifier, à toi de choisir
                
                # Créer la notification
                try:
                    VeilleNotificationService._creer_notification(
                        destinataire=user,
                        type_notif=type_notif,
                        titre=f"⭐ {titre}",
                        message=message,
                        urgence='important',
                        entite_type='veille',
                        entite_id=veille.id,
                        client_id=veille.client_id,
                        actions=[
                            {'label': 'Voir la veille', 'url': f'/veille/{veille.id}'},
                        ]
                    )
                    destinataires_vus.add(user.id)
                    nb_notifs += 1
                except Exception as e:
                    print(f"⚠️ Erreur notification pour {user.username} : {e}")
            
            print(f"📬 {nb_notifs} notification(s) envoyée(s) aux favoris")
            return nb_notifs
            
        except ImportError:
            print("⚠️ Module VeilleFavori non disponible")
            return 0
        except Exception as e:
            print(f"⚠️ Erreur notifier_aux_favoris : {e}")
            return ArithmeticError
