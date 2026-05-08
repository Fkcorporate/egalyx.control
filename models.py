from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime, date, timezone
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


# -------------------- USER --------------------
class User(UserMixin, db.Model):
    __tablename__ = 'user'
    
    # ============================================
    # CHAMPS EXISTANTS (conservés)
    # ============================================
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    role = db.Column(db.String(20), default='utilisateur')
    department = db.Column(db.String(100))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)

    is_blocked = db.Column(db.Boolean, default=False)
    blocked_at = db.Column(db.DateTime, nullable=True)
    blocked_by = db.Column(db.Integer, nullable=True)
    blocked_reason = db.Column(db.String(255), nullable=True)
    deleted_at = db.Column(db.DateTime, nullable=True)
    deleted_by = db.Column(db.Integer, nullable=True)
    
    # Multi-tenant
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'))
    is_client_admin = db.Column(db.Boolean, default=False)
    can_manage_users = db.Column(db.Boolean, default=False)
    can_view_users_list = db.Column(db.Boolean, default=False)
    
    # Relation client
    client = db.relationship('Client', back_populates='utilisateurs')
    
    # ============================================
    # NOUVEAUX CHAMPS POUR LA SÉCURITÉ DES MOTS DE PASSE
    # ============================================
    
    # Historique des mots de passe (pour éviter la réutilisation)
    password_history = db.Column(db.JSON, default=[])
    
    # Date du dernier changement de mot de passe
    password_changed_at = db.Column(db.DateTime, nullable=True)
    
    # Tentatives de connexion échouées
    failed_login_attempts = db.Column(db.Integer, default=0)
    
    # Date du dernier échec de connexion
    last_failed_login = db.Column(db.DateTime, nullable=True)
    
    # Date d'expiration du mot de passe (90 jours par défaut)
    password_expires_at = db.Column(db.DateTime, nullable=True)
    
    # Token de réinitialisation de mot de passe
    reset_password_token = db.Column(db.String(100), nullable=True, unique=True)
    
    # Date d'expiration du token
    reset_password_expires = db.Column(db.DateTime, nullable=True)
    
    # Forcer le changement de mot de passe à la prochaine connexion
    force_password_change = db.Column(db.Boolean, default=False)
    
    # Verrouillage temporaire du compte
    locked_until = db.Column(db.DateTime, nullable=True)
    lock_reason = db.Column(db.String(255), nullable=True)
    
    # Token de session pour invalider toutes les sessions
    session_token = db.Column(db.String(100), nullable=True)
    
    # ============================================
    # PERMISSIONS (JSON)
    # ============================================
    permissions = db.Column(db.JSON, default={
        'can_view_dashboard': True,
        'can_manage_risks': False,
        'can_manage_kri': False,
        'can_manage_audit': False,
        'can_manage_regulatory': False,
        'can_manage_logigram': False,
        'can_manage_settings': False,
        'can_export_data': False,
        'can_view_reports': True,
        'can_delete_data': False,
        'can_access_all_departments': False,
        'can_archive_data': False,
        'can_validate_risks': False,
        'can_confirm_evaluations': False,
        'can_view_departments': False,
        'can_manage_departments': False,
        'can_view_users_list': False,
        'can_edit_users': False,
        'can_create_users': False,
        'can_deactivate_users': False,
        'can_delete_users': False,
        'can_block_users': False,
        'can_manage_permissions': False,
        # Modules
        'module_cartographie': True,
        'module_kri': True,
        'module_audit': True,
        'module_veille': True,
        'module_processus': True,
        'module_questionnaires': True,
        'module_plans_action': True,
        'module_analyse_ia': False,
        'can_manage_quality': False

    })
    
    # ============================================
    # PRÉFÉRENCES NOTIFICATIONS
    # ============================================
    preferences_notifications = db.Column(db.JSON, default={
        'web': {
            'nouvelle_constatation': True,
            'nouvelle_recommandation': True,
            'nouveau_plan': True,
            'echeance_7j': True,
            'echeance_3j': True,
            'echeance_1j': True,
            'retard': True,
            'validation_requise': True,
            'kri_alerte': True,
            'veille_nouvelle': True,
            'audit_demarre': True,
            'audit_termine': True
        },
        'email': {
            'nouvelle_constatation': False,
            'nouvelle_recommandation': False,
            'nouveau_plan': False,
            'echeance_7j': False,
            'echeance_3j': True,
            'echeance_1j': True,
            'retard': True,
            'validation_requise': True,
            'kri_alerte': True,
            'veille_nouvelle': False
        },
        'frequence_email': 'quotidien',
        'pause_until': None
    })
    
    # ============================================
    # RELATIONS
    # ============================================
    
    # Pôles
    poles_geres = db.relationship('Pole', 
                                  back_populates='responsable', 
                                  foreign_keys='Pole.responsable_id',
                                  lazy=True)
    
    # Directions
    directions_managees = db.relationship('Direction', 
                                         back_populates='responsable', 
                                         foreign_keys='Direction.responsable_id',
                                         lazy=True)
    
    directions_archivees = db.relationship('Direction', 
                                         back_populates='archived_by_user', 
                                         foreign_keys='Direction.archived_by',
                                         lazy=True)
    
    # Services
    services_managees = db.relationship('Service', 
                                       back_populates='responsable', 
                                       foreign_keys='Service.responsable_id',
                                       lazy=True)
    
    services_archivees = db.relationship('Service', 
                                       back_populates='archived_by_user', 
                                       foreign_keys='Service.archived_by',
                                       lazy=True)
    
    # Processus
    processus_geres = db.relationship('Processus', 
                                     back_populates='responsable', 
                                     foreign_keys='Processus.responsable_id',
                                     lazy=True)
    
    # Évaluations
    evaluations_faites = db.relationship('EvaluationRisque', 
                                        back_populates='evaluateur_final',
                                        foreign_keys='EvaluationRisque.evaluateur_final_id', 
                                        lazy=True)
    
    validations_faites = db.relationship('EvaluationRisque', 
                                        back_populates='validateur',
                                        foreign_keys='EvaluationRisque.validateur_id', 
                                        lazy=True)
    
    pre_evaluations_faites = db.relationship('EvaluationRisque', 
                                            back_populates='referent_pre_evaluation',
                                            foreign_keys='EvaluationRisque.referent_pre_evaluation_id', 
                                            lazy=True)
    
    # Cartographies
    cartographies_crees = db.relationship('Cartographie', 
                                         back_populates='createur',
                                         foreign_keys='Cartographie.created_by', 
                                         lazy=True)
    
    # Risques
    risques_crees = db.relationship('Risque', 
                                   back_populates='createur',
                                   foreign_keys='Risque.created_by', 
                                   lazy=True)
    
    risques_archives = db.relationship('Risque', 
                                      back_populates='archive_user',
                                      foreign_keys='Risque.archived_by', 
                                      lazy=True)
    
    # KRI
    kris_geres = db.relationship('KRI', 
                                back_populates='responsable_mesure', 
                                foreign_keys='KRI.responsable_mesure_id', 
                                lazy=True)
    
    kris_crees = db.relationship('KRI', 
                                back_populates='createur',
                                foreign_keys='KRI.created_by', 
                                lazy=True)
    
    kris_archives = db.relationship('KRI', 
                                   back_populates='archive_par',
                                   foreign_keys='KRI.archived_by', 
                                   lazy=True)
    
    # Audits
    audits_realises = db.relationship('Audit', 
                                     back_populates='responsable',
                                     foreign_keys='Audit.responsable_id', 
                                     lazy=True)
    
    audits_crees = db.relationship('Audit', 
                                  back_populates='createur',
                                  foreign_keys='Audit.created_by', 
                                  lazy=True)
    
    # Mesures KRI
    mesures_prises = db.relationship('MesureKRI', 
                                    back_populates='createur', 
                                    lazy=True)
    
    # Veille
    veilles_crees = db.relationship('VeilleReglementaire', 
                                   back_populates='createur', 
                                   lazy=True)
    
    actions_conformite = db.relationship('ActionConformite', 
                                        back_populates='responsable', 
                                        lazy=True)
    
    documents_veille = db.relationship('VeilleDocument', 
                                      back_populates='uploader', 
                                      foreign_keys='VeilleDocument.uploaded_by', 
                                      lazy=True)
    
    # Logigrammes
    logigrammes_crees = db.relationship('ProcessusActivite', 
                                       back_populates='createur',
                                       foreign_keys='ProcessusActivite.created_by', 
                                       lazy=True)
    
    # Journal d'activité
    activites = db.relationship('JournalActivite', 
                               back_populates='utilisateur',
                               foreign_keys='JournalActivite.utilisateur_id', 
                               lazy=True)
    
    # Plans d'action
    plans_action = db.relationship('PlanAction', 
                                  back_populates='responsable',
                                  foreign_keys='PlanAction.responsable_id', 
                                  lazy=True)
    
    # Notifications
    notifications_recues = db.relationship('Notification', 
                                          back_populates='destinataire',
                                          foreign_keys='Notification.destinataire_id',
                                          lazy=True,
                                          order_by='Notification.created_at.desc()')

    # ============================================
    # MÉTHODES DE GESTION DES MOTS DE PASSE
    # ============================================
    
    def set_password(self, password, check_history=True):
        """
        Définit le mot de passe avec validation de force et historique
        
        Args:
            password: Le nouveau mot de passe
            check_history: Vérifier l'historique (True pour changement)
        
        Raises:
            ValueError: Si le mot de passe ne respecte pas les critères
        """
        import re
        from datetime import datetime, timedelta
        from werkzeug.security import generate_password_hash
        
        # ============================================
        # 1. VALIDATION DE LA FORCE DU MOT DE PASSE
        # ============================================
        
        # Minimum 12 caractères (recommandation ANSSI)
        if len(password) < 12:
            raise ValueError("Le mot de passe doit contenir au moins 12 caractères")
        
        # Au moins une majuscule
        if not re.search(r"[A-Z]", password):
            raise ValueError("Le mot de passe doit contenir au moins une majuscule")
        
        # Au moins une minuscule
        if not re.search(r"[a-z]", password):
            raise ValueError("Le mot de passe doit contenir au moins une minuscule")
        
        # Au moins un chiffre
        if not re.search(r"[0-9]", password):
            raise ValueError("Le mot de passe doit contenir au moins un chiffre")
        
        # Au moins un caractère spécial
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
            raise ValueError("Le mot de passe doit contenir au moins un caractère spécial")
        
        # Pas d'espaces
        if " " in password:
            raise ValueError("Le mot de passe ne doit pas contenir d'espaces")
        
        # Pas de séquences évidentes
        common_patterns = [
            r"123456", r"password", r"motdepasse", r"azerty", r"qwerty",
            r"admin", r"root", r"test", r"123456789", r"0123456789"
        ]
        password_lower = password.lower()
        for pattern in common_patterns:
            if pattern in password_lower:
                raise ValueError(f"Le mot de passe contient une séquence trop simple: '{pattern}'")
        
        # Pas de répétitions (aaaa, 1111, etc.)
        if re.search(r"(.)\1{3,}", password):
            raise ValueError("Le mot de passe contient trop de caractères répétés")
        
        # ============================================
        # 2. VÉRIFICATION DE L'HISTORIQUE
        # ============================================
        
        if check_history and self.password_history:
            # Vérifier les 5 derniers mots de passe
            for old_hash in self.password_history[-5:]:
                if check_password_hash(old_hash, password):
                    raise ValueError("Vous ne pouvez pas réutiliser un des 5 derniers mots de passe")
        
        # ============================================
        # 3. SAUVEGARDE DE L'ANCIEN MOT DE PASSE
        # ============================================
        
        if self.password_hash and self.id:  # Si c'est une modification
            if not self.password_history:
                self.password_history = []
            
            # Ajouter l'ancien hash à l'historique
            self.password_history.append(self.password_hash)
            
            # Garder seulement les 10 derniers
            if len(self.password_history) > 10:
                self.password_history = self.password_history[-10:]
        
        # ============================================
        # 4. HASHAGE DU NOUVEAU MOT DE PASSE
        # ============================================
        
        self.password_hash = generate_password_hash(password)
        self.password_changed_at = datetime.utcnow()
        self.failed_login_attempts = 0  # Réinitialiser les tentatives
        self.force_password_change = False  # Désactiver le flag
        
        # Date d'expiration (90 jours)
        self.password_expires_at = datetime.utcnow() + timedelta(days=90)
        
        # Nouveau token de session (invalide les anciennes sessions)
        import secrets
        self.session_token = secrets.token_urlsafe(32)

    def check_password(self, password):
        """
        Vérifie le mot de passe avec gestion des tentatives échouées
        
        Returns:
            tuple: (success, message) - success est un booléen, message est un string
        """
        from datetime import datetime
        from werkzeug.security import check_password_hash
        
        # 1. VÉRIFIER SI LE COMPTE EST BLOQUÉ
        if self.is_blocked:
            if self.locked_until and self.locked_until > datetime.utcnow():
                return False, f"Compte temporairement bloqué jusqu'au {self.locked_until.strftime('%d/%m/%Y %H:%M')}"
            elif self.locked_until and self.locked_until <= datetime.utcnow():
                # Débloquer automatiquement
                self.is_blocked = False
                self.locked_until = None
                self.failed_login_attempts = 0
                self.lock_reason = None
            else:
                return False, "Ce compte est bloqué. Contactez l'administrateur."
        
        # 2. VÉRIFIER LE MOT DE PASSE
        is_valid = check_password_hash(self.password_hash, password)
        
        if is_valid:
            self.failed_login_attempts = 0
            self.last_failed_login = None
            return True, "Connexion réussie"
        
        # Échec : incrémenter le compteur
        self.failed_login_attempts += 1
        self.last_failed_login = datetime.utcnow()
        
        # 3. POLITIQUE DE BLOCAGE PROGRESSIVE
        if self.failed_login_attempts >= 10:
            self.is_blocked = True
            self.blocked_at = datetime.utcnow()
            self.blocked_reason = "Trop de tentatives de connexion échouées (10+)"
            return False, "Compte bloqué pour sécurité. Contactez l'administrateur."
        
        elif self.failed_login_attempts >= 5:
            self.locked_until = datetime.utcnow() + timedelta(minutes=30)
            self.lock_reason = f"Trop de tentatives échouées ({self.failed_login_attempts})"
            return False, f"Trop de tentatives. Compte bloqué 30 minutes."
        
        elif self.failed_login_attempts >= 3:
            return False, f"Mot de passe incorrect. Tentative {self.failed_login_attempts}/5"
        
        else:
            return False, "Nom d'utilisateur ou mot de passe incorrect"
    
    def is_password_expired(self):
        """Vérifie si le mot de passe a expiré"""
        from datetime import datetime
        if not self.password_expires_at:
            return False
        return datetime.utcnow() > self.password_expires_at
    
    def generate_reset_token(self, expires_in=3600):
        """
        Génère un token de réinitialisation de mot de passe
        
        Args:
            expires_in: Durée de validité en secondes (défaut: 1 heure)
        
        Returns:
            str: Le token de réinitialisation
        """
        import secrets
        from datetime import datetime, timedelta
        
        self.reset_password_token = secrets.token_urlsafe(32)
        self.reset_password_expires = datetime.utcnow() + timedelta(seconds=expires_in)
        db.session.commit()
        return self.reset_password_token
    
    def verify_reset_token(self, token):
        """
        Vérifie si un token de réinitialisation est valide
        
        Args:
            token: Le token à vérifier
        
        Returns:
            bool: True si le token est valide
        """
        from datetime import datetime
        
        if not self.reset_password_token or not self.reset_password_expires:
            return False
        
        if self.reset_password_token != token:
            return False
        
        if datetime.utcnow() > self.reset_password_expires:
            return False
        
        return True
    
    def invalidate_sessions(self):
        """Invalide toutes les sessions de l'utilisateur"""
        import secrets
        self.session_token = secrets.token_urlsafe(32)
        db.session.commit()

    # ============================================
    # MÉTHODES DE PERMISSIONS
    # ============================================
    
    def has_permission(self, permission):
        """Vérifie si l'utilisateur a une permission spécifique"""
        
        print(f"🔐 [DEBUG] Vérification permission '{permission}' pour {self.username} (rôle: {self.role})")
        
        # 1. SUPER ADMIN : TOUJOURS AUTORISÉ
        if self.role == 'super_admin':
            print(f"   ✅ Super admin - accès immédiat")
            return True
        
        # 2. ADMIN CLIENT
        is_admin_client = (self.role == 'admin') or (getattr(self, 'is_client_admin', False))
        
        if is_admin_client:
            print(f"   👑 Utilisateur est un ADMIN CLIENT")
            
            permissions_admin_obligatoires = {
                'can_view_dashboard': True,
                'can_view_reports': True,
                'can_view_departments': True,
                'can_view_notifications': True,
                'can_manage_risks': True,
                'can_validate_risks': True,
                'can_manage_kri': True,
                'can_manage_audit': True,
                'can_confirm_evaluations': True,
                'can_manage_action_plans': True,
                'can_view_action_plans': True,
                'can_view_users_list': True,
                'can_edit_users': True,
                'can_manage_users': True,
                'can_create_users': True,
                'can_deactivate_users': True,
                'can_delete_users': True,
                'can_manage_departments': True,
                'can_access_all_departments': True,
                'can_manage_settings': True,
                'can_archive_data': True,
                'can_export_data': True,
                'can_manage_regulatory': self.client and self.client.formule and 
                                          self.client.formule.modules.get('veille_reglementaire', False) if self.client else False,
                'can_manage_logigram': self.client and self.client.formule and 
                                        self.client.formule.modules.get('gestion_processus', False) if self.client else False,
                'can_manage_clients': False,
                'can_provision_servers': False,
                'can_manage_permissions': True,
            }
            
            if permission in permissions_admin_obligatoires:
                return permissions_admin_obligatoires[permission]
        
        # 3. GESTIONNAIRE (manager)
        if self.role == 'manager':
            print(f"   👤 Utilisateur est un GESTIONNAIRE")
            
            permissions_manager = {
                'can_view_dashboard': True,
                'can_view_reports': True,
                'can_view_departments': True,
                'can_view_notifications': True,
                'can_manage_risks': True,
                'can_validate_risks': True,
                'can_manage_kri': True,
                'can_manage_audit': True,
                'can_view_action_plans': True,
                'can_manage_action_plans': True,
                'can_access_all_departments': True,
                'can_export_data': True,
                'can_manage_users': True,
                'can_edit_users': True,
                'can_view_users_list': True,
                'can_create_users': True,
                'can_deactivate_users': True,
                'can_delete_users': True,
                'can_manage_permissions': True,
                'can_manage_settings': True,
                'can_manage_departments': True,
                'can_manage_clients': False,
                'can_provision_servers': False,
            }
            
            if permission in permissions_manager:
                return permissions_manager[permission]
        
        # 4. PERMISSIONS EXPLICITES DANS LA BASE
        if self.permissions and permission in self.permissions:
            return bool(self.permissions[permission])
        
        # 5. PERMISSIONS PAR DÉFAUT SELON LE RÔLE
        role_defaults = {
            'auditeur': {
                'can_view_dashboard': True,
                'can_view_reports': True,
                'can_view_departments': True,
                'can_view_notifications': True,
                'can_manage_audit': True,
                'can_view_action_plans': True,
            },
            'utilisateur': {
                'can_view_dashboard': True,
                'can_view_reports': True,
                'can_view_departments': True,
                'can_view_notifications': True,
                'can_view_action_plans': True,
            },
            'compliance': {
                'can_view_dashboard': True,
                'can_view_reports': True,
                'can_view_departments': True,
                'can_view_notifications': True,
                'can_manage_regulatory': True,
            },
            'consultant': {
                'can_view_dashboard': True,
                'can_view_reports': True,
                'can_view_departments': True,
            }
        }
        
        if self.role in role_defaults and permission in role_defaults[self.role]:
            return role_defaults[self.role][permission]
        
        print(f"   ❌ Permission '{permission}' REFUSÉE")
        return False
    
    # ============================================
    # MÉTHODES DE GESTION DES UTILISATEURS
    # ============================================
    
    def can_manage_user(self, target_user):
        """Vérifie si l'utilisateur peut gérer un autre utilisateur"""
        
        # On ne peut pas gérer soi-même
        if self.id == target_user.id:
            return False
        
        # Même client
        if self.client_id != target_user.client_id:
            return False
        
        # SUPER ADMIN
        if self.role == 'super_admin':
            return True
        
        # ADMIN CLIENT
        if self.is_client_admin:
            return not target_user.is_client_admin
        
        # GESTIONNAIRE
        if self.can_manage_users:
            return (not target_user.is_client_admin and 
                    not target_user.can_manage_users)
        
        return False
    
    def can_edit_plan(self, plan):
        """Vérifie si l'utilisateur peut modifier un plan d'action"""
        
        # SUPER ADMIN
        if self.role == 'super_admin':
            return True
        
        # Même client
        plan_client_id = getattr(plan, 'client_id', None)
        if plan_client_id and self.client_id != plan_client_id:
            return False
        
        # ADMIN CLIENT
        if self.is_client_admin:
            return True
        
        # Créateur du plan
        if hasattr(plan, 'created_by') and self.id == plan.created_by:
            return True
        
        # Responsable du plan
        if hasattr(plan, 'responsable_id') and self.id == plan.responsable_id:
            return True
        
        # Permission spécifique
        return self.has_permission('can_manage_action_plans')
    
    def can_archive_audit(self, audit):
        """Vérifie si l'utilisateur peut archiver un audit"""
        
        if self.role == 'super_admin':
            return True
        
        audit_client_id = getattr(audit, 'client_id', None)
        
        if audit_client_id is None:
            if hasattr(audit, 'created_by') and self.id == audit.created_by:
                return True
            if hasattr(audit, 'responsable_id') and self.id == audit.responsable_id:
                return True
            return False
        
        if audit_client_id != self.client_id:
            return False
        
        if self.is_client_admin:
            return True
        
        if self.id == getattr(audit, 'created_by', None) or \
           self.id == getattr(audit, 'responsable_id', None):
            return True
        
        return self.has_permission('can_manage_audit')
    
    # ============================================
    # MÉTHODES DE NOTIFICATIONS
    # ============================================
    
    def get_notification_preference(self, channel, event):
        """Obtenir la préférence de notification"""
        if not self.preferences_notifications:
            return True
        if channel not in self.preferences_notifications:
            return True
        return self.preferences_notifications[channel].get(event, True)
    
    def should_receive_notification(self, notification_type, channel='web'):
        """Vérifie si l'utilisateur devrait recevoir une notification"""
        
        # Vérifier pause
        if self.preferences_notifications and self.preferences_notifications.get('pause_until'):
            try:
                from datetime import datetime
                pause_date = self.preferences_notifications['pause_until']
                if isinstance(pause_date, str):
                    pause_date = datetime.strptime(pause_date, '%Y-%m-%d').date()
                elif isinstance(pause_date, datetime):
                    pause_date = pause_date.date()
                
                if pause_date and pause_date >= datetime.utcnow().date():
                    return False
            except Exception:
                pass
        
        return self.get_notification_preference(channel, notification_type)
    
    def get_notifications_non_lues_count(self):
        """Compter les notifications non lues"""
        from models import Notification
        return Notification.query.filter_by(
            destinataire_id=self.id,
            est_lue=False
        ).count()
    
    def get_notifications_recentes(self, limit=10):
        """Obtenir les notifications récentes"""
        from models import Notification
        return Notification.query.filter_by(
            destinataire_id=self.id
        ).order_by(
            Notification.created_at.desc()
        ).limit(limit).all()
    
    # ============================================
    # MÉTHODES UTILITAIRES
    # ============================================
    
    def get_role_display_name(self):
        """Retourne le nom d'affichage du rôle"""
        role_names = {
            'admin': 'Administrateur',
            'manager': 'Manager',
            'auditeur': 'Auditeur',
            'compliance': 'Responsable Conformité',
            'consultant': 'Consultant',
            'utilisateur': 'Utilisateur',
            'super_admin': 'Super Administrateur'
        }
        return role_names.get(self.role, self.role.title())
    
    def update_last_login(self):
        """Met à jour la date de dernière connexion"""
        from datetime import datetime
        self.last_login = datetime.utcnow()
        db.session.commit()
    
    def get_allowed_sections(self):
        """Retourne les sections accessibles"""
        sections = []
        if self.has_permission('can_view_dashboard'):
            sections.append('dashboard')
        if self.has_permission('can_manage_risks'):
            sections.extend(['cartographie', 'risques'])
        if self.has_permission('can_manage_kri'):
            sections.append('kri')
        if self.has_permission('can_manage_audit'):
            sections.extend(['audit', 'plans_action'])
        if self.has_permission('can_manage_regulatory'):
            sections.append('veille')
        if self.has_permission('can_manage_logigram'):
            sections.append('logigrammes')
        if self.has_permission('can_manage_users'):
            sections.append('administration')
        if self.has_permission('can_view_reports'):
            sections.append('rapports')
        return sections
    
    def __repr__(self):
        return f'<User {self.username} ({self.role})>'


# -------------------- DIRECTION --------------------
class Direction(db.Model):
    __tablename__ = 'direction'
    
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    
    # 🔴 NOUVEAU: Lien vers le pôle/filiale
    pole_id = db.Column(db.Integer, db.ForeignKey('poles.id'), nullable=True)
    
    # Responsable peut être soit un utilisateur (ID) soit un nom saisi manuellement
    responsable_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    responsable_nom_manuel = db.Column(db.String(200), nullable=True)
    responsable_type = db.Column(db.String(20), default='utilisateur')
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    is_archived = db.Column(db.Boolean, default=False)
    archived_at = db.Column(db.DateTime)
    archived_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)

    # Relations
    pole = db.relationship('Pole', back_populates='directions')
    
    responsable = db.relationship('User', 
                                 back_populates='directions_managees', 
                                 foreign_keys=[responsable_id])
    
    archived_by_user = db.relationship('User', 
                                      back_populates='directions_archivees', 
                                      foreign_keys=[archived_by])
    
    services = db.relationship('Service', back_populates='direction', lazy=True)
    cartographies = db.relationship('Cartographie', back_populates='direction', lazy=True)
    processus = db.relationship('Processus', back_populates='direction', lazy=True)
    
    @property
    def responsable_nom(self):
        if self.responsable_id and self.responsable:
            return self.responsable.username
        elif self.responsable_nom_manuel:
            return self.responsable_nom_manuel
        else:
            return "Non assigné"
    
    @property
    def a_responsable(self):
        return bool(self.responsable_id or self.responsable_nom_manuel)

# -------------------- SERVICE --------------------
class Service(db.Model):
    __tablename__ = 'service'
    
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    direction_id = db.Column(db.Integer, db.ForeignKey('direction.id'))
    
    # 🔴 NOUVEAU: Responsable peut être soit un utilisateur (ID) soit un nom saisi manuellement
    responsable_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    responsable_nom_manuel = db.Column(db.String(200), nullable=True)  # Nom saisi manuellement
    responsable_type = db.Column(db.String(20), default='utilisateur')  # 'utilisateur' ou 'manuel'
    
    # 🔴 NOUVEAU: Membres de l'équipe (stockés en JSON)
    equipe_membres = db.Column(db.JSON, default=[])  # Liste des noms des membres
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    is_archived = db.Column(db.Boolean, default=False)
    archived_at = db.Column(db.DateTime)
    archived_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)

    # Relations
    direction = db.relationship('Direction', back_populates='services')
    
    responsable = db.relationship('User', 
                                 back_populates='services_managees', 
                                 foreign_keys=[responsable_id])
    
    archived_by_user = db.relationship('User', 
                                      back_populates='services_archivees', 
                                      foreign_keys=[archived_by])
    
    processus = db.relationship('Processus', back_populates='service', lazy=True)
    cartographies = db.relationship('Cartographie', back_populates='service', lazy=True)
    
    # Propriété pour obtenir le nom du responsable (quel que soit le mode)
    @property
    def responsable_nom(self):
        if self.responsable_id and self.responsable:
            return self.responsable.username
        elif self.responsable_nom_manuel:
            return self.responsable_nom_manuel
        else:
            return "Non assigné"
    
    # Propriété pour savoir si le responsable est assigné
    @property
    def a_responsable(self):
        return bool(self.responsable_id or self.responsable_nom_manuel)
    
    # Méthode pour ajouter un membre à l'équipe
    def ajouter_membre_equipe(self, nom_membre):
        if not self.equipe_membres:
            self.equipe_membres = []
        if nom_membre not in self.equipe_membres:
            self.equipe_membres.append(nom_membre)
    
    # Méthode pour retirer un membre de l'équipe
    def retirer_membre_equipe(self, nom_membre):
        if self.equipe_membres and nom_membre in self.equipe_membres:
            self.equipe_membres.remove(nom_membre)
    
    # Propriété pour obtenir le nombre de membres
    @property
    def nb_membres_equipe(self):
        return len(self.equipe_membres) if self.equipe_membres else 0


class Pole(db.Model):
    """Pôle ou Filiale - niveau hiérarchique au-dessus des directions"""
    __tablename__ = 'poles'
    
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    
    # Responsable du pôle (optionnel)
    responsable_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    responsable_nom_manuel = db.Column(db.String(200), nullable=True)
    responsable_type = db.Column(db.String(20), default='utilisateur')
    
    # Couleur personnalisée pour ce pôle (optionnel)
    couleur = db.Column(db.String(20), default='#3b82f6')
    
    # Multi-tenant
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)
    
    # Métadonnées
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Archivage
    is_archived = db.Column(db.Boolean, default=False)
    archived_at = db.Column(db.DateTime)
    archived_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    ordre = db.Column(db.Integer, default=0)  # Pour ordonner l'affichage
    
    # Relations
    responsable = db.relationship('User', foreign_keys=[responsable_id],
                                  back_populates='poles_geres')
    directions = db.relationship('Direction', back_populates='pole', lazy=True)
    createur = db.relationship('User', foreign_keys=[created_by])
    archive_user = db.relationship('User', foreign_keys=[archived_by])
    
    @property
    def responsable_nom(self):
        if self.responsable_id and self.responsable:
            return self.responsable.username
        elif self.responsable_nom_manuel:
            return self.responsable_nom_manuel
        return "Non assigné"
    
    @property
    def a_responsable(self):
        return bool(self.responsable_id or self.responsable_nom_manuel)
    
    @property
    def nb_directions(self):
        return len([d for d in self.directions if not d.is_archived and d.is_active])
    
    @property
    def nb_services(self):
        total = 0
        for direction in self.directions:
            if not direction.is_archived and direction.is_active:
                total += len([s for s in direction.services 
                             if not s.is_archived and s.is_active])
        return total


# -------------------- CONFIGURATION ORGANIGRAMME --------------------
class ConfigurationOrganigramme(db.Model):
    """Configuration de l'organigramme pour chaque client"""
    __tablename__ = 'configuration_organigramme'
    
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), unique=True)
    nom_entreprise = db.Column(db.String(200), default="Nom de l'entreprise")
    logo_entreprise = db.Column(db.String(500), nullable=True)  # Chemin du logo
    logo_nom = db.Column(db.String(255), nullable=True)  # Nom original du fichier
    couleur_primaire = db.Column(db.String(20), default="#2563eb")
    couleur_secondaire = db.Column(db.String(20), default="#10b981")
    pied_de_page = db.Column(db.String(500), default="Document confidentiel")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    
    client = db.relationship('Client', backref='config_organigramme')
    

class Cartographie(db.Model):
    __tablename__ = 'cartographie'
    
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    
    # 🔴 AJOUTER CETTE LIGNE
    pole_id = db.Column(db.Integer, db.ForeignKey('poles.id'), nullable=True)
    
    direction_id = db.Column(db.Integer, db.ForeignKey('direction.id'))
    service_id = db.Column(db.Integer, db.ForeignKey('service.id'))
    type_cartographie = db.Column(db.String(50), default='direction')
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    processus_id = db.Column(db.Integer, db.ForeignKey('processus.id')) 
    
    is_archived = db.Column(db.Boolean, default=False)
    archived_at = db.Column(db.DateTime)
    archived_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    archive_reason = db.Column(db.Text)
    
    # Relations
    # 🔴 AJOUTER CETTE RELATION
    pole = db.relationship('Pole', backref='cartographies')
    
    direction = db.relationship('Direction', back_populates='cartographies')
    service = db.relationship('Service', back_populates='cartographies')
    createur = db.relationship('User', foreign_keys=[created_by])
    archive_user = db.relationship('User', foreign_keys=[archived_by])
    risques = db.relationship('Risque', back_populates='cartographie')
    campagnes = db.relationship('CampagneEvaluation', back_populates='cartographie', cascade='all, delete-orphan')
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)
    processus = db.relationship('Processus', backref='cartographies')
    
    @property
    def nom_complet(self):
        if self.pole:
            return f"{self.pole.nom} > {self.nom}"
        return self.nom
    
    @property
    def hierarchie_complete(self):
        parts = []
        if self.pole:
            parts.append(self.pole.nom)
        if self.direction:
            parts.append(self.direction.nom)
        if self.service:
            parts.append(self.service.nom)
        return " > ".join(parts)
    
# -------------------- RISQUE --------------------
class Risque(db.Model):
    __tablename__ = 'risques'
    
    id = db.Column(db.Integer, primary_key=True)
    reference = db.Column(db.String(50), nullable=False)  # ← unique=True ENLEVÉ
    intitule = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text)
    cartographie_id = db.Column(db.Integer, db.ForeignKey('cartographie.id'))
    processus_concerne = db.Column(db.String(200))
    categorie = db.Column(db.String(100))
    type_risque = db.Column(db.String(100))
    cause_racine = db.Column(db.Text)
    consequences = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_archived = db.Column(db.Boolean, default=False)
    archived_at = db.Column(db.DateTime)
    archived_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    archive_reason = db.Column(db.Text)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)

    # Relations
    cartographie = db.relationship('Cartographie', back_populates='risques')
    createur = db.relationship('User', foreign_keys=[created_by], back_populates='risques_crees')
    archive_user = db.relationship('User', foreign_keys=[archived_by], back_populates='risques_archives')
    evaluations = db.relationship('EvaluationRisque', back_populates='risque', lazy=True)
    kri = db.relationship('KRI', back_populates='risque', uselist=False, lazy=True,
                         primaryjoin='Risque.id == KRI.risque_id')
    dispositifs_maitrise = db.relationship('DispositifMaitrise', 
                                          back_populates='risque',
                                          cascade='all, delete-orphan',
                                          lazy=True)
    
    # ⭐ CONTRAINTE UNIQUE COMPOSITE
    __table_args__ = (
        db.UniqueConstraint('reference', 'client_id', name='uix_risque_reference_client'),
    )
    
    # ⭐ MÉTHODE DE GÉNÉRATION
    @staticmethod
    def generer_reference(client_id):
        from datetime import datetime
        annee = datetime.now().year
        prefixe = f"RISQ-{annee}-"
        
        count = Risque.query.filter(
            Risque.reference.like(f'{prefixe}%'),
            Risque.client_id == client_id
        ).count()
        
        return f"{prefixe}{(count + 1):04d}"
    
    # ⭐ MÉTHODE UTILITAIRE (optionnelle)
    def get_derniere_evaluation_niveau(self):
        if self.evaluations:
            derniere = sorted(self.evaluations, key=lambda x: x.created_at)[-1]
            return derniere.niveau_risque
        return None
    
    def __repr__(self):
        return f'<Risque {self.reference}: {self.intitule[:50]}>'

# -------------------- EVALUATION RISQUE (CORRIGÉ) --------------------
class EvaluationRisque(db.Model):
    __tablename__ = 'evaluations_risque'
    
    id = db.Column(db.Integer, primary_key=True)
    risque_id = db.Column(db.Integer, db.ForeignKey('risques.id'), nullable=False)
    campagne_id = db.Column(db.Integer, db.ForeignKey('campagnes_evaluation.id'), nullable=True)

    # Phase 1 - Pré-évaluation
    referent_pre_evaluation_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    date_pre_evaluation = db.Column(db.DateTime)
    impact_pre = db.Column(db.Integer)
    probabilite_pre = db.Column(db.Integer)
    niveau_maitrise_pre = db.Column(db.Integer)
    commentaire_pre_evaluation = db.Column(db.Text)
    
    # Phase 2 - Validation  
    validateur_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    date_validation = db.Column(db.DateTime)
    statut_validation = db.Column(db.String(20), default='en_attente')
    impact_val = db.Column(db.Integer)
    probabilite_val = db.Column(db.Integer)
    niveau_maitrise_val = db.Column(db.Integer)
    commentaire_validation = db.Column(db.Text)
    
    # Phase 3 - Confirmation
    evaluateur_final_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    date_confirmation = db.Column(db.DateTime)
    impact_conf = db.Column(db.Integer)
    probabilite_conf = db.Column(db.Integer)
    niveau_maitrise_conf = db.Column(db.Integer)
    commentaire_confirmation = db.Column(db.Text)
    
    # Informations de campagne (pour compatibilité ascendante)
    campagne_nom = db.Column(db.String(200))
    campagne_date_debut = db.Column(db.Date)
    campagne_date_fin = db.Column(db.Date)
    campagne_objectif = db.Column(db.Text)
    
    # Résultats finaux
    score_risque = db.Column(db.Integer)
    niveau_risque = db.Column(db.String(20))
    type_evaluation = db.Column(db.String(50), default='pre_evaluation')
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)
    
    # Audit
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relations
    risque = db.relationship('Risque', back_populates='evaluations')
    campagne = db.relationship('CampagneEvaluation', back_populates='evaluations')
    referent_pre_evaluation = db.relationship('User', foreign_keys=[referent_pre_evaluation_id])
    validateur = db.relationship('User', foreign_keys=[validateur_id])
    evaluateur_final = db.relationship('User', foreign_keys=[evaluateur_final_id])
    createur = db.relationship('User', foreign_keys=[created_by])

    def get_valeurs_finales(self):
        """Retourne les valeurs finales selon la hiérarchie triphasée"""
        return {
            'impact': self.impact_conf or self.impact_val or self.impact_pre,
            'probabilite': self.probabilite_conf or self.probabilite_val or self.probabilite_pre,
            'niveau_maitrise': self.niveau_maitrise_conf or self.niveau_maitrise_val or self.niveau_maitrise_pre,
            'score': self.score_risque,
            'niveau_risque': self.niveau_risque,
            'phase': 'confirmee' if self.date_confirmation else 
                    'validee' if self.date_validation else 
                    'pre_evaluation'
        }
    
    def est_complete(self):
        """Vérifie si l'évaluation est complète (toutes les phases)"""
        return bool(self.date_confirmation)

    def __repr__(self):
        return f'<EvaluationRisque {self.id} pour risque {self.risque_id}>'

class CampagneEvaluation(db.Model):
    __tablename__ = 'campagnes_evaluation'
    
    id = db.Column(db.Integer, primary_key=True)
    cartographie_id = db.Column(db.Integer, db.ForeignKey('cartographie.id'), nullable=False)
    nom = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    date_debut = db.Column(db.Date)
    date_fin = db.Column(db.Date)
    statut = db.Column(db.String(20), default='en_cours')  # en_cours, terminee, archivee
    
    # AJOUTEZ CES CHAMPS POUR L'ARCHIVAGE
    is_archived = db.Column(db.Boolean, default=False)
    archived_at = db.Column(db.DateTime)
    archived_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    archive_reason = db.Column(db.Text)
    
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relations
    cartographie = db.relationship('Cartographie', back_populates='campagnes')
    createur = db.relationship('User', foreign_keys=[created_by])
    evaluations = db.relationship('EvaluationRisque', back_populates='campagne', cascade='all, delete-orphan')
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)
    
    # AJOUTEZ CETTE RELATION
    archive_user = db.relationship('User', foreign_keys=[archived_by])
    
    def __repr__(self):
        return f'<CampagneEvaluation {self.id}: {self.nom}>'

# -------------------- KRI (CORRIGÉ) --------------------
class KRI(db.Model):
    __tablename__ = 'kri'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # TYPE D'INDICATEUR : 'kri' ou 'kpi'
    type_indicateur = db.Column(db.String(50), nullable=True)  # Ajoutez cette ligne si manquante
    
    # RISQUE ASSOCIÉ (optionnel, surtout pour les KPI)
    risque_id = db.Column(db.Integer, db.ForeignKey('risques.id'), nullable=True)
    
    # INFORMATIONS DE BASE
    nom = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    formule_calcul = db.Column(db.String(300))
    unite_mesure = db.Column(db.String(50))
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)
    
    # SEUILS D'ALERTE
    seuil_alerte = db.Column(db.Float)
    seuil_critique = db.Column(db.Float)
    seuil_cible = db.Column(db.Float, nullable=True) 
    
    # SENS D'ÉVALUATION DES SEUILS
    sens_evaluation_seuil = db.Column(db.String(20), default='superieur')
    # 'superieur' : Risque si valeur actuelle > seuil (défaut)
    # 'inferieur' : Risque si valeur actuelle < seuil
    
    
    # FRÉQUENCE ET RESPONSABLE
    frequence_mesure = db.Column(db.String(50))
    responsable_mesure_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    # MÉTADONNÉES SUPPLÉMENTAIRES
    categorie = db.Column(db.String(50))
    source_donnees = db.Column(db.String(100))
    notes_internes = db.Column(db.Text)
    
    # TIMESTAMPS ET ÉTAT
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    est_actif = db.Column(db.Boolean, default=True)
    archived_at = db.Column(db.DateTime)
    archived_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))

    # RELATIONS
    risque = db.relationship('Risque', back_populates='kri')
    responsable_mesure = db.relationship('User', foreign_keys=[responsable_mesure_id], back_populates='kris_geres')
    createur = db.relationship('User', foreign_keys=[created_by], back_populates='kris_crees')
    archive_par = db.relationship('User', foreign_keys=[archived_by])
    mesures = db.relationship('MesureKRI', back_populates='kri', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<{self.get_type_display()} {self.nom}>'

    def to_dict(self):
        return {
            'id': self.id,
            'type_indicateur': self.type_indicateur,
            'risque_id': self.risque_id,
            'nom': self.nom,
            'description': self.description,
            'formule_calcul': self.formule_calcul,
            'unite_mesure': self.unite_mesure,
            'seuil_alerte': self.seuil_alerte,
            'seuil_critique': self.seuil_critique,
            'sens_evaluation_seuil': self.sens_evaluation_seuil,
            'frequence_mesure': self.frequence_mesure,
            'responsable_mesure_id': self.responsable_mesure_id,
            'categorie': self.categorie,
            'source_donnees': self.source_donnees,
            'notes_internes': self.notes_internes,
            'est_actif': self.est_actif,
            'archived_at': self.archived_at.isoformat() if self.archived_at else None,
            'archived_by': self.archived_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'created_by': self.created_by
        }

    def archiver(self, user_id):
        """Archiver l'indicateur"""
        self.est_actif = False
        self.archived_at = datetime.utcnow()
        self.archived_by = user_id
        self.updated_at = datetime.utcnow()

    def restaurer(self):
        """Restaurer l'indicateur"""
        self.est_actif = True
        self.archived_at = None
        self.archived_by = None
        self.updated_at = datetime.utcnow()

    def get_derniere_mesure(self):
        """Obtenir la dernière mesure"""
        if self.mesures:
            return max(self.mesures, key=lambda x: x.date_mesure)
        return None

    def get_statistiques(self):
        """Obtenir les statistiques de l'indicateur"""
        if not self.mesures:
            return None
            
        valeurs = [m.valeur for m in self.mesures]
        return {
            'moyenne': sum(valeurs) / len(valeurs) if valeurs else 0,
            'min': min(valeurs) if valeurs else 0,
            'max': max(valeurs) if valeurs else 0,
            'nb_mesures': len(valeurs),
            'derniere_valeur': valeurs[-1] if valeurs else None
        }

    def get_etat_alerte(self, valeur):
        """Retourne l'état d'alerte basé sur le sens d'évaluation"""
        if valeur is None:
            return 'inconnu'
        
        # Pour les KPI, on utilise aussi la logique des seuils mais avec des libellés différents
        if self.sens_evaluation_seuil == 'inferieur':
            # Risque/alerte si valeur < seuil
            if self.seuil_critique is not None and valeur <= self.seuil_critique:
                return 'critique' if self.type_indicateur == 'kri' else 'hors_cible'
            elif self.seuil_alerte is not None and valeur <= self.seuil_alerte:
                return 'alerte' if self.type_indicateur == 'kri' else 'sous_performance'
            else:
                return 'normal' if self.type_indicateur == 'kri' else 'dans_cible'
        else:
            # Risque/alerte si valeur > seuil (par défaut)
            if self.seuil_critique is not None and valeur >= self.seuil_critique:
                return 'critique' if self.type_indicateur == 'kri' else 'hors_cible'
            elif self.seuil_alerte is not None and valeur >= self.seuil_alerte:
                return 'alerte' if self.type_indicateur == 'kri' else 'sous_performance'
            else:
                return 'normal' if self.type_indicateur == 'kri' else 'dans_cible'
    
    def get_couleur_etat(self, valeur):
        """Retourne la couleur Bootstrap correspondant à l'état"""
        etat = self.get_etat_alerte(valeur)
        
        if self.type_indicateur == 'kri':
            couleurs = {
                'critique': 'danger',
                'alerte': 'warning',
                'normal': 'success',
                'inconnu': 'secondary'
            }
        else:  # KPI
            couleurs = {
                'hors_cible': 'danger',
                'sous_performance': 'warning',
                'dans_cible': 'success',
                'inconnu': 'secondary'
            }
        
        return couleurs.get(etat, 'secondary')
    
    def get_libelle_etat(self, valeur):
        """Retourne le libellé de l'état selon le type d'indicateur"""
        etat = self.get_etat_alerte(valeur)
        
        if self.type_indicateur == 'kri':
            libelles = {
                'critique': 'CRITIQUE',
                'alerte': 'ALERTE',
                'normal': 'NORMAL',
                'inconnu': 'N/A'
            }
        else:  # KPI
            libelles = {
                'hors_cible': 'HORS CIBLE',
                'sous_performance': 'SOUS-PERFORMANCE',
                'dans_cible': 'DANS CIBLE',
                'inconnu': 'N/A'
            }
        
        return libelles.get(etat, 'INCONNU')
    
    def get_description_sens_evaluation(self):
        """Retourne une description lisible du sens d'évaluation"""
        if self.type_indicateur == 'kri':
            descriptions = {
                'superieur': 'Risque si valeur > seuil',
                'inferieur': 'Risque si valeur < seuil'
            }
        else:  # KPI
            descriptions = {
                'superieur': 'Sous-performance si valeur > seuil',
                'inferieur': 'Sous-performance si valeur < seuil'
            }
        
        return descriptions.get(self.sens_evaluation_seuil, 'Sens non défini')
    
    def get_type_display(self):
        """Retourne l'affichage du type d'indicateur"""
        types = {
            'kri': 'KRI',
            'kpi': 'KPI'
        }
        return types.get(self.type_indicateur, 'Indicateur')
    
    def get_couleur_type(self):
        """Retourne la couleur Bootstrap selon le type"""
        return 'danger' if self.type_indicateur == 'kri' else 'success'
    
    def get_icon_type(self):
        """Retourne l'icône FontAwesome selon le type"""
        return 'exclamation-triangle' if self.type_indicateur == 'kri' else 'chart-line'
    
    def est_associe_risque(self):
        """Vérifie si l'indicateur est associé à un risque"""
        return self.risque_id is not None
    
    def get_risque_associe_info(self):
        """Retourne les informations du risque associé si disponible"""
        if self.risque:
            return {
                'reference': self.risque.reference,
                'intitule': self.risque.intitule,
                'niveau': self.risque.get_derniere_evaluation_niveau() if self.risque.evaluations else 'N/A'
            }
        return None
    
    def peut_etre_supprime(self):
        """Vérifie si l'indicateur peut être supprimé"""
        # Un indicateur sans mesure peut être supprimé
        return len(self.mesures) == 0
    
    def clone(self, nouveau_nom=None, nouveau_createur_id=None):
        """Clone l'indicateur avec un nouveau nom"""
        clone = KRI(
            type_indicateur=self.type_indicateur,
            risque_id=self.risque_id,
            nom=nouveau_nom or f"{self.nom} (Copie)",
            description=self.description,
            formule_calcul=self.formule_calcul,
            unite_mesure=self.unite_mesure,
            seuil_alerte=self.seuil_alerte,
            seuil_critique=self.seuil_critique,
            sens_evaluation_seuil=self.sens_evaluation_seuil,
            frequence_mesure=self.frequence_mesure,
            responsable_mesure_id=self.responsable_mesure_id,
            categorie=self.categorie,
            source_donnees=self.source_donnees,
            notes_internes=self.notes_internes,
            created_by=nouveau_createur_id or self.created_by
        )
        return clone

    @classmethod
    def get_actifs(cls):
        """Obtenir tous les indicateurs actifs"""
        return cls.query.filter_by(est_actif=True).order_by(cls.type_indicateur, cls.nom).all()
    
    @classmethod
    def get_actifs_par_type(cls, type_indicateur):
        """Obtenir tous les indicateurs actifs d'un type spécifique"""
        return cls.query.filter_by(est_actif=True, type_indicateur=type_indicateur).order_by(cls.nom).all()
    
    @classmethod
    def get_kris_actifs(cls):
        """Obtenir tous les KRI actifs"""
        return cls.get_actifs_par_type('kri')
    
    @classmethod
    def get_kpis_actifs(cls):
        """Obtenir tous les KPI actifs"""
        return cls.get_actifs_par_type('kpi')

    @classmethod
    def get_archives(cls):
        """Obtenir tous les indicateurs archivés"""
        return cls.query.filter_by(est_actif=False).order_by(cls.archived_at.desc()).all()

    @classmethod
    def get_par_risque(cls, risque_id):
        """Obtenir les indicateurs d'un risque spécifique"""
        return cls.query.filter_by(risque_id=risque_id, est_actif=True).all()
    
    @classmethod
    def get_sans_risque(cls):
        """Obtenir les indicateurs non associés à un risque"""
        return cls.query.filter(cls.risque_id.is_(None), cls.est_actif==True).all()

    
    def get_difference_cible(self, valeur):
        """
        Calcule la différence entre une valeur et la cible
        Retourne None si pas de cible définie
        """
        if self.type_indicateur != 'kpi' or self.seuil_cible is None:
            return None
        
        try:
            return valeur - self.seuil_cible
        except (TypeError, ValueError):
            return None
    
    def get_interpretation_difference(self, valeur):
        """
        Interprète l'écart par rapport à la cible
        Retourne un dict avec couleur, message et explication
        """
        diff = self.get_difference_cible(valeur)
        if diff is None:
            return None
        
        # Calcul du pourcentage d'écart
        if self.seuil_cible != 0:
            pourcentage = (diff / self.seuil_cible) * 100
        else:
            pourcentage = float('inf') if diff > 0 else float('-inf')
        
        # Interprétation selon le sens d'évaluation
        if self.sens_evaluation_seuil == 'inferieur':
            # Pour un KPI, on veut généralement une valeur ÉLEVÉE (donc diff positive = bonne)
            if diff >= 0:
                if pourcentage > 10:
                    return {
                        'couleur': 'success',
                        'message': 'Excellent',
                        'explication': f'Dépasse la cible de {pourcentage:.1f}%'
                    }
                else:
                    return {
                        'couleur': 'info',
                        'message': 'Atteint',
                        'explication': f'Dans la cible (écart de {pourcentage:.1f}%)'
                    }
            else:
                if pourcentage < -10:
                    return {
                        'couleur': 'danger',
                        'message': 'Critique',
                        'explication': f'Sous la cible de {abs(pourcentage):.1f}%'
                    }
                else:
                    return {
                        'couleur': 'warning',
                        'message': 'Attention',
                        'explication': f'Légèrement sous la cible ({abs(pourcentage):.1f}%)'
                    }
        else:  # sens_evaluation_seuil == 'superieur'
            # Pour certains KPI, on veut une valeur BASSE (ex: taux de défaut)
            if diff <= 0:
                if pourcentage < -10:
                    return {
                        'couleur': 'success',
                        'message': 'Excellent',
                        'explication': f'En dessous de la cible de {abs(pourcentage):.1f}%'
                    }
                else:
                    return {
                        'couleur': 'info',
                        'message': 'Atteint',
                        'explication': f'Dans la cible (écart de {abs(pourcentage):.1f}%)'
                    }
            else:
                if pourcentage > 10:
                    return {
                        'couleur': 'danger',
                        'message': 'Critique',
                        'explication': f'Au-dessus de la cible de {pourcentage:.1f}%'
                    }
                else:
                    return {
                        'couleur': 'warning',
                        'message': 'Attention',
                        'explication': f'Légèrement au-dessus de la cible ({pourcentage:.1f}%)'
                    }
    
    # Optionnel : Ajouter une méthode pour formater la différence
    def format_difference_cible(self, valeur):
        """Formate la différence par rapport à la cible"""
        diff = self.get_difference_cible(valeur)
        if diff is None:
            return "N/A"
        
        signe = "+" if diff > 0 else ""
        return f"{signe}{diff:.2f} {self.unite_mesure or ''}"
    
    @classmethod
    def get_statistiques_globales(cls):
        """Obtenir les statistiques globales des indicateurs"""
        total = cls.query.filter_by(est_actif=True).count()
        kris = cls.query.filter_by(est_actif=True, type_indicateur='kri').count()
        kpis = cls.query.filter_by(est_actif=True, type_indicateur='kpi').count()
        avec_risque = cls.query.filter(cls.risque_id.isnot(None), cls.est_actif==True).count()
        sans_risque = total - avec_risque
        
        return {
            'total': total,
            'kris': kris,
            'kpis': kpis,
            'avec_risque': avec_risque,
            'sans_risque': sans_risque,
            'pourcentage_kris': (kris / total * 100) if total > 0 else 0,
            'pourcentage_kpis': (kpis / total * 100) if total > 0 else 0
        }

# -------------------- MESURE KRI --------------------
class MesureKRI(db.Model):
    __tablename__ = 'mesure_kri'
    
    id = db.Column(db.Integer, primary_key=True)
    kri_id = db.Column(db.Integer, db.ForeignKey('kri.id'))
    valeur = db.Column(db.Float, nullable=False)
    date_mesure = db.Column(db.DateTime, nullable=False)
    commentaire = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    kri = db.relationship('KRI', back_populates='mesures')
    createur = db.relationship('User', back_populates='mesures_prises', foreign_keys=[created_by])
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)

# -------------------- SOUS-ETAPE PROCESSUS --------------------
class SousEtapeProcessus(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    etape_id = db.Column(db.Integer, db.ForeignKey('etape_processus.id'))
    ordre = db.Column(db.Integer, nullable=False)
    nom = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    responsable_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    duree_estimee = db.Column(db.String(50))
    inputs = db.Column(db.Text)
    outputs = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    etape = db.relationship('EtapeProcessus', back_populates='sous_etapes')
    responsable = db.relationship('User', backref='sous_etapes_gerees')
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)

# -------------------- LIEN PROCESSUS --------------------
class LienProcessus(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    processus_id = db.Column(db.Integer, db.ForeignKey('processus.id'))
    etape_source_id = db.Column(db.Integer, db.ForeignKey('etape_processus.id'))
    etape_cible_id = db.Column(db.Integer, db.ForeignKey('etape_processus.id'))
    type_lien = db.Column(db.String(50), default='sequence')
    label = db.Column(db.String(100))
    position_x = db.Column(db.Float)
    position_y = db.Column(db.Float)
    direction = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)

    processus = db.relationship('Processus', back_populates='liens')
    etape_source = db.relationship('EtapeProcessus', foreign_keys=[etape_source_id], backref='liens_sortants')
    etape_cible = db.relationship('EtapeProcessus', foreign_keys=[etape_cible_id], backref='liens_entrants')

# -------------------- ZONE RISQUE PROCESSUS --------------------
class ZoneRisqueProcessus(db.Model):
    __tablename__ = 'zone_risque_processus'
    
    id = db.Column(db.Integer, primary_key=True)
    processus_id = db.Column(db.Integer, db.ForeignKey('processus.id'))
    etape_source_id = db.Column(db.Integer, db.ForeignKey('etape_processus.id'))
    etape_cible_id = db.Column(db.Integer, db.ForeignKey('etape_processus.id'))
    nom = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    type_risque = db.Column(db.String(100))
    niveau_risque = db.Column(db.String(20))
    impact = db.Column(db.Text)
    mesures_controle = db.Column(db.Text)
    responsable_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)  # <-- IMPORTANT
    
    # Relations
    processus = db.relationship('Processus', back_populates='zones_risque')
    etape_source = db.relationship('EtapeProcessus', foreign_keys=[etape_source_id], backref='zones_risque_source')
    etape_cible = db.relationship('EtapeProcessus', foreign_keys=[etape_cible_id], backref='zones_risque_cible')
    responsable = db.relationship('User', backref='zones_risque_geres')

# -------------------- CONTROLE PROCESSUS --------------------
class ControleProcessus(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    processus_id = db.Column(db.Integer, db.ForeignKey('processus.id'))
    etape_id = db.Column(db.Integer, db.ForeignKey('etape_processus.id'))
    nom = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    type_controle = db.Column(db.String(100))
    frequence = db.Column(db.String(50))
    responsable_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    statut = db.Column(db.String(20), default='actif')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    processus = db.relationship('Processus', back_populates='controles')
    etape = db.relationship('EtapeProcessus', back_populates='controles')
    responsable = db.relationship('User', backref='controles_geres')

# -------------------- ETAPE PROCESSUS --------------------
class EtapeProcessus(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    processus_id = db.Column(db.Integer, db.ForeignKey('processus.id'))
    ordre = db.Column(db.Integer, nullable=False)
    nom = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    responsable_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    duree_estimee = db.Column(db.String(50))
    inputs = db.Column(db.Text)
    outputs = db.Column(db.Text)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)
    
    # CHAMPS POUR L'ORGANIGRAMME FLUIDE
    type_etape = db.Column(db.String(20), default='action')
    position_x = db.Column(db.Integer, default=0)
    position_y = db.Column(db.Integer, default=0)
    couleur = db.Column(db.String(20), default='#007bff')
    largeur = db.Column(db.Integer, default=120)
    hauteur = db.Column(db.Integer, default=60)
    
    # TIMESTAMPS POUR SYNCHRO
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    processus = db.relationship('Processus', back_populates='etapes')
    responsable = db.relationship('User', backref='etapes_gerees')
    sous_etapes = db.relationship('SousEtapeProcessus', back_populates='etape', lazy=True)
    controles = db.relationship('ControleProcessus', back_populates='etape', lazy=True)

# -------------------- PROCESSUS --------------------
class Processus(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    direction_id = db.Column(db.Integer, db.ForeignKey('direction.id'))
    service_id = db.Column(db.Integer, db.ForeignKey('service.id'))
    responsable_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    version = db.Column(db.String(20))
    statut = db.Column(db.String(20), default='actif')
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)
    
    # NOUVEAUX CHAMPS POUR SYNCHRONISATION
    a_besoin_sync = db.Column(db.Boolean, default=True)
    derniere_sync_organigramme = db.Column(db.DateTime)
    nb_etapes = db.Column(db.Integer, default=0)
    nb_liens = db.Column(db.Integer, default=0)

    # CHAMPS POUR ORGANIGRAMME FLUIDE
    largeur_canvas = db.Column(db.Integer, default=2000)
    hauteur_canvas = db.Column(db.Integer, default=1500)
    zoom_par_defaut = db.Column(db.Float, default=1.0)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    direction = db.relationship('Direction', back_populates='processus')
    service = db.relationship('Service', back_populates='processus')
    responsable = db.relationship('User', back_populates='processus_geres')
    etapes = db.relationship('EtapeProcessus', back_populates='processus', lazy=True, cascade='all, delete-orphan')
    zones_risque = db.relationship('ZoneRisqueProcessus', back_populates='processus', lazy=True)
    controles = db.relationship('ControleProcessus', back_populates='processus', lazy=True)
    liens = db.relationship('LienProcessus', back_populates='processus', lazy=True, cascade='all, delete-orphan')

# -------------------- VEILLE REGLEMENTAIRE --------------------
class VeilleReglementaire(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titre = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text)
    reference = db.Column(db.String(100))
    type_reglementation = db.Column(db.String(100))
    organisme_emetteur = db.Column(db.String(200))
    date_publication = db.Column(db.Date)
    date_application = db.Column(db.Date)
    statut = db.Column(db.String(20), default='en_vigueur')
    impact_estime = db.Column(db.String(20))
    is_active = db.Column(db.Boolean, default=True)  # Nouveau
    is_archived = db.Column(db.Boolean, default=False)  # Nouveau
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)  # Nouveau

    createur = db.relationship('User', back_populates='veilles_crees', foreign_keys=[created_by])
    actions = db.relationship('ActionConformite', back_populates='veille', lazy=True)
    documents = db.relationship('VeilleDocument', back_populates='veille', lazy=True)  # Nouveau
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)

# -------------------- ACTION CONFORMITE --------------------
class ActionConformite(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    veille_id = db.Column(db.Integer, db.ForeignKey('veille_reglementaire.id'))
    description = db.Column(db.Text, nullable=False)
    responsable_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    date_echeance = db.Column(db.Date)
    statut = db.Column(db.String(20), default='a_faire')
    date_accomplissement = db.Column(db.Date)
    commentaire = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # AJOUTER CES DEUX CHAMPS :
    is_active = db.Column(db.Boolean, default=True)
    is_archived = db.Column(db.Boolean, default=False)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)

    veille = db.relationship('VeilleReglementaire', back_populates='actions')
    responsable = db.relationship('User', back_populates='actions_conformite', foreign_keys=[responsable_id])

# -------------------- VEILLE DOCUMENT --------------------
class VeilleDocument(db.Model):  # Nouveau
    id = db.Column(db.Integer, primary_key=True)
    veille_id = db.Column(db.Integer, db.ForeignKey('veille_reglementaire.id'))
    nom_fichier = db.Column(db.String(255), nullable=False)
    nom_original = db.Column(db.String(255), nullable=False)
    type_fichier = db.Column(db.String(50))
    taille = db.Column(db.Integer)  # Taille en octets
    uploaded_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)

    veille = db.relationship('VeilleReglementaire', back_populates='documents')
    uploader = db.relationship('User', back_populates='documents_veille')

# -------------------- AUDIT --------------------
# -------------------- AUDIT --------------------
class Audit(db.Model):
    __tablename__ = 'audits'
    
    id = db.Column(db.Integer, primary_key=True)
    reference = db.Column(db.String(50), nullable=False)  # unique=True ENLEVÉ
    titre = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    type_audit = db.Column(db.String(50), nullable=False)
    
    # Dates
    date_debut_prevue = db.Column(db.Date)
    date_fin_prevue = db.Column(db.Date)
    date_debut_reelle = db.Column(db.Date)
    date_fin_reelle = db.Column(db.Date)
    
    # Statuts
    statut = db.Column(db.String(50), default='planifie')
    sous_statut = db.Column(db.String(50), default='planification')
    
    # Informations supplémentaires
    portee = db.Column(db.Text)
    objectifs = db.Column(db.Text)
    criteres = db.Column(db.Text)
    processus_id = db.Column(db.Integer, db.ForeignKey('processus_activite.id'), nullable=True)
    responsable_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    equipe_audit_ids = db.Column(db.String(500))
    participants_ids = db.Column(db.String(500))
    observateurs_ids = db.Column(db.String(500))
    parties_prenantes = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_archived = db.Column(db.Boolean, default=False)
    archived_at = db.Column(db.DateTime)
    archived_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    processus_concerne = db.Column(db.String(500))
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)
    mission_associee = db.relationship('MissionAudit', backref='audit_lie', uselist=False)

    # Membres externes
    membres_externes = db.Column(db.JSON, nullable=True, default=list)
    
    # Relations
    createur = db.relationship('User', foreign_keys=[created_by])
    responsable = db.relationship('User', foreign_keys=[responsable_id], 
                                  backref='audits_dont_je_suis_responsable')
    archiveur = db.relationship('User', foreign_keys=[archived_by], 
                               backref='audits_que_jai_archives')
    processus = db.relationship('ProcessusActivite', backref='audits')
    
    # Relations avec les autres modèles
    constatations = db.relationship('Constatation', 
                                    back_populates='audit', 
                                    lazy=True, 
                                    cascade='all, delete-orphan')
    
    recommandations = db.relationship('Recommandation', 
                                      back_populates='audit', 
                                      lazy=True, 
                                      cascade='all, delete-orphan')
    
    plans_action = db.relationship('PlanAction', 
                                   back_populates='audit', 
                                   lazy=True, 
                                   cascade='all, delete-orphan')
    
    audit_risques = db.relationship('AuditRisque', 
                                    back_populates='audit', 
                                    lazy=True, 
                                    cascade='all, delete-orphan')
    
    # ===== CONTRAINTE UNIQUE COMPOSITE =====
    __table_args__ = (
        db.UniqueConstraint('reference', 'client_id', name='uix_audit_reference_client'),
    )
    
    # ===== MÉTHODE STATIQUE DE GÉNÉRATION =====
    @staticmethod
    def generer_reference(client_id):
        """Génère une référence unique PAR CLIENT"""
        from datetime import datetime
        annee = datetime.now().year
        prefixe = f"AUD-{annee}-"
        
        count = Audit.query.filter(
            Audit.reference.like(f'{prefixe}%'),
            Audit.client_id == client_id
        ).count()
        
        return f"{prefixe}{(count + 1):04d}"
    
    # ===== MÉTHODES EXISTANTES (à conserver) =====
    
    def get_equipe_audit(self):
        """Retourne la liste des utilisateurs de l'équipe d'audit"""
        if self.equipe_audit_ids:
            try:
                ids = [int(id.strip()) for id in self.equipe_audit_ids.split(',') if id.strip()]
                if ids:
                    return User.query.filter(User.id.in_(ids)).all()
            except (ValueError, AttributeError):
                return []
        return []
    
    def get_equipe_complete(self):
        """Retourne l'équipe complète"""
        equipe = []
        
        # Utilisateurs avec compte
        users = self.get_equipe_audit()
        for user in users:
            equipe.append({
                'id': user.id,
                'nom': user.nom or '',
                'prenom': user.prenom or '',
                'username': user.username,
                'email': user.email,
                'role': user.role,
                'department': user.department,
                'type': 'utilisateur'
            })
        
        # Membres externes
        if self.membres_externes:
            for membre in self.membres_externes:
                equipe.append({
                    'id': f"ext_{len(equipe)}",
                    'nom': membre.get('nom', ''),
                    'prenom': membre.get('prenom', ''),
                    'email': membre.get('email', ''),
                    'fonction': membre.get('fonction', ''),
                    'organisation': membre.get('organisation', ''),
                    'type': 'externe'
                })
        
        return equipe

    @property
    def programme_associe(self):
        if self.mission_associee:
            return self.mission_associee.programme
        return None
    
    def ajouter_membre_externe(self, nom, prenom, email, fonction='', organisation=''):
        """Ajoute un membre externe"""
        if not self.membres_externes:
            self.membres_externes = []
        
        nouveau_membre = {
            'nom': nom,
            'prenom': prenom,
            'email': email,
            'fonction': fonction,
            'organisation': organisation
        }
        
        self.membres_externes.append(nouveau_membre)
        return nouveau_membre
    
    def supprimer_membre_externe(self, index):
        """Supprime un membre externe"""
        if self.membres_externes and 0 <= index < len(self.membres_externes):
            return self.membres_externes.pop(index)
        return None
    
    def supprimer_utilisateur_equipe(self, user_id):
        """Supprime un utilisateur de l'équipe"""
        if self.equipe_audit_ids:
            try:
                ids = [int(id.strip()) for id in self.equipe_audit_ids.split(',') if id.strip()]
                if user_id in ids:
                    ids.remove(user_id)
                    
                    if ids:
                        self.equipe_audit_ids = ','.join(str(id) for id in ids)
                    else:
                        self.equipe_audit_ids = ''
                    
                    return True
            except (ValueError, AttributeError):
                pass
        return False

    @property
    def processus_audite_display(self):
        """Retourne le nom du processus audité pour l'affichage"""
        if self.processus:
            return self.processus.nom
        elif self.processus_concerne:
            return self.processus_concerne
        return "Non spécifié"
    
    @property
    def progression_globale(self):
        """Progression globale de l'audit basée sur les constatations"""
        if not self.constatations:
            return 0
        
        points_obtenus = 0
        for constat in self.constatations:
            if constat.statut == 'clos':
                points_obtenus += 100
            elif constat.statut == 'en_cours':
                points_obtenus += 50
            elif constat.statut == 'a_valider':
                points_obtenus += 25
        
        total_points = len(self.constatations) * 100
        if total_points == 0:
            return 0
        
        progression = (points_obtenus / total_points) * 100
        return round(progression, 2)
    
    @property
    def taux_realisation_recommandations(self):
        """Taux de réalisation des recommandations"""
        if not self.recommandations:
            return 0
        
        recommandations_terminees = sum(1 for r in self.recommandations if r.statut == 'termine')
        taux = (recommandations_terminees / len(self.recommandations)) * 100 if self.recommandations else 0
        return round(taux, 2)
    
    @property
    def taux_realisation_plans(self):
        """Taux de réalisation des plans d'action"""
        if not self.plans_action:
            return 0
        
        plans_termines = len([p for p in self.plans_action if p.statut == 'termine'])
        taux = (plans_termines / len(self.plans_action)) * 100
        return round(taux, 2)
    
    @property
    def score_global(self):
        """Score global de l'audit - Moyenne pondérée"""
        if not self.constatations and not self.recommandations and not self.plans_action:
            return 0
        
        poids = {
            'progression': 0.4,
            'recommandations': 0.4,
            'plans': 0.2
        }
        
        score = (
            self.progression_globale * poids['progression'] +
            self.taux_realisation_recommandations * poids['recommandations'] +
            self.taux_realisation_plans * poids['plans']
        )
        
        return min(round(score, 2), 100)
    
    @property
    def couleur_progression(self):
        """Retourne la couleur Bootstrap en fonction du score"""
        score = self.score_global
        if score >= 80:
            return 'success'
        elif score >= 60:
            return 'info'
        elif score >= 40:
            return 'warning'
        else:
            return 'danger'
    
    def set_processus(self, processus_id=None, nom_manuel=None):
        """Définit le processus audité soit par ID soit par nom manuel"""
        if processus_id:
            self.processus_id = processus_id
            self.processus_concerne = None
        elif nom_manuel:
            self.processus_concerne = nom_manuel
            self.processus_id = None
    
    @property
    def pourcentage_completion(self):
        """Pourcentage de completion basé sur les dates"""
        if not self.date_debut_reelle or not self.date_fin_prevue:
            return 0
        
        if self.date_fin_reelle:
            return 100
        
        aujourdhui = datetime.utcnow().date()
        
        if aujourdhui < self.date_debut_reelle:
            return 0
        
        if aujourdhui > self.date_fin_prevue:
            return 100
        
        duree_totale = (self.date_fin_prevue - self.date_debut_reelle).days
        duree_ecoulee = (aujourdhui - self.date_debut_reelle).days
        
        if duree_totale <= 0:
            return 100
        
        pourcentage = (duree_ecoulee / duree_totale) * 100
        return min(round(pourcentage, 2), 100)
    
    def get_participants(self):
        """Retourne la liste des participants"""
        if self.participants_ids:
            try:
                ids = [int(id.strip()) for id in self.participants_ids.split(',') if id.strip()]
                if ids:
                    return User.query.filter(User.id.in_(ids)).all()
            except (ValueError, AttributeError):
                return []
        return []
    
    def get_observateurs(self):
        """Retourne la liste des observateurs"""
        if self.observateurs_ids:
            try:
                ids = [int(id.strip()) for id in self.observateurs_ids.split(',') if id.strip()]
                if ids:
                    return User.query.filter(User.id.in_(ids)).all()
            except (ValueError, AttributeError):
                return []
        return []
    
    def get_risques_lies(self):
        """Retourne tous les risques liés à cet audit"""
        risques = []
        risques_ids = set()
        
        # Via les recommandations
        for recommandation in self.recommandations:
            if recommandation.risque_id and recommandation.risque_id not in risques_ids:
                risque = Risque.query.get(recommandation.risque_id)
                if risque:
                    risques.append(risque)
                    risques_ids.add(recommandation.risque_id)
        
        # Via les plans d'action
        for plan in self.plans_action:
            if plan.risque_id and plan.risque_id not in risques_ids:
                risque = Risque.query.get(plan.risque_id)
                if risque:
                    risques.append(risque)
                    risques_ids.add(plan.risque_id)
        
        # Via la table d'association directe
        for audit_risque in self.audit_risques:
            if audit_risque.risque_id and audit_risque.risque_id not in risques_ids:
                risque = Risque.query.get(audit_risque.risque_id)
                if risque:
                    risques.append(risque)
                    risques_ids.add(audit_risque.risque_id)
        
        return risques
    
    def get_statut_display(self):
        """Retourne le statut formaté pour l'affichage"""
        statuts = {
            'planifie': 'Planifié',
            'en_cours': 'En cours',
            'termine': 'Terminé',
            'suspendu': 'Suspendu',
            'annule': 'Annulé'
        }
        return statuts.get(self.statut, self.statut)
    
    def get_sous_statut_display(self):
        """Retourne le sous-statut formaté"""
        sous_statuts = {
            'planification': 'Planification',
            'preparation': 'Préparation',
            'execution': 'Exécution',
            'rapport': 'Rapport',
            'suivi': 'Suivi',
            'cloture': 'Clôture'
        }
        return sous_statuts.get(self.sous_statut, self.sous_statut)
    
    def update_progression(self):
        """Met à jour automatiquement le statut en fonction de la progression"""
        if self.date_fin_reelle:
            self.statut = 'termine'
        elif self.date_debut_reelle and not self.date_fin_reelle:
            self.statut = 'en_cours'
        
        # Mise à jour du sous-statut basé sur la progression
        progression = self.score_global
        if progression >= 90:
            self.sous_statut = 'cloture'
        elif progression >= 70:
            self.sous_statut = 'suivi'
        elif progression >= 40:
            self.sous_statut = 'rapport'
        elif progression >= 20:
            self.sous_statut = 'execution'
        elif progression > 0:
            self.sous_statut = 'preparation'
        else:
            self.sous_statut = 'planification'
    
    def __repr__(self):
        return f'<Audit {self.reference}: {self.titre}>'
    
# -------------------- AUDIT RISQUE - CORRIGÉ --------------------
class AuditRisque(db.Model):
    __tablename__ = 'audit_risques'
    
    id = db.Column(db.Integer, primary_key=True)
    audit_id = db.Column(db.Integer, db.ForeignKey('audits.id'), nullable=False)  # 'audits.id' au lieu de 'audit.id'
    risque_id = db.Column(db.Integer, db.ForeignKey('risques.id'), nullable=False)
    impact_audit = db.Column(db.String(50))  # aggravé, réduit, neutre
    commentaire = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relations corrigées
    audit = db.relationship('Audit', back_populates='audit_risques')
    risque = db.relationship('Risque', backref='audit_associations')

# -------------------- CONSTATATION - CORRIGÉ ET COMPLET --------------------
class Constatation(db.Model):
    __tablename__ = 'constatations'
    
    id = db.Column(db.Integer, primary_key=True)
    reference = db.Column(db.String(50), nullable=False)  # ← unique=True ENLEVÉ
    description = db.Column(db.Text, nullable=False)
    type_constatation = db.Column(db.String(50), nullable=False)
    gravite = db.Column(db.String(50))
    
    # Nouveaux champs
    criticite = db.Column(db.String(50))  # mineure, majeure, critique
    processus_concerne = db.Column(db.String(500))  # Augmenter la longueur
    cause_racine = db.Column(db.Text)  # Méthode 5 Why
    documents_justificatifs = db.Column(db.Text)
    
    # Workflow intelligent
    statut = db.Column(db.String(50), default='a_analyser')  # a_analyser, a_valider, en_action, clos
    
    # Fichiers joints
    fichiers_ids = db.Column(db.String(500))  # Références aux fichiers
    preuves = db.Column(db.Text)
    
    # Liens
    audit_id = db.Column(db.Integer, db.ForeignKey('audits.id'), nullable=False)
    risque_id = db.Column(db.Integer, db.ForeignKey('risques.id'))
    
    # Conclusion et commentaires
    conclusion = db.Column(db.Text)  # Pour le rapport définitif
    commentaires = db.Column(db.Text)  # Commentaires internes
    recommandations_immediates = db.Column(db.Text)  # Actions immédiates proposées
    
    # Audit
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_archived = db.Column(db.Boolean, default=False)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)
    
    # ===== RELATIONS =====
    audit = db.relationship('Audit', back_populates='constatations')
    risque = db.relationship('Risque', backref='constatations')
    createur = db.relationship('User', foreign_keys=[created_by])
    recommandations = db.relationship('Recommandation', back_populates='constatation', lazy=True)
    
    # ===== CONTRAINTE UNIQUE COMPOSITE =====
    __table_args__ = (
        db.UniqueConstraint('reference', 'client_id', name='uix_constatation_reference_client'),
    )
    
    # ===== MÉTHODE STATIQUE DE GÉNÉRATION =====
    @staticmethod
    def generer_reference(client_id):
        """Génère une référence unique PAR CLIENT"""
        from datetime import datetime
        annee = datetime.now().year
        prefixe = f"CONST-{annee}-"
        
        count = Constatation.query.filter(
            Constatation.reference.like(f'{prefixe}%'),
            Constatation.client_id == client_id
        ).count()
        
        return f"{prefixe}{(count + 1):04d}"
    
    # ===== INITIALISATION =====
    def __init__(self, **kwargs):
        """Initialise une constatation avec génération automatique de la référence"""
        # Générer la référence si non fournie et si client_id est présent
        if 'reference' not in kwargs and 'client_id' in kwargs and kwargs['client_id']:
            kwargs['reference'] = self.generer_reference(kwargs['client_id'])
        
        super().__init__(**kwargs)
    
    # ===== PROPRIÉTÉS CALCULÉES =====
    
    @property
    def couleur_criticite(self):
        return {
            'mineure': 'info',
            'moyenne': 'warning',
            'majeure': 'danger',
            'critique': 'dark'
        }.get(self.criticite or 'mineure', 'secondary')
    
    @property
    def processus_audite_display(self):
        """Retourne le nom du processus concerné"""
        if self.processus_concerne:
            return self.processus_concerne
        elif self.audit and self.audit.processus:
            return self.audit.processus.nom
        return None
    
    @property
    def get_preuves_list(self):
        """Retourne la liste des preuves sous forme de liste Python"""
        if self.preuves:
            # Si les preuves sont stockées séparées par des virgules
            return [p.strip() for p in self.preuves.split(',') if p.strip()]
        return []
    
    @property
    def get_couleur_statut(self):
        """Couleur Bootstrap pour le statut"""
        couleurs = {
            'a_analyser': 'secondary',
            'a_valider': 'warning',
            'en_action': 'info',
            'clos': 'success'
        }
        return couleurs.get(self.statut, 'light')
    
    @property
    def get_statut_label(self):
        """Libellé du statut en français"""
        labels = {
            'a_analyser': 'À analyser',
            'a_valider': 'À valider',
            'en_action': 'En action',
            'clos': 'Clos'
        }
        return labels.get(self.statut, self.statut)
    
    @property
    def get_criticite_label(self):
        """Libellé de la criticité en français"""
        labels = {
            'mineure': 'Mineure',
            'moyenne': 'Moyenne',
            'majeure': 'Majeure',
            'critique': 'Critique'
        }
        return labels.get(self.criticite, 'Non définie')
    
    @property
    def get_gravite_label(self):
        """Libellé de la gravité en français"""
        labels = {
            'faible': 'Faible',
            'moyenne': 'Moyenne',
            'elevee': 'Élevée',
            'critique': 'Critique'
        }
        return labels.get(self.gravite, 'Non définie')
    
    @property
    def nb_preuves(self):
        """Retourne le nombre de preuves"""
        return len(self.get_preuves_list)
    
    @property
    def nb_fichiers(self):
        """Retourne le nombre de fichiers joints"""
        return len(self.get_fichiers_list())
    
    # ===== MÉTHODES DE GESTION DES FICHIERS =====
    
    def get_fichiers_list(self):
        """Retourne la liste des IDs de fichiers"""
        if self.fichiers_ids:
            try:
                return [int(id.strip()) for id in self.fichiers_ids.split(',') if id.strip()]
            except (ValueError, AttributeError):
                return []
        return []
    
    def ajouter_preuve(self, nom_fichier):
        """Ajoute une preuve à la constatation"""
        if not self.preuves:
            self.preuves = nom_fichier
        else:
            preuves_list = self.get_preuves_list
            if nom_fichier not in preuves_list:
                preuves_list.append(nom_fichier)
                self.preuves = ','.join(preuves_list)
        self.updated_at = datetime.utcnow()
    
    def supprimer_preuve(self, nom_fichier):
        """Supprime une preuve de la constatation"""
        if self.preuves:
            preuves_list = self.get_preuves_list
            if nom_fichier in preuves_list:
                preuves_list.remove(nom_fichier)
                self.preuves = ','.join(preuves_list) if preuves_list else None
                self.updated_at = datetime.utcnow()
                return True
        return False
    
    def ajouter_fichier(self, fichier_id):
        """Ajoute un fichier à la constatation"""
        if not self.fichiers_ids:
            self.fichiers_ids = str(fichier_id)
        else:
            fichiers_list = self.get_fichiers_list()
            if fichier_id not in fichiers_list:
                fichiers_list.append(fichier_id)
                self.fichiers_ids = ','.join(str(id) for id in fichiers_list)
        self.updated_at = datetime.utcnow()
    
    def supprimer_fichier(self, fichier_id):
        """Supprime un fichier de la constatation"""
        if self.fichiers_ids:
            fichiers_list = self.get_fichiers_list()
            if fichier_id in fichiers_list:
                fichiers_list.remove(fichier_id)
                self.fichiers_ids = ','.join(str(id) for id in fichiers_list) if fichiers_list else None
                self.updated_at = datetime.utcnow()
                return True
        return False
    
    # ===== MÉTHODES DE WORKFLOW =====
    
    def set_processus(self, processus_id=None, nom_manuel=None, from_audit=False):
        """Définit le processus concerné"""
        if from_audit and self.audit:
            # Utiliser le processus de l'audit
            self.processus_concerne = self.audit.processus_audite_display
        elif nom_manuel:
            self.processus_concerne = nom_manuel
        elif processus_id:
            # Récupérer le nom du processus
            from models import Processus
            processus = Processus.query.get(processus_id)
            if processus:
                self.processus_concerne = processus.nom
    
    def passer_a_analyser(self, utilisateur_id=None):
        """Passe le statut à 'À analyser'"""
        self.statut = 'a_analyser'
        self.updated_at = datetime.utcnow()
        self._log_changement_statut('a_analyser', utilisateur_id)
    
    def passer_a_valider(self, utilisateur_id=None):
        """Passe le statut à 'À valider'"""
        self.statut = 'a_valider'
        self.updated_at = datetime.utcnow()
        self._log_changement_statut('a_valider', utilisateur_id)
    
    def passer_en_action(self, utilisateur_id=None):
        """Passe le statut à 'En action'"""
        self.statut = 'en_action'
        self.updated_at = datetime.utcnow()
        self._log_changement_statut('en_action', utilisateur_id)
    
    def passer_clos(self, utilisateur_id=None, conclusion=None):
        """Passe le statut à 'Clos'"""
        self.statut = 'clos'
        if conclusion:
            self.conclusion = conclusion
        if utilisateur_id:
            self.updated_by = utilisateur_id
        self.updated_at = datetime.utcnow()
        self._log_changement_statut('clos', utilisateur_id)
    
    def _log_changement_statut(self, nouveau_statut, utilisateur_id=None):
        """Log le changement de statut (à implémenter si vous avez un système de log)"""
        # Optionnel : Ajouter une entrée dans un journal d'audit
        # Vous pouvez implémenter cette méthode selon votre système de log
        pass
    
    # ===== MÉTHODES D'ARCHIVAGE =====
    
    def archiver(self, utilisateur_id=None):
        """Archive la constatation"""
        self.is_archived = True
        self.updated_at = datetime.utcnow()
        # Optionnel : enregistrer qui a archivé
        if utilisateur_id:
            self.archived_by = utilisateur_id
        self.archived_at = datetime.utcnow()
    
    def restaurer(self):
        """Restaurer une constatation archivée"""
        self.is_archived = False
        self.updated_at = datetime.utcnow()
        self.archived_at = None
        self.archived_by = None
    
    # ===== MÉTHODE DE CONVERSION =====
    
    def to_dict(self):
        """Convertit la constatation en dictionnaire pour API"""
        return {
            'id': self.id,
            'reference': self.reference,
            'description': self.description,
            'type_constatation': self.type_constatation,
            'gravite': self.gravite,
            'gravite_label': self.get_gravite_label,
            'criticite': self.criticite,
            'criticite_label': self.get_criticite_label,
            'criticite_couleur': self.couleur_criticite,
            'processus_concerne': self.processus_audite_display,
            'cause_racine': self.cause_racine,
            'statut': self.statut,
            'statut_label': self.get_statut_label,
            'statut_couleur': self.get_couleur_statut,
            'conclusion': self.conclusion,
            'commentaires': self.commentaires,
            'recommandations_immediates': self.recommandations_immediates,
            'nb_preuves': self.nb_preuves,
            'nb_fichiers': self.nb_fichiers,
            'preuves': self.get_preuves_list,
            'fichiers_ids': self.get_fichiers_list(),
            'audit_id': self.audit_id,
            'audit_reference': self.audit.reference if self.audit else None,
            'risque_id': self.risque_id,
            'risque_reference': self.risque.reference if self.risque else None,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'is_archived': self.is_archived
        }
    
    def __repr__(self):
        return f'<Constatation {self.reference}: {self.description[:50]}...>'



# models.py - Version corrigée de DemandeContact

class DemandeContact(db.Model):
    """Modèle pour les demandes de contact - SANS clé étrangère problématique"""
    __tablename__ = 'demandes_contact'
    
    id = db.Column(db.Integer, primary_key=True)
    reference = db.Column(db.String(50), unique=True, nullable=False)
    nom_complet = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(200), nullable=False)
    societe = db.Column(db.String(200))
    telephone = db.Column(db.String(50))
    sujet = db.Column(db.String(200))
    message = db.Column(db.Text, nullable=False)
    
    # Métadonnées
    ip_address = db.Column(db.String(50))
    user_agent = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Statut - SANS foreign key pour éviter l'erreur
    traite = db.Column(db.Boolean, default=False)
    traite_le = db.Column(db.DateTime)
    traite_par = db.Column(db.Integer)  # Juste l'ID, sans contrainte FK
    notes = db.Column(db.Text)
    
    def __repr__(self):
        return f'<DemandeContact {self.reference}>'

class FichierMetadata(db.Model):
    __tablename__ = 'fichiers_metadata'
    
    id = db.Column(db.Integer, primary_key=True)
    nom_fichier = db.Column(db.String(500), nullable=False)
    chemin = db.Column(db.String(1000), nullable=False)
    type_fichier = db.Column(db.String(50))
    taille = db.Column(db.Integer)  # en octets
    commentaire = db.Column(db.Text)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)  # AJOUTÉ
    responsable_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    entite_type = db.Column(db.String(50))  # 'constatation', 'audit', 'recommandation'
    entite_id = db.Column(db.Integer)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relations
    client = db.relationship('Client')  # AJOUTÉ
    responsable = db.relationship('User', foreign_keys=[responsable_id])
    createur = db.relationship('User', foreign_keys=[created_by])

    
# -------------------- RECOMMANDATION - CORRIGÉ ET COMPLET --------------------
from datetime import datetime, timezone

# Dans votre modèle Recommandation :
class Recommandation(db.Model):
    __tablename__ = 'recommandations'
    
    id = db.Column(db.Integer, primary_key=True)
    reference = db.Column(db.String(50), nullable=False)  # ← unique=True ENLEVÉ
    description = db.Column(db.Text, nullable=False)
    type_recommandation = db.Column(db.String(50), nullable=False)
    categorie = db.Column(db.String(50))
    delai_mise_en_oeuvre = db.Column(db.String(50))
    date_echeance = db.Column(db.Date)
    urgence = db.Column(db.Integer, default=1)
    impact_operationnel = db.Column(db.Integer, default=1)
    score_priorite = db.Column(db.Integer, default=0)
    statut = db.Column(db.String(50), default='a_traiter')
    taux_avancement = db.Column(db.Integer, default=0)
    audit_id = db.Column(db.Integer, db.ForeignKey('audits.id'), nullable=False)
    constatation_id = db.Column(db.Integer, db.ForeignKey('constatations.id'))
    risque_id = db.Column(db.Integer, db.ForeignKey('risques.id'), nullable=True)
    responsable_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                          onupdate=lambda: datetime.now(timezone.utc))
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)
    
    # ===== RELATIONS =====
    audit = db.relationship('Audit', back_populates='recommandations')
    constatation = db.relationship('Constatation', back_populates='recommandations')
    risque = db.relationship('Risque', backref='recommandations')
    responsable = db.relationship('User', foreign_keys=[responsable_id], backref='recommandations_responsable')
    createur = db.relationship('User', foreign_keys=[created_by], backref='recommandations_crees')
    plan_action = db.relationship('PlanAction', back_populates='recommandation', uselist=False, lazy=True)
    historique = db.relationship('HistoriqueRecommandation', backref='recommandation', lazy=True, cascade='all, delete-orphan')
    client = db.relationship('Client')
    
    # ===== CONTRAINTE UNIQUE COMPOSITE =====
    __table_args__ = (
        db.UniqueConstraint('reference', 'client_id', name='uix_recommandation_reference_client'),
    )
    
    # ===== MÉTHODE STATIQUE DE GÉNÉRATION =====
    @staticmethod
    def generer_reference(client_id):
        """Génère une référence unique PAR CLIENT"""
        from datetime import datetime
        annee = datetime.now().year
        prefixe = f"RECO-{annee}-"
        
        count = Recommandation.query.filter(
            Recommandation.reference.like(f'{prefixe}%'),
            Recommandation.client_id == client_id
        ).count()
        
        return f"{prefixe}{(count + 1):04d}"
    
    # ===== INITIALISATION =====
    def __init__(self, **kwargs):
        # Générer la référence si non fournie
        if 'reference' not in kwargs and 'client_id' in kwargs:
            kwargs['reference'] = self.generer_reference(kwargs['client_id'])
        
        super().__init__(**kwargs)
        self.calculer_score_priorite()
    
    # ===== MÉTHODES DE CALCUL =====
    def calculer_score_priorite(self):
        """Calcule automatiquement le score de priorité"""
        score = (self.urgence * 0.4 + self.impact_operationnel * 0.6) * 20
        
        if self.risque and hasattr(self.risque, 'evaluations') and self.risque.evaluations:
            try:
                derniere_eval = sorted(self.risque.evaluations, key=lambda x: x.created_at)[-1]
                score += derniere_eval.score_risque * 0.2
            except (IndexError, AttributeError):
                pass
        
        self.score_priorite = min(100, int(score))
        return self.score_priorite
    
    def recalculer_score(self):
        """Recalcule le score de priorité (alias pour compatibilité)"""
        return self.calculer_score_priorite()
    
    # ===== PROPRIÉTÉS CALCULÉES =====
    @property
    def couleur_statut(self):
        couleurs = {
            'a_traiter': 'secondary',
            'en_cours': 'warning',
            'termine': 'success',
            'retarde': 'danger',
            'annule': 'dark'
        }
        return couleurs.get(self.statut, 'light')
    
    @property
    def get_statut_label(self):
        """Libellé du statut en français"""
        labels = {
            'a_traiter': 'À traiter',
            'en_cours': 'En cours',
            'termine': 'Terminé',
            'retarde': 'Retardé',
            'annule': 'Annulé'
        }
        return labels.get(self.statut, self.statut)
    
    @property
    def est_en_retard(self):
        if not self.date_echeance or self.statut == 'termine':
            return False
        return datetime.now(timezone.utc).date() > self.date_echeance
    
    @property
    def get_priorite_label(self):
        """Libellé de la priorité basé sur le score"""
        if self.score_priorite >= 80:
            return 'Critique'
        elif self.score_priorite >= 60:
            return 'Élevée'
        elif self.score_priorite >= 40:
            return 'Moyenne'
        else:
            return 'Faible'
    
    @property
    def get_priorite_couleur(self):
        """Couleur Bootstrap pour la priorité"""
        if self.score_priorite >= 80:
            return 'danger'
        elif self.score_priorite >= 60:
            return 'warning'
        elif self.score_priorite >= 40:
            return 'info'
        else:
            return 'secondary'
    
    @property
    def jours_restants(self):
        """Jours restants avant échéance"""
        if not self.date_echeance or self.statut == 'termine':
            return None
        delta = self.date_echeance - datetime.now(timezone.utc).date()
        return max(0, delta.days)
    
    @property
    def progression_display(self):
        """Affichage de la progression avec icône"""
        if self.taux_avancement == 100:
            return '✅ Terminé'
        elif self.taux_avancement >= 75:
            return '🚀 Bien avancé'
        elif self.taux_avancement >= 50:
            return '📈 En bonne voie'
        elif self.taux_avancement >= 25:
            return '⏳ En cours'
        else:
            return '🟢 Nouvelle'
    
    # ===== MÉTHODES DE WORKFLOW =====
    def changer_statut(self, nouveau_statut, utilisateur_id, commentaire=None):
        ancien_statut = self.statut
        self.statut = nouveau_statut
        
        historique = HistoriqueRecommandation(
            recommandation_id=self.id,
            action='changement_statut',
            details={
                'ancien_statut': ancien_statut,
                'nouveau_statut': nouveau_statut,
                'commentaire': commentaire,
                'date': datetime.now(timezone.utc).isoformat()
            },
            utilisateur_id=utilisateur_id
        )
        db.session.add(historique)
        
        if nouveau_statut == 'termine':
            self.taux_avancement = 100
        
        self.updated_at = datetime.now(timezone.utc)
        db.session.commit()
    
    def mettre_a_jour_avancement(self, nouveau_taux, utilisateur_id):
        ancien_taux = self.taux_avancement
        self.taux_avancement = min(100, max(0, nouveau_taux))
        
        historique = HistoriqueRecommandation(
            recommandation_id=self.id,
            action='mise_a_jour_avancement',
            details={
                'ancien_taux': ancien_taux,
                'nouveau_taux': self.taux_avancement,
                'date': datetime.now(timezone.utc).isoformat()
            },
            utilisateur_id=utilisateur_id
        )
        db.session.add(historique)
        
        if self.taux_avancement == 100 and self.statut != 'termine':
            self.statut = 'termine'
        
        self.updated_at = datetime.now(timezone.utc)
        db.session.commit()
    
    def mettre_en_cours(self, utilisateur_id, commentaire=None):
        """Passe la recommandation en cours"""
        self.changer_statut('en_cours', utilisateur_id, commentaire)
    
    def terminer(self, utilisateur_id, commentaire=None):
        """Termine la recommandation"""
        self.changer_statut('termine', utilisateur_id, commentaire)
    
    def annuler(self, utilisateur_id, commentaire=None):
        """Annule la recommandation"""
        self.changer_statut('annule', utilisateur_id, commentaire)
    
    # ===== MÉTHODES DE GESTION =====
    def prolonger_delai(self, nouvelles_jours, utilisateur_id, raison=None):
        """Prolonge le délai de la recommandation"""
        if self.date_echeance:
            from datetime import timedelta
            ancienne_date = self.date_echeance
            self.date_echeance = self.date_echeance + timedelta(days=nouvelles_jours)
            
            historique = HistoriqueRecommandation(
                recommandation_id=self.id,
                action='prolongation',
                details={
                    'ancienne_date': ancienne_date.isoformat(),
                    'nouvelle_date': self.date_echeance.isoformat(),
                    'jours_ajoutes': nouvelles_jours,
                    'raison': raison
                },
                utilisateur_id=utilisateur_id
            )
            db.session.add(historique)
            self.updated_at = datetime.now(timezone.utc)
            db.session.commit()
            return True
        return False
    
    def changer_responsable(self, nouveau_responsable_id, utilisateur_id, raison=None):
        """Change le responsable de la recommandation"""
        ancien_responsable_id = self.responsable_id
        self.responsable_id = nouveau_responsable_id
        
        historique = HistoriqueRecommandation(
            recommandation_id=self.id,
            action='changement_responsable',
            details={
                'ancien_responsable_id': ancien_responsable_id,
                'nouveau_responsable_id': nouveau_responsable_id,
                'raison': raison
            },
            utilisateur_id=utilisateur_id
        )
        db.session.add(historique)
        self.updated_at = datetime.now(timezone.utc)
        db.session.commit()
    
    # ===== MÉTHODES D'ARCHIVAGE =====
    def archiver(self):
        """Archive la recommandation (soft delete)"""
        self.is_archived = True
        self.updated_at = datetime.now(timezone.utc)
    
    def restaurer(self):
        """Restaure une recommandation archivée"""
        self.is_archived = False
        self.updated_at = datetime.now(timezone.utc)
    
    # ===== MÉTHODE DE CONVERSION =====
    def to_dict(self):
        """Convertit la recommandation en dictionnaire pour API"""
        return {
            'id': self.id,
            'reference': self.reference,
            'description': self.description,
            'type_recommandation': self.type_recommandation,
            'categorie': self.categorie,
            'delai_mise_en_oeuvre': self.delai_mise_en_oeuvre,
            'date_echeance': self.date_echeance.isoformat() if self.date_echeance else None,
            'urgence': self.urgence,
            'impact_operationnel': self.impact_operationnel,
            'score_priorite': self.score_priorite,
            'priorite_label': self.get_priorite_label,
            'priorite_couleur': self.get_priorite_couleur,
            'statut': self.statut,
            'statut_label': self.get_statut_label,
            'statut_couleur': self.couleur_statut,
            'taux_avancement': self.taux_avancement,
            'progression_display': self.progression_display,
            'est_en_retard': self.est_en_retard,
            'jours_restants': self.jours_restants,
            'audit_id': self.audit_id,
            'audit_reference': self.audit.reference if self.audit else None,
            'constatation_id': self.constatation_id,
            'constatation_reference': self.constatation.reference if self.constatation else None,
            'risque_id': self.risque_id,
            'responsable_id': self.responsable_id,
            'responsable_nom': self.responsable.username if self.responsable else None,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'has_plan_action': self.plan_action is not None,
            'plan_action_id': self.plan_action.id if self.plan_action else None
        }
    
    def __repr__(self):
        return f'<Recommandation {self.reference}: {self.description[:50]}...>'

# -------------------- HISTORIQUE RECOMMANDATION - CORRIGÉ --------------------
class HistoriqueRecommandation(db.Model):
    __tablename__ = 'historique_recommandations'
    
    id = db.Column(db.Integer, primary_key=True)
    recommandation_id = db.Column(db.Integer, db.ForeignKey('recommandations.id'), nullable=False)
    action = db.Column(db.String(50), nullable=False)  # creation, modification, changement_statut, changement_responsable, prolongation
    details = db.Column(db.JSON)  # Stocke les changements
    utilisateur_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)
   
    utilisateur = db.relationship('User')
    
    @property
    def get_action_display(self):
        """Retourne l'action formatée"""
        actions = {
            'creation': 'Création',
            'modification': 'Modification',
            'changement_statut': 'Changement de statut',
            'changement_responsable': 'Changement de responsable',
            'prolongation': 'Prolongation',
            'mise_a_jour_avancement': 'Mise à jour avancement'
        }
        return actions.get(self.action, self.action)
    
    def __repr__(self):
        return f'<HistoriqueReco {self.action} pour rec {self.recommandation_id}>'


# ============================================
# 1. DÉFINIR LES TABLES D'ASSOCIATION EN PREMIER
# ============================================

# Table d'association pour la relation plusieurs-à-plusieurs entre plans et audits
plan_audits = db.Table('plan_audits',
    db.Column('plan_id', db.Integer, db.ForeignKey('plans_action.id'), primary_key=True),
    db.Column('audit_id', db.Integer, db.ForeignKey('audits.id'), primary_key=True),
    db.Column('created_at', db.DateTime, default=datetime.utcnow),
    db.Column('created_by', db.Integer, db.ForeignKey('user.id'))
)


# ============================================
# MODULE FEUILLES DE TRAVAIL (WORKPAPERS)
# ============================================

class FeuilleTravail(db.Model):
    """Feuille de travail pour une mission d'audit"""
    __tablename__ = 'feuilles_travail'
    
    id = db.Column(db.Integer, primary_key=True)
    reference = db.Column(db.String(50), unique=True, nullable=False)
    titre = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    
    # Liens
    audit_id = db.Column(db.Integer, db.ForeignKey('audits.id'), nullable=False)
    mission_id = db.Column(db.Integer, db.ForeignKey('missions_audit.id'), nullable=True)
    constatation_id = db.Column(db.Integer, db.ForeignKey('constatations.id'), nullable=True)
    
    # Type de feuille
    type_feuille = db.Column(db.String(50), default='standard')  # standard, checklist, test, analyse
    statut = db.Column(db.String(50), default='brouillon')  # brouillon, en_cours, termine, valide
    
    # Contenu structuré (JSON)
    contenu = db.Column(db.JSON, default={})
    
    # Références croisées
    procedure_id = db.Column(db.Integer, db.ForeignKey('controle_processus.id'), nullable=True)
    risque_id = db.Column(db.Integer, db.ForeignKey('risques.id'), nullable=True)
    controle_id = db.Column(db.Integer, db.ForeignKey('controle_processus.id'), nullable=True)
    
    # Personnes
    preparee_par_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    verifiee_par_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    approuvee_par_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    # Dates
    date_preparation = db.Column(db.DateTime, default=datetime.utcnow)
    date_verification = db.Column(db.DateTime)
    date_approbation = db.Column(db.DateTime)
    
    # Documents joints
    pieces_jointes = db.Column(db.Text)
    
    # Métadonnées multi-tenant
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'))
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_archived = db.Column(db.Boolean, default=False)
    
    # Relations
    audit = db.relationship('Audit', foreign_keys=[audit_id], backref='feuilles_travail')
    mission = db.relationship('MissionAudit', foreign_keys=[mission_id])
    constatation = db.relationship('Constatation', foreign_keys=[constatation_id])
    preparee_par = db.relationship('User', foreign_keys=[preparee_par_id])
    verifiee_par = db.relationship('User', foreign_keys=[verifiee_par_id])
    approuvee_par = db.relationship('User', foreign_keys=[approuvee_par_id])
    createur = db.relationship('User', foreign_keys=[created_by])
    
    tests = db.relationship('TestControleFeuille', back_populates='feuille', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<FeuilleTravail {self.reference}>'
    
    def generer_reference(self):
        """Génère une référence unique et robuste"""
        annee = datetime.now().year
        prefixe = f"FT-{annee}-"
        
        # Trouver le dernier numéro utilisé
        dernier = FeuilleTravail.query.filter(
            FeuilleTravail.reference.like(f'{prefixe}%'),
            FeuilleTravail.client_id == self.client_id
        ).order_by(FeuilleTravail.id.desc()).first()
        
        if dernier and dernier.reference:
            try:
                # Extraire le numéro de la dernière référence
                numero = int(dernier.reference.split('-')[-1])
                nouveau_numero = numero + 1
            except (ValueError, IndexError):
                nouveau_numero = 1
        else:
            nouveau_numero = 1
        
        return f"{prefixe}{nouveau_numero:04d}"
    
    def to_dict(self):
        return {
            'id': self.id,
            'reference': self.reference,
            'titre': self.titre,
            'description': self.description,
            'type_feuille': self.type_feuille,
            'statut': self.statut,
            'contenu': self.contenu,
            'date_preparation': self.date_preparation.isoformat() if self.date_preparation else None
        }
    
    @property
    def progression(self):
        """Calcule la progression basée sur les tests"""
        if not self.tests:
            return 0
        total = len(self.tests)
        termines = len([t for t in self.tests if t.resultat == 'conforme'])
        return round((termines / total) * 100) if total > 0 else 0



class TestControleFeuille(db.Model):
    """Ligne de test de contrôle dans une feuille de travail - Version Ultra Complète"""
    __tablename__ = 'tests_controle_feuille'
    
    id = db.Column(db.Integer, primary_key=True)
    feuille_travail_id = db.Column(db.Integer, db.ForeignKey('feuilles_travail.id'), nullable=False)
    
    # ============================================
    # 1. INFORMATIONS GÉNÉRALES
    # ============================================
    objet_test = db.Column(db.String(200), nullable=False)
    objectif_controle = db.Column(db.Text)  # Objectif spécifique du contrôle
    reference_norme = db.Column(db.String(100))  # Référence à une norme (ISO, COSO, etc.)
    
    # ============================================
    # 2. PROCÉDURE DÉTAILLÉE
    # ============================================
    procedure = db.Column(db.Text)
    criteres_acceptation = db.Column(db.Text)  # Critères pour considérer le test conforme
    etapes_cles = db.Column(db.Text)  # Étapes clés séparées par des sauts de ligne
    
    # ============================================
    # 3. ÉCHANTILLONNAGE
    # ============================================
    echantillon = db.Column(db.Text)
    methode_echantillonnage = db.Column(db.String(50))  # aléatoire, ciblé, statistique, exhaustif, stratifié
    taille_echantillon = db.Column(db.Integer)
    population_totale = db.Column(db.Integer)
    periode_couverte = db.Column(db.String(200))
    taux_confiance = db.Column(db.Float)  # Pourcentage (ex: 95)
    marge_erreur = db.Column(db.Float)  # Pourcentage
    
    # ============================================
    # 4. RÉSULTATS DU TEST
    # ============================================
    resultat = db.Column(db.String(50), default='non_testé')  # non_testé, conforme, non_conforme, na, partiellement_conforme
    observations = db.Column(db.Text)
    ecart_constate = db.Column(db.Text)
    
    # Classification des anomalies
    classification_anomalie = db.Column(db.String(50))  # mineure, majeure, critique, information
    impact_financier = db.Column(db.Float)
    impact_fonctionnel = db.Column(db.Text)
    cause_racine = db.Column(db.Text)  # Analyse de la cause racine
    
    # ============================================
    # 5. CORRECTIONS ET ACTIONS
    # ============================================
    correction_effectuee = db.Column(db.Boolean, default=False)
    date_correction = db.Column(db.Date)
    correction_commentaire = db.Column(db.Text)
    action_curative = db.Column(db.Text)  # Action immédiate
    action_preventive = db.Column(db.Text)  # Action pour éviter récurrence
    responsable_correction_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    # ============================================
    # 6. PREUVES ET DOCUMENTS
    # ============================================
    preuves = db.Column(db.Text)  # Noms des fichiers séparés par ;
    url_preuves = db.Column(db.Text)  # Liens externes
    lien_grille_controle = db.Column(db.String(500))  # Lien vers grille Excel
    
    # ============================================
    # 7. APPROBATION ET REVUE
    # ============================================
    statut_revision = db.Column(db.String(50), default='brouillon')  # brouillon, en_revision, approuve, rejete
    approuve_par_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    approuve_le = db.Column(db.DateTime)
    commentaire_revision = db.Column(db.Text)
    
    # ============================================
    # 8. MÉTRIQUES ET SUIVI
    # ============================================
    nb_erreurs_trouvees = db.Column(db.Integer, default=0)
    nb_elements_testes = db.Column(db.Integer, default=0)
    taux_reussite = db.Column(db.Float)  # Calculé automatiquement
    temps_passe_minutes = db.Column(db.Integer)  # Temps passé sur ce test
    difficulte = db.Column(db.String(20))  # facile, moyen, difficile
    
    # ============================================
    # 9. RISQUES ET CRITICITÉ
    # ============================================
    risque_associe_id = db.Column(db.Integer, db.ForeignKey('risques.id'))
    niveau_criticite = db.Column(db.String(20))  # faible, moyen, eleve, critique
    probabilite_occurrence = db.Column(db.String(20))  # rare, possible, probable, frequente
    gravite_impact = db.Column(db.String(20))  # mineur, modere, severe, critique
    
    # ============================================
    # 10. CHAMPS SYSTÈME
    # ============================================
    ordre = db.Column(db.Integer, default=0)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    is_archived = db.Column(db.Boolean, default=False)
    
    # ============================================
    # RELATIONS
    # ============================================
    feuille = db.relationship('FeuilleTravail', back_populates='tests')
    risque = db.relationship('Risque', foreign_keys=[risque_associe_id])
    createur = db.relationship('User', foreign_keys=[created_by], lazy='joined')
    moderateur = db.relationship('User', foreign_keys=[updated_by], lazy='joined')
    approbateur = db.relationship('User', foreign_keys=[approuve_par_id], lazy='joined')
    responsable_correction = db.relationship('User', foreign_keys=[responsable_correction_id], lazy='joined')
    
    def __repr__(self):
        return f'<TestControleFeuille {self.id}: {self.objet_test[:50]}>'
    
    def to_dict(self, include_all=False):
        """Convertir en dictionnaire"""
        base_dict = {
            'id': self.id,
            'objet_test': self.objet_test,
            'procedure': self.procedure,
            'echantillon': self.echantillon,
            'resultat': self.resultat,
            'observations': self.observations,
            'ecart_constate': self.ecart_constate,
            'preuves': self.preuves.split(';') if self.preuves else [],
            'ordre': self.ordre,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'statut_revision': self.statut_revision,
            'taux_reussite': self.taux_reussite,
            'niveau_criticite': self.niveau_criticite
        }
        
        if include_all:
            extra_dict = {
                'objectif_controle': self.objectif_controle,
                'reference_norme': self.reference_norme,
                'criteres_acceptation': self.criteres_acceptation,
                'etapes_cles': self.etapes_cles,
                'methode_echantillonnage': self.methode_echantillonnage,
                'taille_echantillon': self.taille_echantillon,
                'population_totale': self.population_totale,
                'periode_couverte': self.periode_couverte,
                'taux_confiance': self.taux_confiance,
                'marge_erreur': self.marge_erreur,
                'classification_anomalie': self.classification_anomalie,
                'impact_financier': self.impact_financier,
                'impact_fonctionnel': self.impact_fonctionnel,
                'cause_racine': self.cause_racine,
                'correction_effectuee': self.correction_effectuee,
                'date_correction': self.date_correction.isoformat() if self.date_correction else None,
                'correction_commentaire': self.correction_commentaire,
                'action_curative': self.action_curative,
                'action_preventive': self.action_preventive,
                'responsable_correction': self.responsable_correction.username if self.responsable_correction else None,
                'url_preuves': self.url_preuves,
                'lien_grille_controle': self.lien_grille_controle,
                'approuve_par': self.approbateur.username if self.approbateur else None,
                'approuve_le': self.approuve_le.isoformat() if self.approuve_le else None,
                'commentaire_revision': self.commentaire_revision,
                'nb_erreurs_trouvees': self.nb_erreurs_trouvees,
                'nb_elements_testes': self.nb_elements_testes,
                'temps_passe_minutes': self.temps_passe_minutes,
                'difficulte': self.difficulte,
                'risque_associe_id': self.risque_associe_id,
                'probabilite_occurrence': self.probabilite_occurrence,
                'gravite_impact': self.gravite_impact,
                'created_by': self.createur.username if self.createur else None,
                'updated_by': self.moderateur.username if self.moderateur else None,
                'is_archived': self.is_archived
            }
            base_dict.update(extra_dict)
        
        return base_dict
    
    def calculer_taux_reussite(self):
        """Calculer automatiquement le taux de réussite"""
        if self.nb_elements_testes > 0:
            taux = ((self.nb_elements_testes - self.nb_erreurs_trouvees) / self.nb_elements_testes) * 100
            self.taux_reussite = round(taux, 2)
        else:
            self.taux_reussite = None
        return self.taux_reussite
    
    @staticmethod
    def get_resultat_badge(resultat):
        """Retourner le badge HTML pour un résultat"""
        badges = {
            'non_testé': '<span class="badge bg-secondary">⏳ Non testé</span>',
            'conforme': '<span class="badge bg-success">✅ Conforme</span>',
            'non_conforme': '<span class="badge bg-danger">❌ Non conforme</span>',
            'partiellement_conforme': '<span class="badge bg-warning">⚠️ Partiellement conforme</span>',
            'na': '<span class="badge bg-info">N/A</span>'
        }
        return badges.get(resultat, '<span class="badge bg-secondary">Inconnu</span>')
    
    @staticmethod
    def get_criticite_badge(niveau):
        """Retourner le badge HTML pour la criticité"""
        badges = {
            'faible': '<span class="badge bg-success">🟢 Faible</span>',
            'moyen': '<span class="badge bg-warning">🟡 Moyen</span>',
            'eleve': '<span class="badge bg-danger">🟠 Élevé</span>',
            'critique': '<span class="badge bg-dark">🔴 Critique</span>'
        }
        return badges.get(niveau, '<span class="badge bg-secondary">Non défini</span>')

# ============================================
# MODÈLES AVANCÉS POUR FEUILLES DE TRAVAIL
# ============================================

class FeuilleTravailVersion(db.Model):
    """Historique des versions d'une feuille de travail"""
    __tablename__ = 'feuilles_travail_versions'
    
    id = db.Column(db.Integer, primary_key=True)
    feuille_travail_id = db.Column(db.Integer, db.ForeignKey('feuilles_travail.id'), nullable=False)
    version_numero = db.Column(db.Integer, nullable=False)
    
    # Snapshot du contenu
    contenu_snapshot = db.Column(db.JSON, nullable=False)
    tests_snapshot = db.Column(db.JSON)
    
    # Métadonnées de version
    version_commentaire = db.Column(db.Text)
    version_type = db.Column(db.String(50), default='modification')  # creation, modification, validation, rollback
    
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relations
    feuille = db.relationship('FeuilleTravail', backref='versions')
    createur = db.relationship('User', foreign_keys=[created_by])
    
    __table_args__ = (db.UniqueConstraint('feuille_travail_id', 'version_numero', name='unique_version'),)


class ModeleFeuilleTravail(db.Model):
    """Modèles prédéfinis de feuilles de travail (bibliothèque professionnelle)"""
    __tablename__ = 'modeles_feuilles_travail'
    
    id = db.Column(db.Integer, primary_key=True)
    reference = db.Column(db.String(50), unique=True, nullable=False)
    nom = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    categorie = db.Column(db.String(100))  # Financier, Conformité, IT, Opérationnel, etc.
    
    # Template de contenu
    template_contenu = db.Column(db.JSON, default={})
    template_tests = db.Column(db.JSON, default=[])
    
    # Niveau de maturité recommandé
    niveau_maturite = db.Column(db.Integer, default=3)  # 1-5
    
    # Standards référencés
    normes = db.Column(db.JSON, default=[])  # ISO 9001, COSO, COBIT, etc.
    
    # Usage
    nb_utilisations = db.Column(db.Integer, default=0)
    note_moyenne = db.Column(db.Float, default=0)
    
    is_public = db.Column(db.Boolean, default=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<ModeleFeuilleTravail {self.reference}: {self.nom}>'


class ReferenceCroiseeFeuille(db.Model):
    """Références croisées entre feuilles de travail et autres entités"""
    __tablename__ = 'references_croisees_feuilles'
    
    id = db.Column(db.Integer, primary_key=True)
    feuille_travail_id = db.Column(db.Integer, db.ForeignKey('feuilles_travail.id'), nullable=False)
    
    # Type de référence
    type_reference = db.Column(db.String(50), nullable=False)  # constatation, recommandation, plan_action, risque, procedure, norme
    
    # ID de l'entité référencée
    entite_id = db.Column(db.Integer, nullable=False)
    
    # Métadonnées de la référence
    contexte = db.Column(db.Text)
    est_auto_genere = db.Column(db.Boolean, default=False)
    
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    feuille = db.relationship('FeuilleTravail', backref='references_croisees')
    
    __table_args__ = (db.UniqueConstraint('feuille_travail_id', 'type_reference', 'entite_id', name='unique_reference'),)


class CommentaireFeuille(db.Model):
    """Système de commentaires collaboratifs avec résolution"""
    __tablename__ = 'commentaires_feuille'
    
    id = db.Column(db.Integer, primary_key=True)
    feuille_travail_id = db.Column(db.Integer, db.ForeignKey('feuilles_travail.id'), nullable=False)
    
    # Position dans la feuille
    section = db.Column(db.String(100))  # general, test_{id}, preuve_{id}
    ligne = db.Column(db.Integer)
    colonne = db.Column(db.Integer)
    
    # Contenu
    contenu = db.Column(db.Text, nullable=False)
    
    # Métadonnées
    type_commentaire = db.Column(db.String(50), default='commentaire')  # commentaire, question, revision, approbation, rejet
    statut = db.Column(db.String(50), default='ouvert')  # ouvert, en_cours, resolu, ferme
    
    # Réponses et résolution
    reponse_a_id = db.Column(db.Integer, db.ForeignKey('commentaires_feuille.id'), nullable=True)
    resolution_commentaire = db.Column(db.Text)
    resolu_par_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    resolu_le = db.Column(db.DateTime)
    
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relations
    feuille = db.relationship('FeuilleTravail', backref='commentaires')
    reponse_a = db.relationship('CommentaireFeuille', remote_side=[id], backref='reponses')
    createur = db.relationship('User', foreign_keys=[created_by])
    resolveur = db.relationship('User', foreign_keys=[resolu_par_id])


class FavoriFeuille(db.Model):
    """Favoris des auditeurs pour accès rapide"""
    __tablename__ = 'favoris_feuilles'
    
    id = db.Column(db.Integer, primary_key=True)
    feuille_travail_id = db.Column(db.Integer, db.ForeignKey('feuilles_travail.id'), nullable=False)
    utilisateur_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    ordre = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    feuille = db.relationship('FeuilleTravail')
    utilisateur = db.relationship('User', foreign_keys=[utilisateur_id])
    
    __table_args__ = (db.UniqueConstraint('feuille_travail_id', 'utilisateur_id', name='unique_favori'),)


class TagFeuille(db.Model):
    """Tags pour catégorisation avancée"""
    __tablename__ = 'tags_feuilles'
    
    id = db.Column(db.Integer, primary_key=True)
    feuille_travail_id = db.Column(db.Integer, db.ForeignKey('feuilles_travail.id'), nullable=False)
    tag = db.Column(db.String(100), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (db.UniqueConstraint('feuille_travail_id', 'tag', name='unique_tag'),)

# ============================================
# MODULE PLAN DE DÉVELOPPEMENT DES AUDITEURS
# ============================================

# ============================================
# MODÈLES POUR LE DÉVELOPPEMENT DES AUDITEURS
# ============================================

class Competence(db.Model):
    """Compétence à développer"""
    __tablename__ = 'competences'
    
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    nom = db.Column(db.String(200), nullable=False)
    categorie = db.Column(db.String(50))  # Technique, Comportementale, Management, Normative
    description = db.Column(db.Text)
    niveau_requis = db.Column(db.Integer, default=2)  # 1: Débutant, 2: Intermédiaire, 3: Avancé, 4: Expert
    est_actif = db.Column(db.Boolean, default=True)
    
    # Métadonnées
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)
    
    def __repr__(self):
        return f'<Competence {self.code}: {self.nom}>'
    
    def get_niveau_text(self):
        niveaux = {1: 'Débutant', 2: 'Intermédiaire', 3: 'Avancé', 4: 'Expert'}
        return niveaux.get(self.niveau_requis, 'Inconnu')


class EvaluationCompetence(db.Model):
    """Évaluation des compétences d'un auditeur"""
    __tablename__ = 'evaluations_competences'
    
    id = db.Column(db.Integer, primary_key=True)
    auditeur_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    competence_id = db.Column(db.Integer, db.ForeignKey('competences.id'), nullable=False)
    
    # Niveaux d'évaluation
    niveau_actuel = db.Column(db.Integer, default=1)
    niveau_souhaite = db.Column(db.Integer, default=2)
    evaluation_superieur = db.Column(db.Integer)
    evaluation_auto = db.Column(db.Integer)
    
    # Écart et priorité
    ecart = db.Column(db.Integer)  # Calculé automatiquement
    priorite = db.Column(db.String(20), default='moyenne')  # basse, moyenne, haute, urgente
    
    # Commentaires
    commentaire_evaluateur = db.Column(db.Text)
    commentaire_auditeur = db.Column(db.Text)
    
    # Dates
    date_evaluation = db.Column(db.DateTime, default=datetime.utcnow)
    date_prochaine_evaluation = db.Column(db.DateTime)
    evaluateur_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    # Relations
    auditeur = db.relationship('User', foreign_keys=[auditeur_id])
    competence = db.relationship('Competence')
    evaluateur = db.relationship('User', foreign_keys=[evaluateur_id])
    
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)

    
    def __repr__(self):
        return f'<Evaluation {self.auditeur_id}/{self.competence_id}>'
    
    def calculer_ecart(self):
        self.ecart = self.niveau_souhaite - (self.evaluation_superieur or self.niveau_actuel)
        return self.ecart


class Formation(db.Model):
    """Formation disponible"""
    __tablename__ = 'formations'
    
    id = db.Column(db.Integer, primary_key=True)
    reference = db.Column(db.String(20), unique=True, nullable=False)
    titre = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    objectifs = db.Column(db.Text)
    
    # Détails
    duree_heures = db.Column(db.Float)
    cout = db.Column(db.Float)
    formateur = db.Column(db.String(200))
    organisme = db.Column(db.String(200))
    
    # Type et catégorie
    type_formation = db.Column(db.String(50))
    categorie = db.Column(db.String(50))
    
    # Compétences visées
    competences_visees = db.Column(db.Text)
    
    # Dates
    date_debut = db.Column(db.Date)
    date_fin = db.Column(db.Date)
    date_limite_inscription = db.Column(db.Date)
    
    # Statut
    est_actif = db.Column(db.Boolean, default=True)
    places_disponibles = db.Column(db.Integer, default=0)
    
    # Métadonnées (une seule fois chacune)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)

    
    # Relations
    createur = db.relationship('User', foreign_keys=[created_by])
    
    def __repr__(self):
        return f'<Formation {self.reference}: {self.titre}>'
    
    @staticmethod
    def generer_reference():
        annee = datetime.now().year
        count = Formation.query.filter(Formation.reference.like(f'FOR-{annee}-%')).count() + 1
        return f"FOR-{annee}-{count:04d}"

class InscriptionFormation(db.Model):
    """Inscription d'un auditeur à une formation"""
    __tablename__ = 'inscriptions_formation'
    
    id = db.Column(db.Integer, primary_key=True)
    formation_id = db.Column(db.Integer, db.ForeignKey('formations.id'), nullable=False)
    auditeur_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Statut
    statut = db.Column(db.String(50), default='inscrit')  # inscrit, en_attente, termine, abandonne
    presence_confirmee = db.Column(db.Boolean, default=False)
    validation_obtenue = db.Column(db.Boolean, default=False)
    note_obtenue = db.Column(db.Float)
    
    # Évaluation de la formation
    satisfaction = db.Column(db.Integer)  # 1-5
    commentaire = db.Column(db.Text)
    
    # Dates
    date_inscription = db.Column(db.DateTime, default=datetime.utcnow)
    date_completion = db.Column(db.DateTime)
    
    # Relations
    formation = db.relationship('Formation')
    auditeur = db.relationship('User', foreign_keys=[auditeur_id])
    
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=False)
    
    def __repr__(self):
        return f'<Inscription {self.auditeur_id} -> {self.formation_id}>'


class PlanDeveloppementIndividuel(db.Model):
    """Plan de développement individuel (PDI)"""
    __tablename__ = 'plans_developpement'
    
    id = db.Column(db.Integer, primary_key=True)
    reference = db.Column(db.String(20), unique=True, nullable=False)
    auditeur_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    annee = db.Column(db.Integer, nullable=False)
    
    # Objectifs
    objectifs_globaux = db.Column(db.Text)
    objectifs_smart = db.Column(db.Text)  # Spécifiques, Mesurables, Atteignables, Réalistes, Temporels
    
    # Actions
    actions_prevues = db.Column(db.Text)
    actions_realisees = db.Column(db.Text)
    
    # Compétences ciblées
    competences_cibles = db.Column(db.Text)  # IDs séparés par des virgules
    
    # Formations planifiées
    formations_prevues = db.Column(db.Text)  # IDs séparés par des virgules
    
    # Mentorat
    mentor_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    seances_mentorat = db.Column(db.Integer, default=0)
    
    # Suivi
    progression = db.Column(db.Integer, default=0)  # Pourcentage
    statut = db.Column(db.String(50), default='brouillon')  # brouillon, en_cours, termine, valide
    
    # Relecture et validation
    valide_par_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    date_validation = db.Column(db.DateTime)
    commentaire_validation = db.Column(db.Text)
    
    # Métadonnées
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    # Relations
    auditeur = db.relationship('User', foreign_keys=[auditeur_id])
    mentor = db.relationship('User', foreign_keys=[mentor_id])
    validateur = db.relationship('User', foreign_keys=[valide_par_id])
    createur = db.relationship('User', foreign_keys=[created_by])
    
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)
    
    def __repr__(self):
        return f'<PDI {self.reference} - {self.auditeur_id}>'
    
    def generer_reference(self):
        return f"PDI-{self.annee}-{self.auditeur_id:04d}"
    
    def calculer_progression(self):
        """Calculer la progression basée sur les actions réalisées"""
        if self.actions_prevues and self.actions_realisees:
            prevues = len(self.actions_prevues.split(','))
            realisees = len(self.actions_realisees.split(','))
            self.progression = round((realisees / prevues) * 100) if prevues > 0 else 0
        return self.progression


class FeedbackAuditeur(db.Model):
    """Feedback 360° pour les auditeurs"""
    __tablename__ = 'feedbacks_auditeurs'
    
    id = db.Column(db.Integer, primary_key=True)
    auditeur_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    evaluateur_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    mission_id = db.Column(db.Integer, db.ForeignKey('missions_audit.id'))
    
    # Catégories d'évaluation (1-5)
    qualite_travail = db.Column(db.Integer)
    respect_delais = db.Column(db.Integer)
    communication = db.Column(db.Integer)
    autonomie = db.Column(db.Integer)
    esprit_equipe = db.Column(db.Integer)
    rigueur = db.Column(db.Integer)
    
    # Commentaires
    points_forts = db.Column(db.Text)
    points_amelioration = db.Column(db.Text)
    commentaire_global = db.Column(db.Text)
    
    # Anonymat
    est_anonyme = db.Column(db.Boolean, default=True)
    
    # Dates
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    periode = db.Column(db.String(20))  # trimestre1, semestre1, annuel
    
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=False)
    
    def __repr__(self):
        return f'<Feedback {self.auditeur_id} par {self.evaluateur_id}>'
    
    def get_moyenne(self):
        notes = [self.qualite_travail, self.respect_delais, self.communication, 
                 self.autonomie, self.esprit_equipe, self.rigueur]
        notes_valides = [n for n in notes if n is not None]
        return round(sum(notes_valides) / len(notes_valides), 1) if notes_valides else 0


class PlanAction(db.Model):
    __tablename__ = 'plans_action'
    
    # ============================================
    # COLONNES DE BASE
    # ============================================
    id = db.Column(db.Integer, primary_key=True)
    reference = db.Column(db.String(50), nullable=False)  # ← Enlevé unique=True
    nom = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    date_debut = db.Column(db.Date)
    date_fin_prevue = db.Column(db.Date)
    date_fin_reelle = db.Column(db.Date)
    statut = db.Column(db.String(50), default='en_attente')
    pourcentage_realisation = db.Column(db.Integer, default=0)
    efficacite = db.Column(db.String(50))
    score_efficacite = db.Column(db.Integer)
    commentaire_evaluation = db.Column(db.Text)
    priorite = db.Column(db.String(20), default='moyenne')
    espace_travail_actif = db.Column(db.Boolean, default=True)
    
    # ============================================
    # RELATIONS AVEC AUTRES ENTITÉS
    # ============================================
    
    # Relation plusieurs-à-plusieurs avec les dispositifs
    dispositifs = db.relationship('DispositifMaitrise',
                                 secondary='plan_dispositifs',
                                 back_populates='plans_action',
                                 lazy='dynamic')
    
    # Ancienne relation dispositif_id (à conserver temporairement pour compatibilité)
    dispositif_id = db.Column(db.Integer, db.ForeignKey('dispositifs_maitrise.id'), nullable=True)
    dispositif = db.relationship('DispositifMaitrise', foreign_keys=[dispositif_id])
    
    # Relation avec le risque principal (optionnel, pour compatibilité)
    risque_id = db.Column(db.Integer, db.ForeignKey('risques.id'), nullable=True)
    risque = db.relationship('Risque', foreign_keys=[risque_id], backref='plans_action_principaux')
    
    # Relations avec les audits et recommandations
    audit_id = db.Column(db.Integer, db.ForeignKey('audits.id'), nullable=True)
    recommandation_id = db.Column(db.Integer, db.ForeignKey('recommandations.id'), nullable=True)
    constatations_ids = db.Column(db.String(500))
    
    # Relations utilisateurs
    responsable_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    # Relations de navigation
    audit = db.relationship('Audit', back_populates='plans_action')
    recommandation = db.relationship('Recommandation', back_populates='plan_action')
    responsable = db.relationship('User', foreign_keys=[responsable_id])
    createur = db.relationship('User', foreign_keys=[created_by])
    
    # Sous-actions
    sous_actions = db.relationship('SousAction', 
                                   backref='plan_action', 
                                   lazy=True, 
                                   cascade='all, delete-orphan',
                                   order_by='SousAction.created_at')
    
    # ============================================
    # COLONNES D'ARCHIVAGE
    # ============================================
    is_archived = db.Column(db.Boolean, default=False)
    archived_at = db.Column(db.DateTime)
    archived_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    archive_reason = db.Column(db.Text)
    statut_archive = db.Column(db.String(20), default='actif')
    
    # ============================================
    # TIMESTAMPS
    # ============================================
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # ============================================
    # MULTI-TENANT
    # ============================================
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)
    
    # Relations avec les utilisateurs d'archivage
    archive_user = db.relationship('User', foreign_keys=[archived_by])
    client = db.relationship('Client')
    audits = db.relationship('Audit',
                             secondary='plan_audits',
                             backref=db.backref('plans_action_multiples', lazy='dynamic'),
                             lazy='dynamic')
    
    # ===== CONTRAINTE UNIQUE COMPOSITE =====
    __table_args__ = (
        db.UniqueConstraint('reference', 'client_id', name='uix_planaction_reference_client'),
    )
    
    # ===== MÉTHODE STATIQUE DE GÉNÉRATION =====
    @staticmethod
    def generer_reference(client_id):
        """Génère une référence unique PAR CLIENT"""
        from datetime import datetime
        annee = datetime.now().year
        prefixe = f"PA-{annee}-"
        
        count = PlanAction.query.filter(
            PlanAction.reference.like(f'{prefixe}%'),
            PlanAction.client_id == client_id
        ).count()
        
        return f"{prefixe}{(count + 1):04d}"
    
    # ============================================
    # PROPRIÉTÉS CALCULÉES
    # ============================================
    
    @property
    def progression_reelle(self):
        """Calcule automatiquement la progression basée sur les sous-actions"""
        if not self.sous_actions:
            return self.pourcentage_realisation or 0
        
        sous_actions_actives = [sa for sa in self.sous_actions]
        
        if not sous_actions_actives:
            return 0
        
        total_progression = sum(sa.pourcentage_realisation or 0 for sa in sous_actions_actives)
        progression_calculee = round(total_progression / len(sous_actions_actives))
        
        if progression_calculee != self.pourcentage_realisation:
            self.pourcentage_realisation = progression_calculee
            try:
                db.session.commit()
            except:
                db.session.rollback()
        
        return progression_calculee

    @property
    def etapes(self):
        """Propriété pour compatibilité - retourne les sous-actions"""
        return self.sous_actions
    
    @property
    def ordre(self):
        """Propriété pour compatibilité - retourne l'ID comme ordre"""
        return self.id

    @property
    def tous_les_audits(self):
        """Retourne tous les audits liés à ce plan"""
        audits = list(self.audits)
        if self.audit and self.audit not in audits:
            audits.append(self.audit)
        return audits
    
    @property
    def source_info_complete(self):
        """Retourne les informations sur toutes les sources du plan"""
        from flask import url_for
        sources = []
        
        # Audits multiples
        for audit in self.audits:
            sources.append({
                'type': 'audit',
                'reference': audit.reference,
                'titre': audit.titre,
                'url': url_for('detail_audit', id=audit.id)
            })
        
        # Ancien audit simple (pour compatibilité)
        if self.audit and self.audit not in self.audits:
            sources.append({
                'type': 'audit_principal',
                'reference': self.audit.reference,
                'titre': self.audit.titre,
                'url': url_for('detail_audit', id=self.audit_id)
            })
        
        # Risque
        if self.risque:
            sources.append({
                'type': 'risque',
                'reference': self.risque.reference,
                'intitule': self.risque.intitule,
                'url': url_for('detail_risque', id=self.risque_id)
            })
        
        # Dispositifs
        for dispositif in self.dispositifs:
            sources.append({
                'type': 'dispositif',
                'reference': dispositif.reference,
                'intitule': dispositif.nom,
                'url': url_for('detail_dispositif', dispositif_id=dispositif.id)
            })
        
        return sources
    
    @property
    def risques_concernes(self):
        """Retourne la liste des risques concernés par ce plan via les dispositifs liés"""
        risques = set()
        for dispositif in self.dispositifs:
            if dispositif.risque:
                risques.add(dispositif.risque)
        return list(risques)
    
    @property
    def risque_principal(self):
        """Retourne le risque principal (pour compatibilité)"""
        if self.risque:
            return self.risque
        risques = self.risques_concernes
        return risques[0] if risques else None
    
    @property
    def get_etapes_ordonnees(self):
        """Retourne les étapes/sous-actions triées"""
        if self.sous_actions:
            from datetime import date
            return sorted(self.sous_actions, 
                         key=lambda x: (x.date_fin_prevue or date.max, x.created_at))
        return []
    
    @property
    def dispositifs_concernes(self):
        """Retourne la liste des dispositifs liés (pour compatibilité)"""
        return list(self.dispositifs)
    
    def get_progression_detaillee(self):
        """Calcule la progression détaillée"""
        if not self.sous_actions:
            return {
                'pourcentage': 0,
                'terminees': 0,
                'total': 0,
                'en_cours': 0,
                'a_faire': 0,
                'retardees': 0
            }
        
        total = len(self.sous_actions)
        terminees = len([sa for sa in self.sous_actions if sa.statut == 'termine'])
        en_cours = len([sa for sa in self.sous_actions if sa.statut == 'en_cours'])
        a_faire = len([sa for sa in self.sous_actions if sa.statut == 'a_faire'])
        retardees = len([sa for sa in self.sous_actions if sa.est_en_retard])
        
        return {
            'pourcentage': round((terminees / total) * 100) if total > 0 else 0,
            'terminees': terminees,
            'total': total,
            'en_cours': en_cours,
            'a_faire': a_faire,
            'retardees': retardees
        }
    
    @property
    def type_plan(self):
        """Détermine le type de plan (risque, dispositif, audit)"""
        if self.dispositifs.count() > 0:
            return 'dispositif'
        elif self.risque_id:
            return 'risque'
        elif self.audit_id:
            return 'audit'
        else:
            return 'autre'
    
    @property
    def source_info(self):
        """Retourne les informations sur la source du plan"""
        from flask import url_for
        
        if self.risque_id and self.risque:
            return {
                'type': 'risque',
                'reference': self.risque.reference,
                'intitule': self.risque.intitule,
                'url': url_for('detail_risque', id=self.risque_id)
            }
        elif self.audit_id and self.audit:
            return {
                'type': 'audit',
                'reference': self.audit.reference,
                'titre': self.audit.titre,
                'url': url_for('detail_audit', id=self.audit_id)
            }
        elif self.dispositifs.count() > 0:
            dispositif = self.dispositifs.first()
            return {
                'type': 'dispositif',
                'reference': dispositif.reference if dispositif else 'N/A',
                'intitule': dispositif.nom if dispositif else 'N/A',
                'url': url_for('detail_dispositif', dispositif_id=dispositif.id) if dispositif else '#'
            }
        return {'type': 'autre', 'reference': 'N/A'}
    
    @property
    def est_en_retard(self):
        """Vérifie si le plan est en retard"""
        if self.statut == 'termine':
            return False
        if not self.date_fin_prevue:
            return False
        return datetime.utcnow().date() > self.date_fin_prevue

    @property
    def couleur_priorite(self):
        """Retourne la couleur Bootstrap pour la priorité"""
        couleurs = {
            'faible': 'success',
            'moyenne': 'warning',
            'haute': 'danger',
            'critique': 'dark'
        }
        return couleurs.get(self.priorite, 'secondary')
    
    @property
    def couleur_statut(self):
        """Retourne la couleur Bootstrap en fonction du statut"""
        couleurs = {
            'en_attente': 'secondary',
            'en_cours': 'warning',
            'termine': 'success',
            'suspendu': 'info',
            'annule': 'danger'
        }
        return couleurs.get(self.statut, 'secondary')
    
    # ============================================
    # MÉTHODES D'ARCHIVAGE
    # ============================================
    
    def archiver(self, user_id, reason=None):
        """Archiver le plan"""
        self.is_archived = True
        self.statut_archive = 'archive'
        self.archived_at = datetime.utcnow()
        self.archived_by = user_id
        if reason:
            self.archive_reason = reason
        self.updated_at = datetime.utcnow()
        
    def desarchiver(self):
        """Désarchiver le plan"""
        self.is_archived = False
        self.statut_archive = 'actif'
        self.archived_at = None
        self.archived_by = None
        self.archive_reason = None
        self.updated_at = datetime.utcnow()
    
    # ============================================
    # MÉTHODES DE SÉRIALISATION
    # ============================================
    
    def to_dict(self):
        """Convertit l'objet PlanAction en dictionnaire pour la sérialisation JSON"""
        return {
            'id': self.id,
            'reference': self.reference,
            'nom': self.nom,
            'description': self.description,
            'date_debut': self.date_debut.isoformat() if self.date_debut else None,
            'date_fin_prevue': self.date_fin_prevue.isoformat() if self.date_fin_prevue else None,
            'date_fin_reelle': self.date_fin_reelle.isoformat() if self.date_fin_reelle else None,
            'statut': self.statut,
            'pourcentage_realisation': self.pourcentage_realisation,
            'priorite': self.priorite,
            'client_id': self.client_id,
            'progression_reelle': self.progression_reelle,
            'est_en_retard': self.est_en_retard,
            'couleur_statut': self.couleur_statut,
            'couleur_priorite': self.couleur_priorite,
            'is_archived': self.is_archived,
            'statut_archive': self.statut_archive,
            'archived_at': self.archived_at.isoformat() if self.archived_at else None,
            'archived_by': self.archived_by,
            'archive_reason': self.archive_reason,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'type_plan': self.type_plan,
            'dispositifs_count': self.dispositifs.count(),
            'sous_actions_count': len(self.sous_actions),
            'risques_concernes': [{
                'id': r.id,
                'reference': r.reference,
                'intitule': r.intitule
            } for r in self.risques_concernes]
        }
    
    def to_dict_simple(self):
        """Version simplifiée pour les listes"""
        return {
            'id': self.id,
            'reference': self.reference,
            'nom': self.nom,
            'statut': self.statut,
            'pourcentage_realisation': self.pourcentage_realisation,
            'priorite': self.priorite,
            'date_fin_prevue': self.date_fin_prevue.isoformat() if self.date_fin_prevue else None,
            'est_en_retard': self.est_en_retard,
            'dispositifs_count': self.dispositifs.count()
        }
    
    def __repr__(self):
        return f'<PlanAction {self.reference}: {self.nom}>'


# ============================================
# TABLE D'ASSOCIATION PLAN-DISPOSITIF
# ============================================
plan_dispositifs = db.Table('plan_dispositifs',
    db.Column('plan_id', db.Integer, db.ForeignKey('plans_action.id'), primary_key=True),
    db.Column('dispositif_id', db.Integer, db.ForeignKey('dispositifs_maitrise.id'), primary_key=True),
    db.Column('created_at', db.DateTime, default=datetime.utcnow),
    db.Column('created_by', db.Integer, db.ForeignKey('user.id'))
)




# ============================================
# ÉTAPE PLAN ACTION (pour compatibilité)
# ============================================
class EtapePlanAction(db.Model):
    __tablename__ = 'etapes_plan_action'
    
    id = db.Column(db.Integer, primary_key=True)
    plan_action_id = db.Column(db.Integer, db.ForeignKey('plans_action.id'), nullable=False)
    ordre = db.Column(db.Integer, nullable=False)
    description = db.Column(db.Text, nullable=False)
    date_echeance = db.Column(db.Date)
    statut = db.Column(db.String(50), default='a_faire')
    responsable_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    responsable = db.relationship('User', foreign_keys=[responsable_id])
    
    @property
    def couleur_statut(self):
        """Couleur Bootstrap pour le statut"""
        couleurs = {
            'a_faire': 'secondary',
            'en_cours': 'warning',
            'termine': 'success',
            'retarde': 'danger'
        }
        return couleurs.get(self.statut, 'light')

# -------------------- SOUS ACTION - CORRIGÉ --------------------
class SousAction(db.Model):
    __tablename__ = 'sous_actions'
    
    id = db.Column(db.Integer, primary_key=True)
    plan_action_id = db.Column(db.Integer, db.ForeignKey('plans_action.id'), nullable=False)  # 'plans_action.id'
    reference = db.Column(db.String(50))
    description = db.Column(db.Text, nullable=False)
    date_debut = db.Column(db.Date)
    date_fin_prevue = db.Column(db.Date)
    date_fin_reelle = db.Column(db.Date)
    pourcentage_realisation = db.Column(db.Integer, default=0)
    statut = db.Column(db.String(50), default='a_faire')
    responsable_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)
    
    responsable = db.relationship('User')
    
    @property
    def est_en_retard(self):
        """Vérifie si la sous-action est en retard"""
        if not self.date_fin_prevue or self.statut == 'termine':
            return False
        return datetime.utcnow().date() > self.date_fin_prevue
    
    @property
    def couleur_statut(self):
        """Couleur Bootstrap pour le statut"""
        couleurs = {
            'a_faire': 'secondary',
            'en_cours': 'warning',
            'termine': 'success',
            'retarde': 'danger'
        }
        return couleurs.get(self.statut, 'light')

    @property
    def commentaires_recentes(self):
        """Retourne les commentaires spécifiques à cette sous-action"""
        return sorted(self.commentaires, key=lambda x: x.created_at, reverse=True)[:10]
    
    def terminer(self):
        """Termine la sous-action"""
        self.statut = 'termine'
        self.pourcentage_realisation = 100
        self.date_fin_reelle = datetime.utcnow().date()
        self.updated_at = datetime.utcnow()



# -------------------- MATRICE MATURITE - CORRIGÉ --------------------
class MatriceMaturite(db.Model):
    __tablename__ = 'matrices_maturite'
    
    id = db.Column(db.Integer, primary_key=True)
    audit_id = db.Column(db.Integer, db.ForeignKey('audits.id'), nullable=False)  # 'audits.id'
    exigence = db.Column(db.String(200), nullable=False)
    niveau_conformite = db.Column(db.String(50))  # conforme, partiellement_conforme, non_conforme, non_applicable
    commentaire = db.Column(db.Text)
    risques_associes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)
    
    audit = db.relationship('Audit', backref='matrices_maturite')
    
    @property
    def couleur_niveau(self):
        """Couleur Bootstrap pour le niveau de conformité"""
        couleurs = {
            'conforme': 'success',
            'partiellement_conforme': 'warning',
            'non_conforme': 'danger',
            'non_applicable': 'info'
        }
        return couleurs.get(self.niveau_conformite, 'secondary')

# -------------------- JOURNAL AUDIT - CORRIGÉ --------------------
class JournalAudit(db.Model):
    __tablename__ = 'journaux_audit'
    
    id = db.Column(db.Integer, primary_key=True)
    audit_id = db.Column(db.Integer, db.ForeignKey('audits.id', ondelete='CASCADE'), nullable=False)  # AJOUT: ondelete='CASCADE'
    action = db.Column(db.String(100), nullable=False)
    details = db.Column(db.JSON)
    utilisateur_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    signature = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)
    
    # Relations - AJOUTER cascade
    audit = db.relationship('Audit', backref=db.backref('journal_entries', cascade='all, delete-orphan'))
    utilisateur = db.relationship('User')
    client = db.relationship('Client')
    
    @property
    def get_action_display(self):
        """Retourne l'action formatée"""
        actions = {
            'creation_constat': 'Création de constatation',
            'modification_reco': 'Modification de recommandation',
            'upload_fichier': 'Upload de fichier',
            'retard_plan': 'Retard de plan',
            'validation': 'Validation',
            'changement_statut': 'Changement de statut',
            'ajout_membre': 'Ajout de membre',
            'suppression_membre': 'Suppression de membre'
        }
        return actions.get(self.action, self.action)
    
    def creer_entree(self, audit_id, action, details, utilisateur_id):
        """Crée une entrée dans le journal"""
        self.audit_id = audit_id
        self.action = action
        self.details = details
        self.utilisateur_id = utilisateur_id
        self.created_at = datetime.utcnow()


# -------------------- HISTORIQUE MODIFICATION --------------------
class HistoriqueModification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    entite_type = db.Column(db.String(50))
    entite_id = db.Column(db.Integer)
    utilisateur_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    modifications = db.Column(db.JSON)
    date_modification = db.Column(db.DateTime, default=datetime.utcnow)
    
    utilisateur = db.relationship('User')

# -------------------- ALERTE --------------------
class Alerte(db.Model):
    __tablename__ = 'alertes'
    
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(50))
    gravite = db.Column(db.String(20))
    titre = db.Column(db.String(200))
    description = db.Column(db.Text)
    entite_type = db.Column(db.String(50))
    entite_id = db.Column(db.Integer)
    est_lue = db.Column(db.Boolean, default=False)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)
    
    createur = db.relationship('User', backref='alertes_crees')

# ==================== MODÈLES POUR ORGANIGRAMME FLUIDE ====================

class ZoneRisqueOrganigramme(db.Model):
    """Zones de risque positionnées sur l'organigramme"""
    id = db.Column(db.Integer, primary_key=True)
    processus_id = db.Column(db.Integer, db.ForeignKey('processus.id'))
    nom = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    type_risque = db.Column(db.String(100))
    niveau_risque = db.Column(db.String(20), default='moyen')
    couleur = db.Column(db.String(20), default='#ffeb3b')
    etapes_associees = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)

    processus = db.relationship('Processus', backref='zones_risque_organigramme')

class PointDecision(db.Model):
    """Points de décision (losanges) pour les embranchements"""
    id = db.Column(db.Integer, primary_key=True)
    processus_id = db.Column(db.Integer, db.ForeignKey('processus.id'))
    etape_id = db.Column(db.Integer, db.ForeignKey('etape_processus.id'))
    question = db.Column(db.String(300), nullable=False)
    position_x = db.Column(db.Integer, default=0)
    position_y = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    processus = db.relationship('Processus', backref='points_decision')
    etape = db.relationship('EtapeProcessus', backref='points_decision')

# -------------------- MODÈLES AUDIT COMPLÉMENTAIRES --------------------

class LigneOrganisation(db.Model):
    __tablename__ = 'ligne_organisation'
    
    id = db.Column(db.Integer, primary_key=True)
    processus_id = db.Column(db.Integer, db.ForeignKey('processus.id'), nullable=False)
    type_ligne = db.Column(db.String(20), nullable=False)
    position_x = db.Column(db.Integer, default=0)
    position_y = db.Column(db.Integer, default=0)
    couleur = db.Column(db.String(7), default='#6c757d')
    epaisseur = db.Column(db.Integer, default=2)
    style = db.Column(db.String(20), default='solid')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)
    
    processus = db.relationship('Processus', backref=db.backref('lignes_organisation', lazy=True, cascade='all, delete-orphan'))

class TitreOrganisation(db.Model):
    __tablename__ = 'titre_organisation'
    
    id = db.Column(db.Integer, primary_key=True)
    processus_id = db.Column(db.Integer, db.ForeignKey('processus.id'), nullable=False)
    texte = db.Column(db.String(200), nullable=False)
    position_x = db.Column(db.Integer, default=0)
    position_y = db.Column(db.Integer, default=0)
    taille_police = db.Column(db.Integer, default=20)
    couleur = db.Column(db.String(7), default='#000000')
    gras = db.Column(db.Boolean, default=False)
    italique = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)
    
    processus = db.relationship('Processus', backref=db.backref('titres_organisation', lazy=True, cascade='all, delete-orphan'))

# -------------------- CONFIGURATIONS AUDIT --------------------

class ConfigurationAudit(db.Model):
    """Configuration des paramètres d'audit"""
    __tablename__ = 'configurations_audit'
    
    id = db.Column(db.Integer, primary_key=True)
    nom_config = db.Column(db.String(100), nullable=False, unique=True)
    type_audit = db.Column(db.String(50), nullable=False)
    duree_standard = db.Column(db.Integer, default=30)
    seuil_gravite_min = db.Column(db.Integer, default=3)
    seuil_gravite_max = db.Column(db.Integer, default=5)
    categories_audit = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)

    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class TemplateConstatation(db.Model):
    """Templates de constatations prédéfinies"""
    __tablename__ = 'templates_constatations'
    
    id = db.Column(db.Integer, primary_key=True)
    reference = db.Column(db.String(50), nullable=False)
    titre = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    type_constatation = db.Column(db.String(50), nullable=False)
    gravite_defaut = db.Column(db.String(20), default='moyenne')
    processus_concerne = db.Column(db.String(200))
    cause_racine_typique = db.Column(db.Text)
    recommandation_standard = db.Column(db.Text)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)
    est_actif = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class TemplateRecommandation(db.Model):
    """Templates de recommandations prédéfinies"""
    __tablename__ = 'templates_recommandations'
    
    id = db.Column(db.Integer, primary_key=True)
    reference = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text, nullable=False)
    type_recommandation = db.Column(db.String(50), nullable=False)
    delai_mise_en_oeuvre_standard = db.Column(db.String(50))
    responsable_type = db.Column(db.String(50))
    est_actif = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)

class ElementLogigramme(db.Model):
    __tablename__ = 'element_logigramme'
    id = db.Column(db.Integer, primary_key=True)
    activite_id = db.Column(db.Integer, db.ForeignKey('processus_activite.id'))
    type_element = db.Column(db.String(50))  # 'debut', 'fin', 'action', 'controle', 'risque', 'organisation'
    libelle = db.Column(db.String(200))
    description = db.Column(db.Text)
    position_x = db.Column(db.Integer)
    position_y = db.Column(db.Integer)
    
    # AJOUTEZ CES CHAMPS :
    width = db.Column(db.Integer, default=120)
    height = db.Column(db.Integer, default=60)
    couleur = db.Column(db.String(20), default='#007bff')
    
    style = db.Column(db.JSON)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relations
    processus_activite = db.relationship('ProcessusActivite', back_populates='elements')
    
class LienLogigramme(db.Model):
    __tablename__ = 'lien_logigramme'
    id = db.Column(db.Integer, primary_key=True)
    activite_id = db.Column(db.Integer, db.ForeignKey('processus_activite.id'))
    element_source_id = db.Column(db.Integer, db.ForeignKey('element_logigramme.id'))
    element_cible_id = db.Column(db.Integer, db.ForeignKey('element_logigramme.id'))
    libelle = db.Column(db.String(200))
    
    # AJOUTEZ CES CHAMPS SI NÉCESSAIRE :
    type_lien = db.Column(db.String(50), default='sequence')
    label = db.Column(db.String(100))
    points = db.Column(db.JSON)  # Pour stocker les points de la ligne
    
    style = db.Column(db.JSON)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relations
    processus_activite = db.relationship('ProcessusActivite', back_populates='liens')
    element_source = db.relationship('ElementLogigramme', foreign_keys=[element_source_id], backref='liens_sortants')
    element_cible = db.relationship('ElementLogigramme', foreign_keys=[element_cible_id], backref='liens_entrants')

    
class ProcessusActivite(db.Model):
    __tablename__ = 'processus_activite'
    
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    direction_id = db.Column(db.Integer, db.ForeignKey('direction.id'))
    service_id = db.Column(db.Integer, db.ForeignKey('service.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    is_archived = db.Column(db.Boolean, default=False)
    archived_at = db.Column(db.DateTime)
    # ⚠️ TEMPORAIREMENT: COMMENTEZ CETTE LIGNE ⚠️
    # archived_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)
    
    # Relations
    direction = db.relationship('Direction', backref='processus_activites')
    service = db.relationship('Service', backref='processus_activites')
    createur = db.relationship('User', foreign_keys=[created_by], backref='processus_activites_crees')
    # ⚠️ TEMPORAIREMENT: COMMENTEZ CETTE LIGNE AUSSI ⚠️
    # archiveur = db.relationship('User', foreign_keys=[archived_by], backref='processus_activites_archives')
    
    # CORRECTION: Utilisez les bons noms de classe
    elements = db.relationship('ElementLogigramme', back_populates='processus_activite', lazy=True, cascade='all, delete-orphan')
    liens = db.relationship('LienLogigramme', back_populates='processus_activite', lazy=True, cascade='all, delete-orphan')

    def archiver(self, user_id):
        self.is_archived = True
        self.archived_at = datetime.utcnow()
        # self.archived_by = user_id  # Commenté temporairement
        self.updated_at = datetime.utcnow()
    
    def restaurer(self):
        """Méthode pour restaurer un logigramme archivé"""
        self.is_archived = False
        self.archived_at = None
        # self.archived_by = None  # Commenté temporairement
        self.updated_at = datetime.utcnow()

    def to_dict(self):
        return {
            'id': self.id,
            'nom': self.nom,
            'description': self.description,
            'direction_id': self.direction_id,
            'service_id': self.service_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'created_by': self.created_by,
            'is_archived': self.is_archived,
            'archived_at': self.archived_at.isoformat() if self.archived_at else None,
            # ⚠️ TEMPORAIREMENT: COMMENTEZ CETTE LIGNE ⚠️
            # 'archived_by': self.archived_by,
            'direction': self.direction.nom if self.direction else None,
            'service': self.service.nom if self.service else None
        }
    
class ParametreEvaluation(db.Model):
    """Stocke les paramètres d'évaluation"""
    __tablename__ = 'parametre_evaluation'
    
    id = db.Column(db.Integer, primary_key=True)
    categorie = db.Column(db.String(50), nullable=False)  # 'impact', 'probabilite', 'maitrise'
    niveau = db.Column(db.Integer, nullable=False)  # 1 à 5
    nom_court = db.Column(db.String(50), nullable=False)  # 'Négligeable', 'Mineur', etc.
    description_longue = db.Column(db.Text)  # Description détaillée
    couleur_hex = db.Column(db.String(7), default='#28a745')  # Code couleur hex
    ordre = db.Column(db.Integer, default=1)
    est_actif = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)
    
    __table_args__ = (
        db.UniqueConstraint('categorie', 'niveau', name='u_categorie_niveau'),
    )
    
    def __repr__(self):
        return f'<ParametreEvaluation {self.categorie} niveau {self.niveau}>'


class GuideEvaluation(db.Model):  # <-- Changez models.Model par db.Model
    """Stocke le contenu du guide d'évaluation"""
    __tablename__ = 'guide_evaluation'
    
    id = db.Column(db.Integer, primary_key=True)
    section = db.Column(db.String(100), nullable=False)  # 'phase1', 'phase2', 'phase3', 'matrice', 'conseils'
    titre = db.Column(db.String(200))
    contenu = db.Column(db.Text)
    ordre = db.Column(db.Integer, default=1)
    est_actif = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)
    
    def __repr__(self):
        return f'<GuideEvaluation {self.section}>'


# Modèle pour le journal d'activité
class JournalActivite(db.Model):
    """Modèle pour journaliser les activités des utilisateurs"""
    __tablename__ = 'journal_activite'
    
    id = db.Column(db.Integer, primary_key=True)
    utilisateur_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    action = db.Column(db.String(100), nullable=False)
    details = db.Column(db.Text)  # Renommez 'description' en 'details'
    entite_type = db.Column(db.String(50))
    entite_id = db.Column(db.Integer)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.Text)
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)
    
    # Relation
    utilisateur = db.relationship('User', back_populates='activites',
                                 foreign_keys=[utilisateur_id])
    
    def __repr__(self):
        return f'<JournalActivite {self.action} par utilisateur {self.utilisateur_id}>'


class PermissionTemplate(db.Model):
    __tablename__ = 'permission_templates'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.Text)
    permissions = db.Column(db.JSON, nullable=False)
    role = db.Column(db.String(20), default='utilisateur')
    is_default = db.Column(db.Boolean, default=False)
    client_id = db.Column(db.Integer, nullable=True)  # ✅ Nullable pour SQLite
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# Modèle pour les logs système
class SystemLog(db.Model):
    """Modèle pour les logs système"""
    __tablename__ = 'system_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    level = db.Column(db.String(20))  # 'info', 'warning', 'error', 'critical'
    module = db.Column(db.String(50))
    message = db.Column(db.Text)
    details = db.Column(db.JSON)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)
    ip_address = db.Column(db.String(45))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<SystemLog {self.level} - {self.module}>'


# Modèle pour les sessions utilisateur
class UserSession(db.Model):
    """Modèle pour suivre les sessions utilisateur"""
    __tablename__ = 'user_sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    session_id = db.Column(db.String(100))
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.Text)
    login_time = db.Column(db.DateTime, default=datetime.utcnow)
    logout_time = db.Column(db.DateTime)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)

    is_active = db.Column(db.Boolean, default=True)
    
    # Relation
    user = db.relationship('User')
    
    def __repr__(self):
        return f'<UserSession {self.user_id} - {self.session_id}>'

# -------------------- CONFIGURATION DES CHAMPS DE RISQUE --------------------
class ConfigurationChampRisque(db.Model):
    __tablename__ = 'configuration_champs_risque'
    
    id = db.Column(db.Integer, primary_key=True)
    nom_technique = db.Column(db.String(100), unique=True, nullable=False)
    nom_affichage = db.Column(db.String(200), nullable=False)
    type_champ = db.Column(db.String(50), nullable=False)
    est_obligatoire = db.Column(db.Boolean, default=False)
    est_actif = db.Column(db.Boolean, default=True)
    ordre_affichage = db.Column(db.Integer, default=0)
    section = db.Column(db.String(50), default='general')
    aide_texte = db.Column(db.Text)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)

    valeurs_possibles = db.Column(db.JSON)
    regex_validation = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relation pour voir l'utilisation
    champs_personnalises = db.relationship('ChampPersonnaliseRisque', 
                                          backref='configuration', 
                                          lazy=True,
                                          foreign_keys='ChampPersonnaliseRisque.nom_technique',
                                          primaryjoin='ConfigurationChampRisque.nom_technique==ChampPersonnaliseRisque.nom_technique')
    
    def __repr__(self):
        return f'<ConfigurationChampRisque {self.nom_technique} ({self.nom_affichage})>'
    
    def to_dict(self):
        """Convertit l'objet en dictionnaire pour JSON"""
        return {
            'id': self.id,
            'nom_technique': self.nom_technique,
            'nom_affichage': self.nom_affichage,
            'type_champ': self.type_champ,
            'est_obligatoire': self.est_obligatoire,
            'est_actif': self.est_actif,
            'ordre_affichage': self.ordre_affichage,
            'section': self.section,
            'aide_texte': self.aide_texte,
            'valeurs_possibles': self.valeurs_possibles,
            'regex_validation': self.regex_validation,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    @property
    def is_select_type(self):
        """Retourne True si le champ est de type liste déroulante ou multiple"""
        return self.type_champ in ['select', 'multiselect', 'radio']
    
    @property
    def is_text_type(self):
        """Retourne True si le champ est de type texte"""
        return self.type_champ in ['texte', 'textarea']
    
    def get_valeurs_possibles_list(self):
        """Retourne les valeurs possibles sous forme de liste"""
        if not self.valeurs_possibles:
            return []
        
        if isinstance(self.valeurs_possibles, list):
            return self.valeurs_possibles
        
        if isinstance(self.valeurs_possibles, dict):
            # Si c'est un dict avec format {valeur: label}, retourner les valeurs
            return list(self.valeurs_possibles.keys())
        
        # Si c'est une chaîne, essayer de la parser
        try:
            import json
            parsed = json.loads(self.valeurs_possibles)
            if isinstance(parsed, list):
                return parsed
            elif isinstance(parsed, dict):
                return list(parsed.keys())
        except:
            pass
        
        return []
    
    def get_valeurs_possibles_dict(self):
        """Retourne les valeurs possibles sous forme de dictionnaire {valeur: label}"""
        if not self.valeurs_possibles:
            return {}
        
        if isinstance(self.valeurs_possibles, dict):
            return self.valeurs_possibles
        
        if isinstance(self.valeurs_possibles, list):
            # Convertir la liste en dict avec les mêmes valeurs pour clés et labels
            return {item: item for item in self.valeurs_possibles}
        
        # Si c'est une chaîne, essayer de la parser
        try:
            import json
            parsed = json.loads(self.valeurs_possibles)
            if isinstance(parsed, dict):
                return parsed
            elif isinstance(parsed, list):
                return {item: item for item in parsed}
        except:
            pass
        
        return {}
    
    @classmethod
    def get_champs_actifs(cls):
        """Retourne tous les champs actifs triés par ordre d'affichage"""
        return cls.query.filter_by(est_actif=True)\
                        .order_by(cls.ordre_affichage, cls.nom_affichage)\
                        .all()
    
    @classmethod
    def get_champs_par_section(cls):
        """Retourne les champs actifs groupés par section"""
        champs = cls.get_champs_actifs()
        result = {}
        for champ in champs:
            section = champ.section or 'general'
            if section not in result:
                result[section] = []
            result[section].append(champ)
        return result

    
# -------------------- CONFIGURATION DES LISTES DÉROULANTES --------------------
class ConfigurationListeDeroulante(db.Model):
    __tablename__ = 'configuration_listes_deroulantes'
    
    id = db.Column(db.Integer, primary_key=True)
    nom_technique = db.Column(db.String(100), unique=True, nullable=False)  # Ex: 'categories_risque', 'types_risque'
    nom_affichage = db.Column(db.String(200), nullable=False)  # Ex: 'Catégories de risque', 'Types de risque'
    est_multiple = db.Column(db.Boolean, default=False)  # Sélection multiple ou non
    valeurs = db.Column(db.JSON, nullable=False)  # Liste des valeurs [{'valeur': 'x', 'label': 'X'}]
    valeurs_par_defaut = db.Column(db.JSON)  # Valeurs sélectionnées par défaut
    est_actif = db.Column(db.Boolean, default=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<ConfigurationListe {self.nom_technique}>'


# -------------------- CHAMPS PERSONNALISÉS DE RISQUE --------------------
class ChampPersonnaliseRisque(db.Model):
    __tablename__ = 'champs_personnalises_risque'
    
    id = db.Column(db.Integer, primary_key=True)
    risque_id = db.Column(db.Integer, db.ForeignKey('risques.id'), nullable=False)
    nom_technique = db.Column(db.String(100), nullable=False)
    type_valeur = db.Column(db.String(20), nullable=False)  # 'string', 'integer', 'boolean', 'date', 'json'
    valeur_string = db.Column(db.Text)
    valeur_integer = db.Column(db.Integer)
    valeur_boolean = db.Column(db.Boolean)
    valeur_date = db.Column(db.DateTime)
    valeur_json = db.Column(db.JSON)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relation
    risque = db.relationship('Risque', backref=db.backref('champs_personnalises', lazy=True))
    
    def get_valeur(self):
        """Retourne la valeur selon le type"""
        if self.type_valeur == 'string':
            return self.valeur_string
        elif self.type_valeur == 'integer':
            return self.valeur_integer
        elif self.type_valeur == 'boolean':
            return self.valeur_boolean
        elif self.type_valeur == 'date':
            return self.valeur_date
        elif self.type_valeur == 'json':
            return self.valeur_json
        return None
    
    def set_valeur(self, valeur):
        """Définit la valeur selon le type"""
        if isinstance(valeur, str):
            self.type_valeur = 'string'
            self.valeur_string = valeur
        elif isinstance(valeur, int):
            self.type_valeur = 'integer'
            self.valeur_integer = valeur
        elif isinstance(valeur, bool):
            self.type_valeur = 'boolean'
            self.valeur_boolean = valeur
        elif isinstance(valeur, datetime):
            self.type_valeur = 'date'
            self.valeur_date = valeur
        elif isinstance(valeur, (dict, list)):
            self.type_valeur = 'json'
            self.valeur_json = valeur
        else:
            self.type_valeur = 'string'
            self.valeur_string = str(valeur)


# -------------------- FICHIER RISQUE --------------------
class FichierRisque(db.Model):
    __tablename__ = 'fichiers_risque'
    
    id = db.Column(db.Integer, primary_key=True)
    risque_id = db.Column(db.Integer, db.ForeignKey('risques.id'), nullable=False)
    nom_fichier = db.Column(db.String(255), nullable=False)
    chemin_fichier = db.Column(db.String(500), nullable=False)
    type_fichier = db.Column(db.String(100))
    taille = db.Column(db.Integer)  # En octets
    categorie = db.Column(db.String(100))  # 'document', 'image', 'analyse', 'autre'
    description = db.Column(db.Text)
    uploaded_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)
    
    # Relations
    risque = db.relationship('Risque', backref=db.backref('fichiers', lazy=True))
    uploader = db.relationship('User', foreign_keys=[uploaded_by])
    
    def __repr__(self):
        return f'<FichierRisque {self.nom_fichier}>'

class FichierKRI(db.Model):
    __tablename__ = 'fichier_kri'
    
    id = db.Column(db.Integer, primary_key=True)
    kri_id = db.Column(db.Integer, db.ForeignKey('kri.id'))
    nom_fichier = db.Column(db.String(255), nullable=False)
    chemin_fichier = db.Column(db.String(500), nullable=False)
    type_fichier = db.Column(db.String(100))
    taille = db.Column(db.Integer)  # Taille en octets
    categorie = db.Column(db.String(50), default='document')
    description = db.Column(db.Text)
    uploaded_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)
    
    # Relations
    kri = db.relationship('KRI', backref=db.backref('fichiers', lazy=True))
    uploader = db.relationship('User', foreign_keys=[uploaded_by])
    
# ========================
# MODÈLES QUESTIONNAIRE (à ajouter à la fin de models.py)
# ========================

class Questionnaire(db.Model):
    __tablename__ = 'questionnaire'
    
    id = db.Column(db.Integer, primary_key=True)
    titre = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    code = db.Column(db.String(50), unique=True, nullable=False)
    instructions = db.Column(db.Text)
    est_actif = db.Column(db.Boolean, default=True)
    est_public = db.Column(db.Boolean, default=False)
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)
    date_modification = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    date_debut = db.Column(db.DateTime)
    date_fin = db.Column(db.DateTime)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)

    temps_estime = db.Column(db.Integer)  # en minutes
    redirection_url = db.Column(db.String(500))
    
    # Configuration
    autoriser_sauvegarde_partielle = db.Column(db.Boolean, default=True)
    afficher_barre_progression = db.Column(db.Boolean, default=True)
    afficher_numero_questions = db.Column(db.Boolean, default=True)
    randomiser_questions = db.Column(db.Boolean, default=False)
    randomiser_options = db.Column(db.Boolean, default=False)
    limit_une_reponse = db.Column(db.Boolean, default=False)
    collecter_email = db.Column(db.Boolean, default=False)
    collecter_nom = db.Column(db.Boolean, default=False)
    notification_email = db.Column(db.Boolean, default=False)
    email_notification = db.Column(db.String(255))
    confirmation_message = db.Column(db.Text)
    
    # Relations
    categories = db.relationship('QuestionnaireCategorie', back_populates='questionnaire', 
                               cascade='all, delete-orphan', lazy=True, order_by='QuestionnaireCategorie.ordre')
    reponses = db.relationship('ReponseQuestionnaire', back_populates='questionnaire', 
                              cascade='all, delete-orphan', lazy=True)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    createur = db.relationship('User', foreign_keys=[created_by], backref='questionnaires_crees')
    
    def generer_lien_public(self):
        """Génère un lien public unique pour le questionnaire"""
        return f"/questionnaires/{self.code}/repondre"
    
    def get_stats(self):
        """Retourne les statistiques du questionnaire"""
        total_reponses = len(self.reponses)
        reponses_completes = sum(1 for r in self.reponses if r.statut == 'complet')
        
        return {
            'total_reponses': total_reponses,
            'reponses_completes': reponses_completes,
            'taux_completion': (reponses_completes / total_reponses * 100) if total_reponses > 0 else 0
        }
    
    def __repr__(self):
        return f'<Questionnaire {self.titre}>'


class QuestionnaireCategorie(db.Model):
    __tablename__ = 'questionnaire_categorie'
    
    id = db.Column(db.Integer, primary_key=True)
    questionnaire_id = db.Column(db.Integer, db.ForeignKey('questionnaire.id', ondelete='CASCADE'), nullable=False)
    titre = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)

    ordre = db.Column(db.Integer, default=0)
    
    # Relations
    questionnaire = db.relationship('Questionnaire', back_populates='categories')
    questions = db.relationship('Question', back_populates='categorie', 
                              cascade='all, delete-orphan', lazy=True, order_by='Question.ordre')
    
    def __repr__(self):
        return f'<Categorie {self.titre}>'

class Question(db.Model):
    __tablename__ = 'question'
    
    TYPES = {
        'text': 'Texte court',
        'textarea': 'Texte long',
        'radio': 'Choix unique',
        'checkbox': 'Choix multiple',
        'select': 'Liste déroulante',
        'date': 'Date',
        'email': 'Email',
        'number': 'Nombre',
        'range': 'Échelle',
        'matrix': 'Matrice',
        'file': 'Fichier',
        'rating': 'Évaluation',
        'yesno': 'Oui/Non'
    }
    
    id = db.Column(db.Integer, primary_key=True)
    categorie_id = db.Column(db.Integer, db.ForeignKey('questionnaire_categorie.id', ondelete='CASCADE'), nullable=False)
    texte = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text)
    type = db.Column(db.String(20), nullable=False, default='text')
    ordre = db.Column(db.Integer, default=0)
    est_obligatoire = db.Column(db.Boolean, default=False)
    validation_regex = db.Column(db.String(500))
    message_validation = db.Column(db.String(500))
    placeholder = db.Column(db.String(200))
    taille_min = db.Column(db.Integer)
    taille_max = db.Column(db.Integer)
    valeurs_min = db.Column(db.Float)
    valeurs_max = db.Column(db.Float)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)

    pas = db.Column(db.Float)
    unite = db.Column(db.String(50))
    
    # Pour les questions de type évaluation
    echelle_min = db.Column(db.Integer, default=1)
    echelle_max = db.Column(db.Integer, default=5)
    libelle_min = db.Column(db.String(100))
    libelle_max = db.Column(db.String(100))
    
    # Relations
    categorie = db.relationship('QuestionnaireCategorie', back_populates='questions')
    options = db.relationship('OptionQuestion', back_populates='question', 
                            cascade='all, delete-orphan', lazy=True, order_by='OptionQuestion.ordre')
    reponses = db.relationship('ReponseQuestion', back_populates='question', 
                              cascade='all, delete-orphan', lazy=True)
    conditions = db.relationship('ConditionQuestion', 
                                foreign_keys='ConditionQuestion.question_id',
                                back_populates='question',
                                cascade='all, delete-orphan', lazy=True)
    
    def get_type_display(self):
        return self.TYPES.get(self.type, self.type)
    
    def __repr__(self):
        return f'<Question {self.texte[:50]}...>'

    
class OptionQuestion(db.Model):
    __tablename__ = 'option_question'
    
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id', ondelete='CASCADE'), nullable=False)
    valeur = db.Column(db.String(500), nullable=False)
    texte = db.Column(db.String(500), nullable=False)
    ordre = db.Column(db.Integer, default=0)
    score = db.Column(db.Float)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)

    est_autre = db.Column(db.Boolean, default=False)
    
    # Relation
    question = db.relationship('Question', back_populates='options')
    
    def __repr__(self):
        return f'<Option {self.texte}>'


class ConditionQuestion(db.Model):
    __tablename__ = 'condition_question'
    
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id', ondelete='CASCADE'), nullable=False)
    question_parent_id = db.Column(db.Integer, db.ForeignKey('question.id', ondelete='CASCADE'), nullable=False)
    operateur = db.Column(db.String(20), nullable=False)  # equals, not_equals, contains, greater_than, etc.
    valeur = db.Column(db.String(500), nullable=False)
    
    # Relations avec foreign_keys explicitement spécifiées
    question = db.relationship('Question', foreign_keys=[question_id], 
                               back_populates='conditions')
    question_parent = db.relationship('Question', foreign_keys=[question_parent_id])
    
    def __repr__(self):
        return f'<Condition {self.operateur} {self.valeur}>'

class ReponseQuestionnaire(db.Model):
    __tablename__ = 'reponse_questionnaire'
    
    id = db.Column(db.Integer, primary_key=True)
    questionnaire_id = db.Column(db.Integer, db.ForeignKey('questionnaire.id'), nullable=False)
    session_id = db.Column(db.String(100), nullable=False, index=True)
    date_debut = db.Column(db.DateTime, default=datetime.utcnow)
    date_fin = db.Column(db.DateTime)
    duree = db.Column(db.Integer)  # en secondes
    statut = db.Column(db.String(20), default='en_cours')  # en_cours, complet, abandonne
    ip_address = db.Column(db.String(45))
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)

    user_agent = db.Column(db.Text)
    
    # Informations du répondant (si collectées)
    email_repondant = db.Column(db.String(255))
    nom_repondant = db.Column(db.String(255))
    autre_info = db.Column(db.JSON)
    
    # Relations
    questionnaire = db.relationship('Questionnaire', back_populates='reponses')
    reponses = db.relationship('ReponseQuestion', back_populates='reponse_questionnaire', 
                              cascade='all, delete-orphan', lazy=True)
    
    def __repr__(self):
        return f'<ReponseQuestionnaire #{self.id}>'


class ReponseQuestion(db.Model):
    __tablename__ = 'reponse_question'
    
    id = db.Column(db.Integer, primary_key=True)
    reponse_questionnaire_id = db.Column(db.Integer, db.ForeignKey('reponse_questionnaire.id', ondelete='CASCADE'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'), nullable=False)
    valeur_texte = db.Column(db.Text)
    valeur_numerique = db.Column(db.Float)
    valeur_date = db.Column(db.DateTime)
    fichier_path = db.Column(db.String(500))
    fichier_nom = db.Column(db.String(255))
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)

    fichier_taille = db.Column(db.Integer)
    date_reponse = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Pour les questions à choix multiples
    options_selectionnees = db.relationship('ReponseOption', back_populates='reponse_question',
                                          cascade='all, delete-orphan', lazy=True)
    
    # Relations
    reponse_questionnaire = db.relationship('ReponseQuestionnaire', back_populates='reponses')
    question = db.relationship('Question', back_populates='reponses')
    
    def get_valeur_formatee(self):
        """Retourne la valeur formatée pour l'affichage"""
        if self.valeur_texte:
            return self.valeur_texte
        elif self.valeur_numerique is not None:
            return str(self.valeur_numerique)
        elif self.valeur_date:
            return self.valeur_date.strftime('%d/%m/%Y %H:%M')
        elif self.fichier_path:
            return f"[Fichier] {self.fichier_nom}"
        return ""
    
    def __repr__(self):
        return f'<ReponseQuestion {self.question_id}>'


class ReponseOption(db.Model):
    __tablename__ = 'reponse_option'
    
    id = db.Column(db.Integer, primary_key=True)
    reponse_question_id = db.Column(db.Integer, db.ForeignKey('reponse_question.id', ondelete='CASCADE'), nullable=False)
    option_id = db.Column(db.Integer, db.ForeignKey('option_question.id'), nullable=False)
    texte_autre = db.Column(db.String(500))
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)

    # Relations
    reponse_question = db.relationship('ReponseQuestion', back_populates='options_selectionnees')
    option = db.relationship('OptionQuestion')
    
    def __repr__(self):
        return f'<ReponseOption {self.option_id}>'

# -------------------- RECOMMANDATION GLOBALE --------------------
class RecommandationGlobale(db.Model):
    """Recommandations globales prédéfinies pour les rapports d'audit"""
    __tablename__ = 'recommandations_globales'
    
    id = db.Column(db.Integer, primary_key=True)
    texte = db.Column(db.Text, nullable=False)
    type_audit = db.Column(db.String(100))  # Type d'audit spécifique (optionnel)
    categorie = db.Column(db.String(100))  # Catégorie : securite, qualite, conformite, etc.
    priorite = db.Column(db.Integer, default=1)  # 1-5
    est_actif = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)

    createur = db.relationship('User', foreign_keys=[created_by])
    
    def __repr__(self):
        return f'<RecommandationGlobale {self.id}: {self.texte[:50]}...>'


class AnalyseIA(db.Model):
    """Modèle pour sauvegarder les analyses IA"""
    __tablename__ = 'analyse_ia'
    
    id = db.Column(db.Integer, primary_key=True)
    audit_id = db.Column(db.Integer, db.ForeignKey('audits.id'), nullable=False)  # CORRECTION: 'audits.id'
    type_analyse = db.Column(db.String(100), nullable=False)
    resultat = db.Column(db.JSON, nullable=False)
    score_confiance = db.Column(db.Float, default=0.0)
    date_analyse = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)

    # CORRECTION: foreign_keys=[audit_id]
    audit = db.relationship('Audit', foreign_keys=[audit_id], backref='analyses_ia')
    
    utilisateur = db.relationship('User', foreign_keys=[created_by], backref='analyses_ia_crees')
    
    def __repr__(self):
        return f'<AnalyseIA {self.id} - Audit {self.audit_id}>'

class Notification(db.Model):
    __tablename__ = 'notification'
    
    # Types de notifications
    TYPE_CONSTATATION = 'nouvelle_constatation'
    TYPE_RECOMMANDATION = 'nouvelle_recommandation'
    TYPE_PLAN = 'nouveau_plan'
    TYPE_ECHEANCE = 'echeance'
    TYPE_RETARD = 'retard'
    TYPE_VALIDATION = 'validation_requise'
    TYPE_KRI_ALERTE = 'kri_alerte'
    TYPE_VEILLE = 'veille_nouvelle'
    TYPE_AUDIT_DEMARRE = 'audit_demarre'
    TYPE_AUDIT_TERMINE = 'audit_termine'
    TYPE_RISQUE_EVALUE = 'risque_evalue'
    TYPE_SYSTEME = 'systeme'
    TYPE_INFO = 'info'
    TYPE_SUCCESS = 'success'
    TYPE_WARNING = 'warning'
    TYPE_ERROR = 'error'
    
    # Niveaux d'urgence
    URGENCE_NORMAL = 'normal'
    URGENCE_IMPORTANT = 'important'
    URGENCE_URGENT = 'urgent'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Informations de base
    type_notification = db.Column(db.String(50), nullable=False)
    titre = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text)
    urgence = db.Column(db.String(20), default=URGENCE_NORMAL)
    
    # Destinataire
    destinataire_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    
    # Entité liée
    entite_type = db.Column(db.String(50))
    entite_id = db.Column(db.Integer)
    
    # Statut
    est_lue = db.Column(db.Boolean, default=False)
    est_envoyee_email = db.Column(db.Boolean, default=False)
    est_envoyee_push = db.Column(db.Boolean, default=False)
    
    # Métadonnées (NE PAS APPELER 'metadata' !)
    actions_possibles = db.Column(db.JSON, default=[])
    donnees_supplementaires = db.Column(db.JSON, default={})  # Renommé !
    expires_at = db.Column(db.DateTime)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    read_at = db.Column(db.DateTime)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)

    # Relations
    destinataire = db.relationship('User', back_populates='notifications_recues', foreign_keys=[destinataire_id])
    
    # Index
    __table_args__ = (
        db.Index('idx_notif_user_read', 'destinataire_id', 'est_lue'),
        db.Index('idx_notif_created', 'created_at'),
    )
    
    # Méthodes
    def to_dict(self, include_details=False):
        """Convertir en dictionnaire"""
        data = {
            'id': self.id,
            'type': self.type_notification,
            'titre': self.titre,
            'message': self.message,
            'urgence': self.urgence,
            'est_lue': self.est_lue,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'time_ago': self.get_time_ago(),
            'icon': self.get_icon(),
            'color': self.get_color(),
            'entite_type': self.entite_type,
            'entite_id': self.entite_id,
            'url': self.get_url(),
        }
        
        if include_details:
            data.update({
                'actions': self.actions_possibles or [],
                'donnees': self.donnees_supplementaires or {},  # Changé
                'read_at': self.read_at.isoformat() if self.read_at else None,
                'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            })
        
        return data
    
    def get_icon(self):
        """Retourne l'icône selon le type"""
        icons = {
            self.TYPE_CONSTATATION: 'exclamation-circle',
            self.TYPE_RECOMMANDATION: 'lightbulb',
            self.TYPE_PLAN: 'tasks',
            self.TYPE_ECHEANCE: 'calendar-exclamation',
            self.TYPE_RETARD: 'clock',
            self.TYPE_VALIDATION: 'check-circle',
            self.TYPE_KRI_ALERTE: 'chart-line',
            self.TYPE_VEILLE: 'balance-scale',
            self.TYPE_AUDIT_DEMARRE: 'play-circle',
            self.TYPE_AUDIT_TERMINE: 'check-circle',
            self.TYPE_RISQUE_EVALUE: 'exclamation-triangle',
            self.TYPE_SYSTEME: 'cog',
            self.TYPE_INFO: 'info-circle',
            self.TYPE_SUCCESS: 'check-circle',
            self.TYPE_WARNING: 'exclamation-triangle',
            self.TYPE_ERROR: 'times-circle',
        }
        return icons.get(self.type_notification, 'bell')
    
    def get_color(self):
        """Retourne la couleur selon l'urgence"""
        colors = {
            self.URGENCE_URGENT: 'danger',
            self.URGENCE_IMPORTANT: 'warning',
            self.URGENCE_NORMAL: 'info',
        }
        return colors.get(self.urgence, 'secondary')
    
    def get_time_ago(self):
        """Retourne le temps écoulé formaté"""
        if not self.created_at:
            return "Récemment"
        
        now = datetime.utcnow()
        diff = now - self.created_at
        
        if diff.days > 365:
            years = diff.days // 365
            return f"{years} an{'s' if years > 1 else ''}"
        elif diff.days > 30:
            months = diff.days // 30
            return f"{months} mois"
        elif diff.days > 7:
            weeks = diff.days // 7
            return f"{weeks} semaine{'s' if weeks > 1 else ''}"
        elif diff.days > 0:
            return f"{diff.days} jour{'s' if diff.days > 1 else ''}"
        elif diff.seconds >= 3600:
            hours = diff.seconds // 3600
            return f"{hours} heure{'s' if hours > 1 else ''}"
        elif diff.seconds >= 60:
            minutes = diff.seconds // 60
            return f"{minutes} minute{'s' if minutes > 1 else ''}"
        else:
            return "À l'instant"
    
    def get_url(self):
        """Retourne l'URL vers l'entité"""
        if not self.entite_type or not self.entite_id:
            return None
        
        urls = {
            'audit': f'/audit/{self.entite_id}',
            'constatation': f'/audit/constatation/{self.entite_id}',
            'recommandation': f'/audit/recommandation/{self.entite_id}',
            'plan_action': f'/audit/plan-action/{self.entite_id}',
            'risque': f'/risque/{self.entite_id}',
            'kri': f'/kri/{self.entite_id}',
            'cartographie': f'/cartographie/{self.entite_id}',
            'processus': f'/processus/{self.entite_id}',
            'veille': f'/veille/{self.entite_id}',
            'questionnaire': f'/questionnaire/{self.entite_id}',
        }
        return urls.get(self.entite_type)
    
    def marquer_comme_lue(self):
        """Marquer la notification comme lue"""
        if not self.est_lue:
            self.est_lue = True
            self.read_at = datetime.utcnow()
            db.session.commit()
            return True
        return False
    
    def est_expiree(self):
        """Vérifier si la notification est expirée"""
        if self.expires_at:
            return datetime.utcnow() > self.expires_at
        return False
    
    @classmethod
    def get_types_display(cls):
        """Retourne les types avec leurs libellés"""
        return {
            cls.TYPE_CONSTATATION: "Nouvelle constatation",
            cls.TYPE_RECOMMANDATION: "Nouvelle recommandation",
            cls.TYPE_PLAN: "Nouveau plan d'action",
            cls.TYPE_ECHEANCE: "Échéance",
            cls.TYPE_RETARD: "Retard",
            cls.TYPE_VALIDATION: "Validation requise",
            cls.TYPE_KRI_ALERTE: "Alerte KRI",
            cls.TYPE_VEILLE: "Nouvelle veille réglementaire",
            cls.TYPE_AUDIT_DEMARRE: "Audit démarré",
            cls.TYPE_AUDIT_TERMINE: "Audit terminé",
            cls.TYPE_RISQUE_EVALUE: "Risque évalué",
            cls.TYPE_SYSTEME: "Système",
            cls.TYPE_INFO: "Information",
            cls.TYPE_SUCCESS: "Succès",
            cls.TYPE_WARNING: "Avertissement",
            cls.TYPE_ERROR: "Erreur",
        }

# -------------------- CLIENT / TENANT --------------------
class Client(db.Model):
    __tablename__ = 'clients'
    
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(200), nullable=False)
    reference = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.Text)
    
    # Informations de contact
    contact_nom = db.Column(db.String(100))
    contact_email = db.Column(db.String(120))
    contact_telephone = db.Column(db.String(20))

    # Configuration
    domaine = db.Column(db.String(200), unique=True)
    logo = db.Column(db.String(500))
    theme_couleur = db.Column(db.String(50), default='#1A3C6B')
    langue = db.Column(db.String(10), default='fr')
    fuseau_horaire = db.Column(db.String(50), default='Europe/Paris')
    
    # Plan et limitations
    plan = db.Column(db.String(50), default='standard')  # standard, premium, enterprise
    max_utilisateurs = db.Column(db.Integer, default=10)
    max_risques = db.Column(db.Integer, default=1000)
    max_audits = db.Column(db.Integer, default=100)
    
    # Statut
    is_active = db.Column(db.Boolean, default=True)
    date_activation = db.Column(db.DateTime)
    date_expiration = db.Column(db.DateTime)
    
    # Sécurité
    api_key = db.Column(db.String(100), unique=True)
    secret_key = db.Column(db.String(100), unique=True)
    
    # Métriques
    nb_utilisateurs = db.Column(db.Integer, default=0)
    nb_risques = db.Column(db.Integer, default=0)
    nb_audits = db.Column(db.Integer, default=0)
    derniere_activite = db.Column(db.DateTime)

    # AJOUTER CES CHAMPS :
    formule_id = db.Column(db.Integer, db.ForeignKey('formules_abonnement.id'))
    users = db.relationship('User', back_populates='client', lazy='dynamic')

    
    # AJOUTER CES RELATIONS :
    formule = db.relationship('FormuleAbonnement', back_populates='clients')
    abonnements = db.relationship('AbonnementClient', back_populates='client', lazy=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relations
    utilisateurs = db.relationship('User', back_populates='client', lazy=True)
    environnements = db.relationship('EnvironnementClient', back_populates='client', lazy=True)
    
    def __repr__(self):
        return f'<Client {self.nom} ({self.reference})>'
    
    def generer_identifiants_api(self):
        """Génère des clés API uniques"""
        import secrets
        self.api_key = secrets.token_urlsafe(32)
        self.secret_key = secrets.token_urlsafe(64)
        return self
    
    def verifier_limites(self):
        """Vérifie si le client dépasse ses limites"""
        return {
            'utilisateurs': self.nb_utilisateurs <= self.max_utilisateurs,
            'risques': self.nb_risques <= self.max_risques,
            'audits': self.nb_audits <= self.max_audits
        }
    
    def incrementer_metrique(self, metrique):
        """Incrémente une métrique"""
        if metrique == 'utilisateurs':
            self.nb_utilisateurs += 1
        elif metrique == 'risques':
            self.nb_risques += 1
        elif metrique == 'audits':
            self.nb_audits += 1
        self.derniere_activite = datetime.utcnow()

# -------------------- ENVIRONNEMENT CLIENT --------------------
class EnvironnementClient(db.Model):
    __tablename__ = 'environnements_client'
    
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)
    nom = db.Column(db.String(100), nullable=False)
    
    # Serveur/Sous-domaine
    sous_domaine = db.Column(db.String(100), unique=True)
    url_acces = db.Column(db.String(500))
    
    # Base de données
    db_host = db.Column(db.String(200))
    db_name = db.Column(db.String(100))
    db_user = db.Column(db.String(100))
    db_password = db.Column(db.String(500))

    # Configuration serveur
    server_ip = db.Column(db.String(50))
    server_port = db.Column(db.Integer, default=22)
    server_ssh_user = db.Column(db.String(50))
    server_ssh_key = db.Column(db.Text)
    
    # Statut
    statut = db.Column(db.String(20), default='actif')  # actif, suspendu, en_maintenance, supprime
    date_provision = db.Column(db.DateTime)
    date_suspension = db.Column(db.DateTime)
    
    # Ressources
    cpu_alloue = db.Column(db.String(50), default='1 core')
    ram_alloue = db.Column(db.String(50), default='1GB')
    stockage_alloue = db.Column(db.String(50), default='10GB')
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relations
    client = db.relationship('Client', back_populates='environnements')

def __repr__(self):
    return f'<Environnement {self.nom} pour client {self.client_id}>'

def get_db_connection_string(self):
    """Retourne la chaîne de connexion à la base de données"""
    return f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}/{self.db_name}"

def provisionner_serveur(self):
    """Déclenche le provisionnement du serveur"""
    # Cette méthode serait implémentée avec Ansible/Terraform/etc.
    pass

# -------------------- JOURNAL ACTIVITÉ CLIENT --------------------
class JournalActiviteClient(db.Model):
    __tablename__ = 'journal_activite_client'
    
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)
    utilisateur_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    action = db.Column(db.String(100), nullable=False)
    details = db.Column(db.JSON)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relations
    client = db.relationship('Client')
    utilisateur = db.relationship('User')
    
    def __repr__(self):
        return f'<JournalActiviteClient {self.action} pour client {self.client_id}>'

    
class ClientDataFilter:
    """Filtre automatiquement TOUTES les requêtes par client"""
    
    # Modèles qui doivent être filtrés par client_id
    CLIENT_MODELS = [
        User, Direction, Service, Cartographie, Risque, EvaluationRisque,
        KRI, MesureKRI, Processus, EtapeProcessus, SousEtapeProcessus, 
        LienProcessus, ZoneRisqueProcessus, ControleProcessus, 
        VeilleReglementaire, ActionConformite, Audit, Constatation, 
        Recommandation, PlanAction, EtapePlanAction, HistoriqueModification,
        Alerte, ZoneRisqueOrganigramme, PointDecision, LigneOrganisation,
        TitreOrganisation, ConfigurationAudit, TemplateConstatation,
        TemplateRecommandation, ProcessusActivite, ElementLogigramme,
        LienLogigramme, VeilleDocument, ParametreEvaluation,
        GuideEvaluation, JournalActivite, PermissionTemplate,
        SystemLog, Notification, ConfigurationChampRisque,
        ConfigurationListeDeroulante, ChampPersonnaliseRisque,
        FichierRisque, FichierKRI, AuditRisque, SousAction,
        JournalAudit, HistoriqueRecommandation, MatriceMaturite,
        Questionnaire, QuestionnaireCategorie, Question, OptionQuestion,
        ConditionQuestion, ReponseQuestionnaire, ReponseQuestion,
        ReponseOption, CampagneEvaluation, AnalyseIA, FichierMetadata,
        RecommandationGlobale
    ]
    
    @classmethod
    def apply_client_filter(cls, query, model_class):
        """Applique automatiquement le filtre client_id à une requête"""
        
        # 1. SUPER ADMIN : PAS DE FILTRE
        if current_user.is_authenticated and current_user.role == 'super_admin':
            return query
        
        # 2. USER NON CONNECTÉ : PAS DE FILTRE (arrivera à la page login)
        if not current_user.is_authenticated:
            return query
        
        # 3. USER CONNECTÉ AVEC CLIENT_ID
        client_id = current_user.client_id
        
        # 4. FILTRER PAR CLIENT_ID DIRECT
        if hasattr(model_class, 'client_id'):
            return query.filter(model_class.client_id == client_id)
        
        # 5. FILTRER PAR CREATED_BY (utilisateur du client)
        if hasattr(model_class, 'created_by'):
            # Récupérer tous les utilisateurs du même client
            user_ids = cls._get_client_user_ids(client_id)
            return query.filter(model_class.created_by.in_(user_ids))
        
        # 6. FILTRER PAR RELATIONS
        # Pour les modèles qui n'ont pas client_id mais sont liés à un modèle qui en a
        filter_map = cls._get_filter_mappings(model_class, client_id)
        if filter_map:
            return query.filter(*filter_map)
        
        # 7. PAR DÉFAUT : retourner la requête originale
        return query
    
    @staticmethod
    def _get_client_user_ids(client_id):
        """Récupère tous les IDs d'utilisateurs d'un client"""
        user_ids = User.query.filter_by(client_id=client_id).with_entities(User.id).all()
        return [uid[0] for uid in user_ids] if user_ids else [-1]  # [-1] pour éviter les résultats
    
    @classmethod
    def _get_filter_mappings(cls, model_class, client_id):
        """Mappage des relations pour filtrer indirectement"""
        mappings = {
            # Mappages spécifiques si nécessaire
        }
        
        return mappings.get(model_class)

# ====================
# MODÈLES FORMULES
# ====================

class FormuleAbonnement(db.Model):
    """Formule d'abonnement standard/prémium"""
    __tablename__ = 'formules_abonnement'
    
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    code = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.Text)
    prix_mensuel = db.Column(db.Float, default=0)
    prix_annuel = db.Column(db.Float, default=0)
    
    # Limites
    max_utilisateurs = db.Column(db.Integer, default=10)
    max_risques = db.Column(db.Integer, default=1000)
    max_audits = db.Column(db.Integer, default=100)
    max_processus = db.Column(db.Integer, default=50)
    max_logigrammes = db.Column(db.Integer, default=20)
    
    # Stockage
    stockage_upload = db.Column(db.Integer, default=1024)
    stockage_documents = db.Column(db.Integer, default=512)
    
    # Features activées
    features = db.Column(db.JSON, default={
        'risques': True,
        'kri': True,
        'audit': True,
        'veille_reglementaire': False,
        'logigrammes': False,
        'ia_analyse': False,
        'reports_avances': False,
        'multi_sites': False,
        'api_avancee': False,
        'sauvegardes_auto': False,
        'support_prioritaire': False,
        'custom_domain': False,
        'sso': False,
        'import_export': True,
        'workflow': False,
        'notifications': True
    })
    
    # Modules accessibles - UTILISEZ LES NOMS EXACTS DE LA BASE DE DONNÉES
    modules = db.Column(db.JSON, default={
        # Modules standards
        'cartographie': True,
        'matrices_risque': True,
        'suivi_kri': True,
        'audit_interne': True,
        'plans_action': True,
        
        # Modules problématiques - NOMS EXACTS DE LA BASE DE DONNÉES
        'veille_reglementaire': False,  # IMPORTANT: pas 'veille'
        'gestion_processus': False,     # IMPORTANT: pas 'processus'
        'analyse_ia': False,           # IMPORTANT: pas 'ia_analyse'
        'tableaux_bord': False,        # IMPORTANT: pas 'tableaux_bord_personnalisables'
        
        # Autres modules
        'organigramme': False,
        'questionnaires': False,
        'portail_fournisseurs': False,
        'reporting_avance': False
    })
    
    # Rôles autorisés
    roles_autorises = db.Column(db.JSON, default=['utilisateur', 'auditeur', 'manager'])
    
    # Permissions par défaut pour cette formule
    permissions_template = db.Column(db.JSON, default={
        # ==================== PERMISSIONS DE BASE ====================
        'can_view_dashboard': True,
        'can_view_reports': True,
        'can_view_departments': True,
        'can_view_users_list': True,   # Peut voir la liste (lecture seule)
        
        # ==================== PERMISSIONS MODULAIRES ====================
        # Cartographie
        'can_manage_risks': True,
        'can_validate_risks': True,
        
        # KRI
        'can_manage_kri': True,
        
        # Audit
        'can_manage_audit': True,
        'can_confirm_evaluations': True,
        
        # Veille règlementaire (lié au module 'veille_reglementaire')
        'can_manage_regulatory': False,
        
        # Processus (lié au module 'gestion_processus')
        'can_manage_logigram': False,
        
        # Analyse IA (lié au module 'analyse_ia')
        'can_use_ia_analysis': False,
        
        # Reporting
        'can_export_data': False,
        
        # ==================== ADMINISTRATION ====================
        'can_manage_settings': False,
        'can_manage_permissions': False,
        'can_manage_users': False,
        'can_edit_users': False,
        'can_manage_departments': False,
        'can_access_all_departments': False,
        'can_delete_data': False,
        'can_archive_data': False,
        
        # ==================== PARAMÉTRAGE ====================
        'can_manage_lists': False,
        'can_manage_fields': False,
        'can_manage_files': False,
        'can_manage_templates': False,
        
        # ==================== SYSTÈME ====================
        'can_manage_clients': False,
        'can_provision_servers': False,
        'can_manage_action_plans': True,  # Pour plans_action
        'can_view_action_plans': True,    # Pour consultation
    })
    
    is_active = db.Column(db.Boolean, default=True)
    is_public = db.Column(db.Boolean, default=True)
    ordre_affichage = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relations
    clients = db.relationship('Client', back_populates='formule')
    
    def __repr__(self):
        return f'<Formule {self.nom} ({self.code})>'
    
    def get_features_list(self):
        """Retourne la liste des features activées"""
        return [k for k, v in self.features.items() if v]
    
    def get_modules_list(self):
        """Retourne la liste des modules accessibles"""
        return [k for k, v in self.modules.items() if v]
    
    def get_module_status(self, module_code):
        """
        Retourne le statut d'un module avec gestion des alias
        Pour résoudre le problème de mapping
        """
        # Mapping des alias vers les noms réels de la base de données
        module_alias_map = {
            # Alias courants → Noms réels dans la base
            'veille': 'veille_reglementaire',
            'processus': 'gestion_processus', 
            'logigrammes': 'gestion_processus',
            'ia_analyse': 'analyse_ia',
            'tableaux_bord_personnalisables': 'tableaux_bord',
            
            # Autres alias
            'questionnaires': 'questionnaires',
            'organigramme': 'organigramme',
            'portail_fournisseurs': 'portail_fournisseurs',
            'reporting_avance': 'reporting_avance',
            'matrices_risque': 'matrices_risque',
            'plans_action': 'plans_action',
            'risques': 'cartographie',
            'cartographie': 'cartographie',
            'audit_interne': 'audit_interne',
            'suivi_kri': 'suivi_kri'
        }
        
        # Convertir l'alias en nom réel
        real_module = module_alias_map.get(module_code, module_code)
        
        # Vérifier si le module existe dans la base
        exists = real_module in self.modules
        is_active = self.modules.get(real_module, False) if exists else False
        
        return {
            'alias': module_code,
            'real_name': real_module,
            'is_active': is_active,
            'exists': exists,
            'value': self.modules.get(real_module) if exists else None
        }
    
    def can_access_module(self, module_code):
        """
        Vérifie si la formule permet d'accéder à un module
        Version corrigée avec gestion des alias
        """
        module_info = self.get_module_status(module_code)
        
        if not module_info['exists']:
            print(f"⚠️ Module '{module_code}' (réel: '{module_info['real_name']}') non trouvé dans {list(self.modules.keys())}")
            return False
        
        return module_info['is_active']
    
    def can_use_feature(self, feature_code):
        """Vérifie si la formule permet d'utiliser une feature"""
        return self.features.get(feature_code, False)
    
    def get_role_permissions(self, role):
        """Retourne les permissions pour un rôle spécifique dans cette formule"""
        if role not in self.roles_autorises:
            return {}
        
        # Copie des permissions de base
        base_permissions = self.permissions_template.copy()
        
        # Ajustements selon le rôle
        role_adjustments = {
            'admin': {
                'can_manage_users': True,
                'can_manage_settings': True,
                'can_manage_permissions': True,
                'can_edit_users': True,
                'can_view_users_list': True,
                'can_manage_departments': True,
                'can_delete_data': True,
                'can_archive_data': True
            },
            'manager': {
                'can_manage_risks': True,
                'can_manage_kri': True,
                'can_manage_audit': True,
                'can_view_reports': True,
                'can_export_data': True,
                'can_validate_risks': True
            },
            'auditeur': {
                'can_manage_audit': True,
                'can_view_reports': True,
                'can_view_departments': True
            },
            'utilisateur': {
                'can_view_dashboard': True,
                'can_view_reports': True,
                'can_view_departments': True,
                'can_view_users_list': True
            },
            'compliance': {
                'can_manage_regulatory': True,
                'can_view_reports': True,
                'can_export_data': True
            },
            'consultant': {
                'can_view_reports': True,
                'can_view_departments': True
            }
        }
        
        if role in role_adjustments:
            for perm, value in role_adjustments[role].items():
                if perm in base_permissions:
                    # Appliquer l'ajustement seulement si la permission existe
                    base_permissions[perm] = value
        
        # S'assurer que les permissions liées aux modules sont correctes
        self.synchronize_module_permissions()
        
        return base_permissions
    
    def synchronize_module_permissions(self):
        """
        Synchronise automatiquement les permissions avec les modules activés
        Doit être appelé avant de retourner les permissions
        """
        # Mapping module → permissions
        module_permission_map = {
            'veille_reglementaire': ['can_manage_regulatory'],
            'gestion_processus': ['can_manage_logigram'],
            'analyse_ia': ['can_use_ia_analysis'],
            'suivi_kri': ['can_manage_kri'],
            'audit_interne': ['can_manage_audit', 'can_confirm_evaluations'],
            'cartographie': ['can_manage_risks', 'can_validate_risks'],
            'reporting_avance': ['can_export_data', 'can_view_reports'],
            'tableaux_bord': ['can_view_dashboard']
        }
        
        for module_name, permissions in module_permission_map.items():
            is_module_active = self.modules.get(module_name, False)
            
            for permission in permissions:
                if permission in self.permissions_template:
                    # Si le module est activé, activer la permission
                    if is_module_active:
                        self.permissions_template[permission] = True
                    # Si le module est désactivé, désactiver la permission
                    else:
                        self.permissions_template[permission] = False
    
    def check_module_permission_sync(self):
        """Vérifie la synchronisation entre modules et permissions"""
        issues = []
        
        # Vérifier les modules problématiques
        problem_modules = {
            'veille_reglementaire': 'can_manage_regulatory',
            'gestion_processus': 'can_manage_logigram',
            'analyse_ia': 'can_use_ia_analysis',
            'tableaux_bord': 'can_view_dashboard'
        }
        
        for module_name, permission in problem_modules.items():
            module_active = self.modules.get(module_name, False)
            permission_active = self.permissions_template.get(permission, False)
            
            if module_active != permission_active:
                issues.append({
                    'module': module_name,
                    'permission': permission,
                    'module_active': module_active,
                    'permission_active': permission_active,
                    'status': 'INCOHERENT'
                })
        
        return issues
    
    def fix_module_permission_sync(self):
        """Corrige automatiquement la synchronisation modules/permissions"""
        issues = self.check_module_permission_sync()
        
        if issues:
            print(f"🔧 Correction des incohérences pour formule {self.nom}:")
            
            for issue in issues:
                module_active = self.modules.get(issue['module'], False)
                self.permissions_template[issue['permission']] = module_active
                print(f"  🔄 {issue['permission']} = {module_active} (module: {issue['module']})")
            
            return True
        
        return False

    
    def get_permissions_list(self):
        """
        Retourne la liste des permissions activées dans le template
        Format: ['permission1', 'permission2', ...]
        """
        if not self.permissions_template:
            return []
        
        # Retourner les clés des permissions qui sont True
        return [permission for permission, is_active in self.permissions_template.items() if is_active]
    
    # Alternative : Méthode qui retourne toutes les permissions avec leur statut
    def get_permissions_with_status(self):
        """
        Retourne toutes les permissions avec leur statut
        Format: {'permission1': True, 'permission2': False, ...}
        """
        return self.permissions_template.copy() if self.permissions_template else {}
    
    # Méthode pour vérifier si une permission spécifique est activée
    def has_permission(self, permission_name):
        """
        Vérifie si une permission spécifique est activée dans la formule
        """
        if not self.permissions_template:
            return False
        
        return self.permissions_template.get(permission_name, False)
    
    # Méthode pour activer/désactiver une permission
    def set_permission(self, permission_name, is_active):
        """
        Active ou désactive une permission spécifique
        """
        if not self.permissions_template:
            self.permissions_template = {}
        
        self.permissions_template[permission_name] = is_active
        self.updated_at = datetime.utcnow()
        return self
    
    def get_usage_stats(self, client_id=None):
        """Retourne les statistiques d'utilisation"""
        from models import User, Risque, Audit, Processus, ProcessusActivite
        
        if client_id:
            # Pour un client spécifique
            users_count = User.query.filter_by(client_id=client_id, is_active=True).count()
            risks_count = Risque.query.filter_by(client_id=client_id, is_archived=False).count()
            audits_count = Audit.query.filter_by(client_id=client_id, is_archived=False).count()
            processes_count = Processus.query.filter_by(client_id=client_id).count()
            logigrammes_count = ProcessusActivite.query.filter_by(client_id=client_id).count()
        else:
            # Pour tous les clients de cette formule
            users_count = sum(client.nb_utilisateurs or 0 for client in self.clients)
            risks_count = sum(client.nb_risques or 0 for client in self.clients)
            audits_count = sum(client.nb_audits or 0 for client in self.clients)
            processes_count = 0
            logigrammes_count = 0
        
        stats = {
            'utilisateurs': {
                'current': users_count,
                'limit': self.max_utilisateurs,
                'percent': min((users_count / max(self.max_utilisateurs, 1)) * 100, 100)
            },
            'risques': {
                'current': risks_count,
                'limit': self.max_risques,
                'percent': min((risks_count / max(self.max_risques, 1)) * 100, 100)
            },
            'audits': {
                'current': audits_count,
                'limit': self.max_audits,
                'percent': min((audits_count / max(self.max_audits, 1)) * 100, 100)
            },
            'processus': {
                'current': processes_count,
                'limit': self.max_processus,
                'percent': min((processes_count / max(self.max_processus, 1)) * 100, 100)
            },
            'logigrammes': {
                'current': logigrammes_count,
                'limit': self.max_logigrammes,
                'percent': min((logigrammes_count / max(self.max_logigrammes, 1)) * 100, 100)
            }
        }
        
        # Ajouter des classes de couleur
        for key, data in stats.items():
            if data['percent'] >= 90:
                data['color_class'] = 'danger'
            elif data['percent'] >= 70:
                data['color_class'] = 'warning'
            else:
                data['color_class'] = 'success'
        
        return stats
    
    def next_level_name(self):
        """Retourne le nom de la formule supérieure"""
        # Logique simple pour trouver la formule suivante
        if self.code == 'standard':
            return 'Premium'
        elif self.code == 'premium':
            return 'Enterprise'
        else:
            return None
    
    def get_problematic_modules_diagnostic(self):
        """Diagnostic des modules problématiques"""
        diagnostic = []
        
        # Modules à vérifier
        modules_to_check = [
            ('veille', 'veille_reglementaire', 'can_manage_regulatory'),
            ('processus', 'gestion_processus', 'can_manage_logigram'),
            ('ia_analyse', 'analyse_ia', 'can_use_ia_analysis'),
            ('tableaux_bord_personnalisables', 'tableaux_bord', 'can_view_dashboard')
        ]
        
        for alias, real_name, permission in modules_to_check:
            # Vérifier l'alias
            alias_exists = alias in self.modules
            alias_value = self.modules.get(alias, 'N/A') if alias_exists else None
            
            # Vérifier le nom réel
            real_exists = real_name in self.modules
            real_value = self.modules.get(real_name, 'N/A') if real_exists else None
            
            # Vérifier la permission
            permission_value = self.permissions_template.get(permission, False)
            
            # Déterminer le statut
            if not real_exists:
                status = '❌ MODULE MANQUANT'
            elif alias_exists and alias_value != real_value:
                status = '⚠️ ALIAS INCOHERENT'
            elif real_value != permission_value:
                status = '⚠️ PERMISSION DESYNCHRONISEE'
            else:
                status = '✅ OK'
            
            diagnostic.append({
                'alias': alias,
                'real_name': real_name,
                'permission': permission,
                'alias_exists': alias_exists,
                'alias_value': alias_value,
                'real_exists': real_exists,
                'real_value': real_value,
                'permission_value': permission_value,
                'status': status,
                'needs_fix': status != '✅ OK'
            })
        
        return diagnostic
    
    def fix_problematic_modules(self):
        """Corrige les modules problématiques"""
        fixes_applied = 0
        
        # Correction des noms
        name_corrections = {
            'veille': 'veille_reglementaire',
            'processus': 'gestion_processus',
            'ia_analyse': 'analyse_ia',
            'tableaux_bord_personnalisables': 'tableaux_bord'
        }
        
        for old_name, new_name in name_corrections.items():
            if old_name in self.modules:
                # Transférer la valeur
                self.modules[new_name] = self.modules[old_name]
                # Supprimer l'ancien
                del self.modules[old_name]
                fixes_applied += 1
                print(f"  🔄 Renommage: {old_name} → {new_name}")
        
        # Synchronisation des permissions
        permission_sync = {
            'veille_reglementaire': 'can_manage_regulatory',
            'gestion_processus': 'can_manage_logigram',
            'analyse_ia': 'can_use_ia_analysis',
            'tableaux_bord': 'can_view_dashboard'
        }
        
        for module_name, permission in permission_sync.items():
            if module_name in self.modules:
                module_active = self.modules[module_name]
                current_permission = self.permissions_template.get(permission, False)
                
                if module_active != current_permission:
                    self.permissions_template[permission] = module_active
                    fixes_applied += 1
                    print(f"  🔄 Permission: {permission} = {module_active}")
        
        if fixes_applied > 0:
            self.updated_at = datetime.utcnow()
        
        return fixes_applied


class AbonnementClient(db.Model):
    """Historique et détails d'abonnement d'un client"""
    __tablename__ = 'abonnements_client'
    
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)
    formule_id = db.Column(db.Integer, db.ForeignKey('formules_abonnement.id'), nullable=False)
    
    # Période
    date_debut = db.Column(db.Date, nullable=False)
    date_fin = db.Column(db.Date)
    periode = db.Column(db.String(20), default='mensuel')
    
    # Statut
    statut = db.Column(db.String(20), default='actif')
    is_renouvellement_auto = db.Column(db.Boolean, default=True)
    
    # Paiement
    montant = db.Column(db.Float)
    devise = db.Column(db.String(3), default='EUR')
    methode_paiement = db.Column(db.String(50))
    reference_paiement = db.Column(db.String(100))
    date_prochain_paiement = db.Column(db.Date)
    
    # Customisation
    customisations = db.Column(db.JSON, default={})
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relations
    client = db.relationship('Client', back_populates='abonnements')
    formule = db.relationship('FormuleAbonnement')
    
    def __repr__(self):
        return f'<Abonnement {self.client.nom} - {self.formule.nom}>'
    
    def is_active(self):
        """Vérifie si l'abonnement est actif"""
        today = datetime.utcnow().date()
        return (self.statut == 'actif' and 
                self.date_debut <= today and 
                (self.date_fin is None or self.date_fin >= today))
    
    def jours_restants(self):
        """Retourne le nombre de jours restants"""
        if not self.date_fin:
            return float('inf')
        today = datetime.utcnow().date()
        return (self.date_fin - today).days

# models.py - Classe FichierRapport complète
class FichierRapport(db.Model):
    """Fichiers attachés aux rapports d'audit"""
    __tablename__ = 'fichiers_rapport'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # CORRECTION DES CLÉS ÉTRANGÈRES :
    # Vérifiez le nom exact des tables dans votre base de données
    audit_id = db.Column(db.Integer, db.ForeignKey('audits.id'), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)
    uploaded_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)  # 'user.id' si c'est le bon nom
    
    # Informations sur le fichier
    nom_fichier = db.Column(db.String(255), nullable=False)
    chemin = db.Column(db.String(500), nullable=False)
    type_fichier = db.Column(db.String(50))
    taille = db.Column(db.Integer)  # en octets
    description = db.Column(db.Text)
    extension = db.Column(db.String(10))
    
    # Métadonnées
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # CORRECTIONS DES RELATIONS :
    # Relation avec Audit
    audit = db.relationship('Audit', 
                           backref=db.backref('fichiers_rapport', lazy='dynamic', cascade='all, delete-orphan'))
    
    # Relation avec User - version simple sans foreign_keys si le nom est correct
    uploader = db.relationship('User', backref='fichiers_uploads')
    
    # Relation avec Client
    client = db.relationship('Client', backref='fichiers_rapport')
    
    def __init__(self, **kwargs):
        super(FichierRapport, self).__init__(**kwargs)
        # Déterminer l'extension si elle n'est pas fournie
        if self.nom_fichier and not self.extension:
            self.extension = self.nom_fichier.split('.')[-1].lower() if '.' in self.nom_fichier else ''
        if self.nom_fichier and not self.type_fichier:
            self.determiner_type_fichier()
    
    def determiner_type_fichier(self):
        """Détermine le type de fichier basé sur l'extension"""
        if not self.nom_fichier:
            self.type_fichier = 'unknown'
            return
        
        ext = self.nom_fichier.split('.')[-1].lower() if '.' in self.nom_fichier else ''
        
        type_map = {
            'pdf': 'document',
            'doc': 'document',
            'docx': 'document',
            'xls': 'excel',
            'xlsx': 'excel',
            'ppt': 'powerpoint',
            'pptx': 'powerpoint',
            'jpg': 'image',
            'jpeg': 'image',
            'png': 'image',
            'gif': 'image',
            'txt': 'texte',
            'csv': 'donnees',
            'zip': 'archive',
            'rar': 'archive',
            '7z': 'archive',
            'xml': 'donnees',
            'json': 'donnees'
        }
        
        self.type_fichier = type_map.get(ext, 'autre')
    
    @property
    def taille_formatee(self):
        """Retourne la taille formatée (KB, MB, GB)"""
        if not self.taille:
            return "0 B"
        
        size = float(self.taille)
        units = ['B', 'KB', 'MB', 'GB', 'TB']
        unit_index = 0
        
        while size >= 1024 and unit_index < len(units) - 1:
            size /= 1024.0
            unit_index += 1
        
        return f"{size:.1f} {units[unit_index]}"
    
    def __repr__(self):
        return f'<FichierRapport {self.nom_fichier} pour audit {self.audit_id}>'
        
    @property
    def est_image(self):
        """Vérifie si le fichier est une image"""
        image_extensions = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp']
        return self.extension.lower() in image_extensions
    
    @property
    def est_document(self):
        """Vérifie si le fichier est un document"""
        doc_extensions = ['pdf', 'doc', 'docx', 'odt', 'rtf']
        return self.extension.lower() in doc_extensions
    
    @property
    def est_tableur(self):
        """Vérifie si le fichier est un tableur"""
        spreadsheet_extensions = ['xls', 'xlsx', 'ods', 'csv']
        return self.extension.lower() in spreadsheet_extensions
    
    @property
    def est_presentation(self):
        """Vérifie si le fichier est une présentation"""
        presentation_extensions = ['ppt', 'pptx', 'odp']
        return self.extension.lower() in presentation_extensions
    
    @property
    def est_archive(self):
        """Vérifie si le fichier est une archive"""
        archive_extensions = ['zip', 'rar', '7z', 'tar', 'gz']
        return self.extension.lower() in archive_extensions
    
    @property
    def date_upload_formatee(self):
        """Retourne la date d'upload formatée"""
        if not self.created_at:
            return "Date inconnue"
        
        now = datetime.utcnow()
        delta = now - self.created_at
        
        if delta.days == 0:
            if delta.seconds < 60:
                return "À l'instant"
            elif delta.seconds < 3600:
                minutes = delta.seconds // 60
                return f"Il y a {minutes} minute{'s' if minutes > 1 else ''}"
            else:
                heures = delta.seconds // 3600
                return f"Il y a {heures} heure{'s' if heures > 1 else ''}"
        elif delta.days == 1:
            return "Hier"
        elif delta.days < 7:
            return f"Il y a {delta.days} jour{'s' if delta.days > 1 else ''}"
        else:
            return self.created_at.strftime('%d/%m/%Y')
    
    @property
    def url_download(self):
        """Retourne l'URL de téléchargement"""
        return f"/fichier-rapport-audit/{self.id}/telecharger"
    
    @property
    def url_delete(self):
        """Retourne l'URL de suppression"""
        return f"/fichier-rapport-audit/{self.id}/supprimer"
    
    @property
    def icon_class(self):
        """Retourne la classe CSS de l'icône FontAwesome"""
        icon_map = {
            'pdf': 'fa-file-pdf text-danger',
            'doc': 'fa-file-word text-primary',
            'docx': 'fa-file-word text-primary',
            'xls': 'fa-file-excel text-success',
            'xlsx': 'fa-file-excel text-success',
            'ppt': 'fa-file-powerpoint text-warning',
            'pptx': 'fa-file-powerpoint text-warning',
            'jpg': 'fa-file-image text-info',
            'jpeg': 'fa-file-image text-info',
            'png': 'fa-file-image text-info',
            'gif': 'fa-file-image text-info',
            'bmp': 'fa-file-image text-info',
            'webp': 'fa-file-image text-info',
            'txt': 'fa-file-alt text-secondary',
            'csv': 'fa-file-csv text-success',
            'zip': 'fa-file-archive text-dark',
            'rar': 'fa-file-archive text-dark',
            '7z': 'fa-file-archive text-dark',
            'tar': 'fa-file-archive text-dark',
            'gz': 'fa-file-archive text-dark',
            'xml': 'fa-file-code text-warning',
            'json': 'fa-file-code text-warning'
        }
        
        return icon_map.get(self.extension.lower(), 'fa-file text-secondary')
    
    @property
    def type_display(self):
        """Retourne le type de fichier en français"""
        type_map = {
            'pdf': 'Document PDF',
            'doc': 'Document Word',
            'docx': 'Document Word',
            'xls': 'Feuille de calcul Excel',
            'xlsx': 'Feuille de calcul Excel',
            'ppt': 'Présentation PowerPoint',
            'pptx': 'Présentation PowerPoint',
            'jpg': 'Image JPEG',
            'jpeg': 'Image JPEG',
            'png': 'Image PNG',
            'gif': 'Image GIF',
            'bmp': 'Image BMP',
            'webp': 'Image WebP',
            'txt': 'Fichier texte',
            'csv': 'Données CSV',
            'zip': 'Archive ZIP',
            'rar': 'Archive RAR',
            '7z': 'Archive 7-Zip',
            'tar': 'Archive TAR',
            'gz': 'Archive GZIP',
            'xml': 'Fichier XML',
            'json': 'Fichier JSON'
        }
        
        return type_map.get(self.extension.lower(), f'Fichier .{self.extension.upper()}')
    
    @property
    def badge_color(self):
        """Retourne la couleur du badge selon le type de fichier"""
        color_map = {
            'pdf': 'danger',
            'doc': 'primary',
            'docx': 'primary',
            'xls': 'success',
            'xlsx': 'success',
            'ppt': 'warning',
            'pptx': 'warning',
            'jpg': 'info',
            'jpeg': 'info',
            'png': 'info',
            'gif': 'info',
            'bmp': 'info',
            'webp': 'info',
            'txt': 'secondary',
            'csv': 'success',
            'zip': 'dark',
            'rar': 'dark',
            '7z': 'dark',
            'tar': 'dark',
            'gz': 'dark',
            'xml': 'warning',
            'json': 'warning'
        }
        
        return color_map.get(self.extension.lower(), 'secondary')
    
    def can_delete(self, user):
        """Vérifie si un utilisateur peut supprimer ce fichier"""
        if not user.is_authenticated:
            return False
        
        # Super admin peut tout supprimer
        if user.role == 'super_admin':
            return True
        
        # Admin client peut supprimer
        if user.role == 'admin':
            return True
        
        # L'uploader peut supprimer son propre fichier
        if self.uploaded_by == user.id:
            return True
        
        # Le créateur de l'audit peut supprimer
        if self.audit and self.audit.created_by == user.id:
            return True
        
        # Le responsable de l'audit peut supprimer
        if self.audit and self.audit.responsable_id == user.id:
            return True
        
        # Membre de l'équipe d'audit peut supprimer
        if self.audit and self.audit.equipe_audit_ids:
            equipe_ids = [int(id_str.strip()) for id_str in self.audit.equipe_audit_ids.split(',') if id_str.strip()]
            if user.id in equipe_ids:
                return True
        
        return False
    
    def can_download(self, user):
        """Vérifie si un utilisateur peut télécharger ce fichier"""
        if not user.is_authenticated:
            return False
        
        # Vérifier l'accès au client
        if user.client_id != self.client_id and user.role != 'super_admin':
            return False
        
        # Si l'utilisateur a accès à l'audit, il peut télécharger les fichiers
        audit = self.audit
        if not audit:
            return False
        
        # Permissions basées sur l'audit
        if user.role == 'super_admin':
            return True
        
        if user.id == audit.created_by or user.id == audit.responsable_id:
            return True
        
        if audit.equipe_audit_ids:
            equipe_ids = [int(id_str.strip()) for id_str in audit.equipe_audit_ids.split(',') if id_str.strip()]
            if user.id in equipe_ids:
                return True
        
        # Observateurs peuvent télécharger
        if audit.observateurs_ids:
            observateur_ids = [int(id_str.strip()) for id_str in audit.observateurs_ids.split(',') if id_str.strip()]
            if user.id in observateur_ids:
                return True
        
        return False
    
    @classmethod
    def get_by_audit(cls, audit_id, user=None):
        """Récupère tous les fichiers d'un audit avec filtrage client"""
        query = cls.query.filter_by(audit_id=audit_id)
        
        # Filtrer par client si l'utilisateur n'est pas super admin
        if user and user.role != 'super_admin':
            if hasattr(cls, 'client_id'):
                query = query.filter(cls.client_id == user.client_id)
        
        return query.order_by(cls.created_at.desc()).all()
    
    @classmethod
    def get_recent_files(cls, limit=10, user=None):
        """Récupère les fichiers récents"""
        query = cls.query
        
        # Filtrer par client si l'utilisateur n'est pas super admin
        if user and user.role != 'super_admin':
            if hasattr(cls, 'client_id'):
                query = query.filter(cls.client_id == user.client_id)
        
        return query.order_by(cls.created_at.desc()).limit(limit).all()
    
    @classmethod
    def get_total_size_by_audit(cls, audit_id):
        """Calcule la taille totale des fichiers d'un audit"""
        total = db.session.query(db.func.sum(cls.taille)).filter_by(audit_id=audit_id).scalar()
        return total or 0
    
    @classmethod
    def get_stats_by_type(cls, user=None):
        """Retourne des statistiques par type de fichier"""
        query = cls.query
        
        # Filtrer par client si l'utilisateur n'est pas super admin
        if user and user.role != 'super_admin':
            if hasattr(cls, 'client_id'):
                query = query.filter(cls.client_id == user.client_id)
        
        stats = query.with_entities(
            cls.type_fichier,
            db.func.count(cls.id).label('count'),
            db.func.sum(cls.taille).label('total_size')
        ).group_by(cls.type_fichier).all()
        
        return [
            {
                'type': stat.type_fichier or 'inconnu',
                'count': stat.count,
                'total_size': stat.total_size or 0,
                'total_size_formatted': cls.format_size(stat.total_size or 0)
            }
            for stat in stats
        ]
    
    @staticmethod
    def format_size(size_bytes):
        """Formatte une taille en octets"""
        if not size_bytes:
            return "0 B"
        
        size = float(size_bytes)
        units = ['B', 'KB', 'MB', 'GB', 'TB']
        unit_index = 0
        
        while size >= 1024 and unit_index < len(units) - 1:
            size /= 1024.0
            unit_index += 1
        
        return f"{size:.1f} {units[unit_index]}"
    
    def to_dict(self):
        """Convertit l'objet en dictionnaire pour API"""
        return {
            'id': self.id,
            'audit_id': self.audit_id,
            'audit_reference': self.audit.reference if self.audit else None,
            'nom_fichier': self.nom_fichier,
            'chemin': self.chemin,
            'type_fichier': self.type_fichier,
            'extension': self.extension,
            'taille': self.taille,
            'taille_formatee': self.taille_formatee,
            'description': self.description,
            'uploaded_by': self.uploaded_by,
            'uploader_username': self.uploader.username if self.uploader else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'date_upload_formatee': self.date_upload_formatee,
            'icon_class': self.icon_class,
            'type_display': self.type_display,
            'badge_color': self.badge_color,
            'url_download': self.url_download,
            'url_delete': self.url_delete,
            'est_image': self.est_image,
            'est_document': self.est_document,
            'est_tableur': self.est_tableur,
            'est_presentation': self.est_presentation,
            'est_archive': self.est_archive
        }
    
    @classmethod
    def create_from_upload(cls, audit_id, file, description=None, uploaded_by=None):
        """Crée un nouveau fichier à partir d'un upload"""
        from werkzeug.utils import secure_filename
        import os
        
        if not file or not hasattr(file, 'filename'):
            raise ValueError("Fichier invalide")
        
        # Sécuriser le nom du fichier
        nom_fichier = secure_filename(file.filename)
        
        # Déterminer le chemin de stockage
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        nom_unique = f"{timestamp}_{nom_fichier}"
        
        # Créer le dossier si nécessaire
        upload_dir = os.path.join('static', 'uploads', 'rapports_audit', str(audit_id))
        os.makedirs(upload_dir, exist_ok=True)
        
        chemin_complet = os.path.join(upload_dir, nom_unique)
        
        # Sauvegarder le fichier
        file.save(chemin_complet)
        
        # Créer l'objet FichierRapport
        fichier = cls(
            audit_id=audit_id,
            nom_fichier=nom_fichier,
            chemin=chemin_complet.replace('\\', '/'),  # Normaliser pour Windows/Linux
            taille=os.path.getsize(chemin_complet),
            description=description,
            uploaded_by=uploaded_by
        )
        
        # Déterminer le client_id depuis l'audit
        from models import Audit
        audit = Audit.query.get(audit_id)
        if audit and hasattr(audit, 'client_id'):
            fichier.client_id = audit.client_id
        
        return fichier
    
    def delete_file(self):
        """Supprime le fichier physique et l'entrée en base"""
        import os
        
        # Supprimer le fichier physique
        if os.path.exists(self.chemin):
            try:
                os.remove(self.chemin)
            except Exception as e:
                print(f"Erreur suppression fichier physique {self.chemin}: {e}")
        
        # Supprimer l'entrée en base
        db.session.delete(self)
        db.session.commit()
        
        return True
    
    def get_preview_url(self):
        """Retourne l'URL de prévisualisation si applicable (pour images)"""
        if self.est_image:
            # Pour les images, on peut retourner le chemin direct
            return self.chemin.replace('static/', '/static/')
        elif self.est_document and self.extension == 'pdf':
            # Pour les PDF, on pourrait utiliser un visualiseur PDF
            return f"/pdf-viewer?file={self.id}"
        return None





# models.py - Ajoutez ces classes
class DispositifMaitrise(db.Model):
    __tablename__ = 'dispositifs_maitrise'
    
    id = db.Column(db.Integer, primary_key=True)
    risque_id = db.Column(db.Integer, db.ForeignKey('risques.id'), nullable=False)
    reference = db.Column(db.String(50), nullable=False)
    nom = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text)
    type_dispositif = db.Column(db.String(100))
    nature = db.Column(db.String(100))
    frequence = db.Column(db.String(100))
    responsable_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    direction_id = db.Column(db.Integer, db.ForeignKey('direction.id'))
    service_id = db.Column(db.Integer, db.ForeignKey('service.id'))
    commentaire_evaluation = db.Column(db.Text)
    reduction_risque_pourcentage = db.Column(db.Float, default=0.0)
    
    # Évaluation du dispositif
    efficacite_attendue = db.Column(db.Integer)
    efficacite_reelle = db.Column(db.Integer)
    couverture = db.Column(db.Integer)
    date_mise_en_place = db.Column(db.Date)
    date_derniere_verification = db.Column(db.Date)
    prochaine_verification = db.Column(db.Date)
    
    # Statut
    statut = db.Column(db.String(50), default='actif')
    justification_statut = db.Column(db.Text)
    
    # Liens avec audit
    audit_id = db.Column(db.Integer, db.ForeignKey('audits.id'))
    
    # SUPPRIMEZ cette ligne si vous passez à la nouvelle relation
    # plan_action_id = db.Column(db.Integer, db.ForeignKey('plans_action.id'))
    
    # Traçabilité
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_archived = db.Column(db.Boolean, default=False)
    archived_at = db.Column(db.DateTime)
    archived_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    # Multi-tenant
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'))
    
    # Relations
    risque = db.relationship('Risque', back_populates='dispositifs_maitrise')
    responsable = db.relationship('User', foreign_keys=[responsable_id])
    direction = db.relationship('Direction')
    service = db.relationship('Service')
    audit = db.relationship('Audit')
    
    # NOUVELLE RELATION plusieurs-à-plusieurs (seule)
    plans_action = db.relationship('PlanAction',
                                   secondary='plan_dispositifs',
                                   back_populates='dispositifs',  # Correspond à ce qui est dans PlanAction
                                   lazy='dynamic')
    
    createur = db.relationship('User', foreign_keys=[created_by])
    archive_user = db.relationship('User', foreign_keys=[archived_by])
    client = db.relationship('Client')
    
    # Documentation
    documents = db.relationship('DocumentDispositif', back_populates='dispositif', cascade='all, delete-orphan')
    verifications = db.relationship('VerificationDispositif', back_populates='dispositif', cascade='all, delete-orphan')
     # ⭐ MÉTHODE DE GÉNÉRATION
    __table_args__ = (
        db.UniqueConstraint('reference', 'client_id', name='uix_dispositif_reference_client'),
    )
    @staticmethod
    def generer_reference(client_id):
        from datetime import datetime
        annee = datetime.now().year
        prefixe = f"DISP-{annee}-"
        
        count = DispositifMaitrise.query.filter(
            DispositifMaitrise.reference.like(f'{prefixe}%'),
            DispositifMaitrise.client_id == client_id
        ).count()
        
        return f"{prefixe}{(count + 1):04d}"
    
    def __repr__(self):
        return f'<DispositifMaitrise {self.reference}: {self.nom}>'

    def get_reduction_risque_conforme(self):
        """
        Calcul conforme ISO 31000 avec logique réaliste
        Un dispositif parfait (5/5 + 5/5) devrait approcher la réduction max du type
        """
        if not self.efficacite_reelle or not self.couverture:
            return 0.0
        
        # 1. RÉDUCTION MAX PAR TYPE (normes sectorielles)
        reduction_max_par_type = {
            'Préventif': 75,   # Peut éviter la survenance jusqu'à 75%
            'Détectif': 60,    # Bonne détection peut réduire impact jusqu'à 60%
            'Correctif': 45,   # Correction rapide peut limiter jusqu'à 45%
            'Dirigeant': 30    # Cadre de contrôle jusqu'à 30%
        }
        
        # 2. SCORE DE BASE SUR 100 (efficacité 60%, couverture 40%)
        efficacite_norm = self.efficacite_reelle / 5  # 0-1
        couverture_norm = self.couverture / 5         # 0-1
        score_base = (efficacite_norm * 60) + (couverture_norm * 40)  # /100
        
        # 3. APPLIQUER LE SCORE À LA RÉDUCTION MAX
        type_dispositif = self.type_dispositif or 'Correctif'
        reduction_max = reduction_max_par_type.get(type_dispositif, 45)
        reduction_calcul = (score_base / 100) * reduction_max
        
        # 4. FACTEURS MODÉRATEURS (beaucoup plus réalistes)
        facteurs = {
            'nature': {
                'Automatique': 1.0,      # Pas de pénalité pour automatique
                'Technique': 0.95,       # Légère réduction
                'Procédurale': 0.85,     # Procédure bien appliquée
                'Organisationnelle': 0.80,
                'Humaine': 0.75,
                None: 0.85
            },
            'frequence': {
                'Permanente': 1.0,       # Surveillance permanente
                'Continue': 0.95,        # Continue mais non permanente
                'Temps réel': 0.95,      # Temps réel
                'Quotidienne': 0.90,     # Quotidien
                'Hebdomadaire': 0.85,    # Hebdomadaire
                'Mensuelle': 0.75,       # Mensuel
                'Trimestrielle': 0.65,   # Trimestriel
                'Annuelle': 0.55,        # Annuel
                'Exceptionnelle': 0.45,  # Exceptionnel
                None: 0.75
            }
        }
        
        facteur_nature = facteurs['nature'].get(self.nature or 'Procédurale', 0.85)
        facteur_frequence = facteurs['frequence'].get(self.frequence or 'Mensuelle', 0.75)
        
        # 5. RÉDUCTION FINALE (facteurs moins pénalisants)
        reduction_finale = reduction_calcul * facteur_nature * facteur_frequence
        
        # Garantir un minimum pour un dispositif parfait
        if self.efficacite_reelle == 5 and self.couverture == 5:
            # Un dispositif parfait devrait donner au moins 80% de la réduction max
            reduction_finale = max(reduction_finale, reduction_max * 0.8)
        
        return round(min(reduction_finale, reduction_max), 1)

    def get_reduction_risque_detaille(self):
        """
        Retourne le calcul détaillé avec explications
        Version améliorée avec facteurs plus réalistes
        """
        details = {}
        
        # 1. RÉDUCTION MAX PAR TYPE (normes sectorielles)
        reduction_max_par_type = {
            'Préventif': 75,
            'Détectif': 60,
            'Correctif': 45,
            'Dirigeant': 30
        }
        
        type_dispositif = self.type_dispositif or 'Correctif'
        details['reduction_max_type'] = reduction_max_par_type.get(type_dispositif, 45)
        details['type'] = type_dispositif
        
        # 2. SCORES DE BASE
        details['efficacite'] = self.efficacite_reelle or 0
        details['couverture'] = self.couverture or 0
        details['efficacite_norm'] = (self.efficacite_reelle or 0) / 5
        details['couverture_norm'] = (self.couverture or 0) / 5
        
        # 3. SCORE PONDÉRÉ
        details['score_pondere'] = (details['efficacite_norm'] * 60) + (details['couverture_norm'] * 40)
        details['reduction_calcul'] = (details['score_pondere'] / 100) * details['reduction_max_type']
        
        # 4. FACTEURS MODÉRATEURS
        facteurs_nature = {
            'Automatique': 1.0, 'Technique': 0.98, 'Logiciel': 0.98,
            'Matériel': 0.97, 'Procédurale': 0.95, 'Organisationnelle': 0.92,
            'Humaine': 0.88, 'Manuel': 0.88, 'Mixte': 0.95
        }
        
        facteurs_frequence = {
            'Permanente': 1.0, 'Continue': 0.98, 'Temps réel': 0.98,
            'Quotidienne': 0.95, 'Hebdomadaire': 0.92, 'Mensuelle': 0.88,
            'Trimestrielle': 0.82, 'Semestrielle': 0.76, 'Annuelle': 0.70,
            'Exceptionnelle': 0.60
        }
        
        # Mapping des valeurs
        nature_map = {
            'manuel': 'Manuel', 'automatique': 'Automatique', 'technique': 'Technique',
            'procédurale': 'Procédurale', 'organisationnelle': 'Organisationnelle',
            'humaine': 'Humaine', 'mixte': 'Mixte'
        }
        
        frequence_map = {
            'permanent': 'Permanente', 'continu': 'Continue', 'temps réel': 'Temps réel',
            'quotidien': 'Quotidienne', 'hebdomadaire': 'Hebdomadaire', 'mensuel': 'Mensuelle',
            'trimestriel': 'Trimestrielle', 'semestriel': 'Semestrielle', 'annuel': 'Annuelle'
        }
        
        # Normalisation
        nature_normalisee = nature_map.get(str(self.nature).lower() if self.nature else '', 'Procédurale')
        frequence_normalisee = frequence_map.get(str(self.frequence).lower() if self.frequence else '', 'Mensuelle')
        
        details['nature'] = nature_normalisee
        details['frequence'] = frequence_normalisee
        details['facteur_nature'] = facteurs_nature.get(nature_normalisee, 0.92)
        details['facteur_frequence'] = facteurs_frequence.get(frequence_normalisee, 0.85)
        
        # 5. CALCUL FINAL
        facteur_global = (details['facteur_nature'] * details['facteur_frequence']) ** 0.5
        details['facteur_global'] = round(facteur_global, 3)
        details['reduction_finale'] = details['reduction_calcul'] * facteur_global
        
        # 6. BONUS (BIEN INDENTÉ)
        if details['efficacite'] == 5 and details['couverture'] == 5:
            seuil_min = details['reduction_max_type'] * 0.85
            if details['reduction_finale'] < seuil_min:
                details['reduction_finale'] = seuil_min
                details['bonus_applique'] = True
            details['garantie_minimum'] = True
            details['bonus_applique'] = False  # Initialisé
        elif details['efficacite'] >= 4 and details['couverture'] >= 4:
            if details['reduction_finale'] < details['reduction_max_type'] * 0.7:
                details['reduction_finale'] = details['reduction_max_type'] * 0.7
                details['bonus_applique'] = True
            details['garantie_minimum'] = False
        else:
            details['garantie_minimum'] = False
            details['bonus_applique'] = False
        
        # 7. LIMITES
        details['reduction_finale'] = min(details['reduction_finale'], details['reduction_max_type'])
        details['reduction_finale'] = max(details['reduction_finale'], 0)
        details['reduction_finale'] = round(details['reduction_finale'], 1)
        
        # 8. NIVEAU D'IMPACT
        if details['reduction_finale'] >= details['reduction_max_type'] * 0.8:
            details['niveau_impact'] = 'TRÈS ÉLEVÉ'
            details['classe_impact'] = 'success'
            details['icone_impact'] = 'fa-check-circle'
        elif details['reduction_finale'] >= details['reduction_max_type'] * 0.6:
            details['niveau_impact'] = 'ÉLEVÉ'
            details['classe_impact'] = 'success'
            details['icone_impact'] = 'fa-check-circle'
        elif details['reduction_finale'] >= details['reduction_max_type'] * 0.4:
            details['niveau_impact'] = 'MODÉRÉ'
            details['classe_impact'] = 'warning'
            details['icone_impact'] = 'fa-exclamation-triangle'
        elif details['reduction_finale'] >= details['reduction_max_type'] * 0.2:
            details['niveau_impact'] = 'FAIBLE'
            details['classe_impact'] = 'danger'
            details['icone_impact'] = 'fa-times-circle'
        else:
            details['niveau_impact'] = 'TRÈS FAIBLE'
            details['classe_impact'] = 'danger'
            details['icone_impact'] = 'fa-times-circle'
        
        return details

    @classmethod
    def get_benchmark_dispositifs(cls, client_id=None, type_dispositif=None):
        """
        Compare les dispositifs entre eux pour identifier les tendances
        """
        query = cls.query
        
        if client_id:
            query = query.filter_by(client_id=client_id)
        if type_dispositif:
            query = query.filter_by(type_dispositif=type_dispositif)
        
        dispositifs = query.all()
        
        stats = {
            'total': len(dispositifs),
            'par_type': {},
            'efficacite_moyenne': 0,
            'couverture_moyenne': 0,
            'reduction_moyenne': 0,
            'top_performers': [],
            'a_ameliorer': [],
            'sans_evaluation': [],
            'avec_plans': 0  # AJOUT
        }
        
        total_efficacite = 0
        total_couverture = 0
        total_reduction = 0
        count_evalue = 0
        
        for d in dispositifs:
            # Stats par type
            if d.type_dispositif not in stats['par_type']:
                stats['par_type'][d.type_dispositif] = 0
            stats['par_type'][d.type_dispositif] += 1
            
            # Compter les dispositifs avec plans
            if hasattr(d, 'plans_action_lies') and d.plans_action_lies.count() > 0:
                stats['avec_plans'] += 1
            
            # Moyennes
            if d.efficacite_reelle:
                total_efficacite += d.efficacite_reelle
                total_couverture += (d.couverture or 0)
                reduction = d.get_reduction_risque_detaille()['reduction_finale']
                total_reduction += reduction
                count_evalue += 1
                
                # Classification
                if d.efficacite_reelle >= 4:
                    stats['top_performers'].append({
                        'id': d.id,
                        'reference': d.reference,
                        'nom': d.nom,
                        'type': d.type_dispositif,
                        'efficacite': d.efficacite_reelle,
                        'reduction': reduction,
                        'plans_count': d.plans_action_lies.count() if hasattr(d, 'plans_action_lies') else 0
                    })
                elif d.efficacite_reelle < 3:
                    stats['a_ameliorer'].append({
                        'id': d.id,
                        'reference': d.reference,
                        'nom': d.nom,
                        'efficacite': d.efficacite_reelle,
                        'ecart': (d.efficacite_attendue or 3) - d.efficacite_reelle,
                        'plans_count': d.plans_action_lies.count() if hasattr(d, 'plans_action_lies') else 0
                    })
            else:
                stats['sans_evaluation'].append({
                    'id': d.id,
                    'reference': d.reference,
                    'nom': d.nom
                })
        
        if count_evalue > 0:
            stats['efficacite_moyenne'] = round(total_efficacite / count_evalue, 1)
            stats['couverture_moyenne'] = round(total_couverture / count_evalue, 1)
            stats['reduction_moyenne'] = round(total_reduction / count_evalue, 1)
        
        # Ajouter les statistiques manquantes pour le template
        stats['non_evalues'] = len(stats['sans_evaluation'])
        stats['non_efficaces'] = len([d for d in dispositifs if d.efficacite_reelle and d.efficacite_reelle < 4])
        
        return stats
    
    def get_plans_action(self):
        """
        Retourne tous les plans d'action liés à ce dispositif
        """
        if hasattr(self, 'plans_action_lies'):
            return self.plans_action_lies.all()
        return []

    def get_matrice_criticite(self):
        """
        Analyse la criticité du dispositif selon plusieurs dimensions
        Retourne une matrice de décision
        """
        details = self.get_reduction_risque_detaille()
        impact = self.get_impact_coso()
        
        # Calcul du score de criticité (0-100)
        score_efficacite = (self.efficacite_reelle or 0) * 20  # 0-100
        score_couverture = (self.couverture or 0) * 20        # 0-100
        score_urgence = 100 - ((score_efficacite + score_couverture) / 2)
        
        # CORRECTION: Remplacer get_niveau_brut() par une valeur par défaut
        # Niveau de risque résiduel
        if self.risque:
            # Si votre modèle Risque a un champ 'niveau' ou 'criticite'
            risque_initial = getattr(self.risque, 'niveau', 3)  # Valeur par défaut 3
            # Ou si vous avez une méthode existante
            if hasattr(self.risque, 'get_niveau'):
                risque_initial = self.risque.get_niveau()
            elif hasattr(self.risque, 'get_criticite'):
                risque_initial = self.risque.get_criticite()
        else:
            risque_initial = 3
        
        reduction = details['reduction_finale'] / 100
        risque_residuel = max(1, round(risque_initial * (1 - reduction)))
        
        # Facteurs aggravants
        facteurs_aggravants = []
        if self.date_derniere_verification:
            jours_depuis = (datetime.now().date() - self.date_derniere_verification).days
            if jours_depuis > 365:
                facteurs_aggravants.append("Non vérifié depuis plus d'un an")
        if self.statut != 'actif':
            facteurs_aggravants.append(f"Statut: {self.statut}")
        if not self.responsable:
            facteurs_aggravants.append("Aucun responsable assigné")
        
        return {
            'urgence': min(100, max(0, score_urgence)),
            'criticite': 'CRITIQUE' if score_urgence > 70 else 'ÉLEVÉE' if score_urgence > 50 else 'MODÉRÉE' if score_urgence > 30 else 'FAIBLE',
            'risque_initial': risque_initial,
            'risque_residuel': risque_residuel,
            'reduction_reelle': details['reduction_finale'],
            'facteurs_aggravants': facteurs_aggravants,
            'recommandation': self.get_recommandation_automatique()
        }

    def get_recommandation_automatique(self):
        """Génère une recommandation automatique basée sur l'analyse"""
        if not self.efficacite_reelle:
            return "🔴 ÉVALUATION REQUISE - Évaluez ce dispositif d'urgence"
        
        if self.efficacite_reelle < self.efficacite_attendue:
            if self.efficacite_attendue - self.efficacite_reelle >= 2:
                return "🔴 ACTION IMMÉDIATE - Écart critique, plan d'action urgent"
            else:
                return "🟠 AMÉLIORATION NÉCESSAIRE - Plan d'action à programmer"
        
        if self.prochaine_verification:
            jours_restants = (self.prochaine_verification - datetime.now().date()).days
            if jours_restants < 0:
                return f"🔴 VÉRIFICATION EN RETARD de {abs(jours_restants)} jours"
            elif jours_restants < 30:
                return f"🟠 VÉRIFICATION PROCHAINE dans {jours_restants} jours"
        
        return "🟢 CONFORME - Surveillance normale"

    def get_impact_coso(self):
        """
        Retourne l'analyse d'impact selon les normes COSO
        Basé sur l'échelle : 5/5=90-100%, 4/5=70-89%, 3/5=50-69%, 2/5=30-49%, 1/5=<30%
        """
        if not self.efficacite_reelle:
            return {
                'niveau': 'Non évalué',
                'classe': 'secondary',
                'icone': 'fa-question-circle',
                'description': 'Évaluez le dispositif pour déterminer son impact',
                'action': 'Évaluation requise'
            }
        
        # Calculer le pourcentage d'efficacité
        efficacite_pct = (self.efficacite_reelle / 5) * 100
        
        # Déterminer le niveau selon l'échelle COSO
        if efficacite_pct >= 90:
            return {
                'niveau': '🔒 CONTRÔLE ROBUSTE',
                'classe': 'success',
                'icone': 'fa-check-circle',
                'description': 'Automatisé ou formalisé, traçabilité complète, aucune défaillance constatée',
                'action': 'Maintenir - Surveillance normale',
                'score': efficacite_pct,
                'etoiles': 5
            }
        elif efficacite_pct >= 70:
            return {
                'niveau': '✅ CONTRÔLE FORT',
                'classe': 'info',
                'icone': 'fa-check-circle',
                'description': 'Fiable mais avec quelques faiblesses mineures',
                'action': 'Optimiser - Améliorations mineures possibles',
                'score': efficacite_pct,
                'etoiles': 4
            }
        elif efficacite_pct >= 50:
            return {
                'niveau': '⚠️ CONTRÔLE MODÉRÉ',
                'classe': 'warning',
                'icone': 'fa-exclamation-triangle',
                'description': 'Des déficiences mais compensées',
                'action': 'Surveiller - Plan d\'action à prévoir',
                'score': efficacite_pct,
                'etoiles': 3
            }
        elif efficacite_pct >= 30:
            return {
                'niveau': '🔴 CONTRÔLE FAIBLE',
                'classe': 'danger',
                'icone': 'fa-times-circle',
                'description': 'Déficiences significatives',
                'action': 'CORRIGER - Plan d\'action urgent',
                'score': efficacite_pct,
                'etoiles': 2
            }
        else:
            return {
                'niveau': '⛔ CONTRÔLE INEXISTANT',
                'classe': 'dark',
                'icone': 'fa-times-circle',
                'description': 'Contrôle inexistant ou totalement inefficace',
                'action': 'CRÉER - Action immédiate',
                'score': efficacite_pct,
                'etoiles': 1
            }

    def stress_test(self, scenario='severe'):
        """
        Simule l'efficacité du dispositif dans des conditions extrêmes
        Scénarios: 'modere', 'severe', 'extreme'
        """
        if not self.efficacite_reelle:
            return {'error': 'Dispositif non évalué'}
        
        details = self.get_reduction_risque_detaille()
        
        # Coefficients de stress par scénario
        scenarios = {
            'modere': {
                'nom': '🌧️ Modéré',
                'facteur_efficacite': 0.8,   # Perte de 20% d'efficacité
                'facteur_couverture': 0.85,   # Perte de 15% de couverture
                'couleur': 'warning',
                'description': 'Perturbation modérée (panne partielle, absence temporaire)'
            },
            'severe': {
                'nom': '⚡ Sévère',
                'facteur_efficacite': 0.5,    # Perte de 50% d'efficacité
                'facteur_couverture': 0.6,     # Perte de 40% de couverture
                'couleur': 'danger',
                'description': 'Perturbation sévère (panne majeure, absence prolongée)'
            },
            'extreme': {
                'nom': '🔥 Extrême',
                'facteur_efficacite': 0.2,    # Perte de 80% d'efficacité
                'facteur_couverture': 0.3,     # Perte de 70% de couverture
                'couleur': 'dark',
                'description': 'Situation catastrophique (sinistre, crise majeure)'
            }
        }
        
        config = scenarios.get(scenario, scenarios['severe'])
        
        # Calcul sous stress
        efficacite_stressee = (self.efficacite_reelle or 0) * config['facteur_efficacite']
        couverture_stressee = (self.couverture or 0) * config['facteur_couverture']
        
        # Sauvegarder les valeurs originales pour restauration
        efficacite_originale = self.efficacite_reelle
        couverture_originale = self.couverture
        
        # Appliquer temporairement les valeurs stressées
        self.efficacite_reelle = efficacite_stressee
        self.couverture = couverture_stressee
        
        # Calculer la réduction sous stress
        details_stress = self.get_reduction_risque_detaille()
        
        # Restaurer les valeurs originales
        self.efficacite_reelle = efficacite_originale
        self.couverture = couverture_originale
        
        # Calcul des impacts
        reduction_normale = details['reduction_finale']
        reduction_stress = details_stress['reduction_finale']
        perte = reduction_normale - reduction_stress
        
        # Déterminer la résilience
        if perte < 10:
            resilience = "🛡️ EXCELLENTE"
            conseil = "Le dispositif résiste très bien au stress"
        elif perte < 25:
            resilience = "👍 BONNE"
            conseil = "Le dispositif résiste bien, mais des améliorations sont possibles"
        elif perte < 50:
            resilience = "⚠️ MODÉRÉE"
            conseil = "Le dispositif montre des faiblesses en conditions de stress"
        else:
            resilience = "🔴 FAIBLE"
            conseil = "Le dispositif est vulnérable - Plan de continuité recommandé"
        
        return {
            'scenario': config['nom'],
            'couleur': config['couleur'],
            'description_scenario': config['description'],
            'efficacite_normale': round(efficacite_originale, 1),
            'efficacite_stress': round(efficacite_stressee, 1),
            'couverture_normale': round(couverture_originale, 1),
            'couverture_stress': round(couverture_stressee, 1),
            'reduction_normale': reduction_normale,
            'reduction_stress': reduction_stress,
            'perte': round(perte, 1),
            'perte_pourcentage': round((perte / reduction_normale * 100) if reduction_normale > 0 else 0, 1),
            'resilience': resilience,
            'conseil': conseil,
            'risque_residuel': max(1, round(3 * (1 - reduction_stress/100)))  # Estimation
        }

    def stress_test_avance(self):
        """Version complète avec 15 scénarios de stress"""
        
        scenarios = {
            # CYBERSÉCURITÉ
            'cyber_ransomware': {
                'nom': '💣 Ransomware',
                'facteur_humain': 0.2,
                'facteur_technique': 0.1,
                'duree': '7 jours',
                'description': 'Chiffrement des données, systèmes bloqués, demande de rançon'
            },
            'cyber_ddos': {
                'nom': '🌐 DDoS',
                'facteur_humain': 0.8,
                'facteur_technique': 0.3,
                'duree': '48h',
                'description': 'Indisponibilité réseau, perte de connectivité externe'
            },
            'cyber_phishing': {
                'nom': '🎣 Phishing ciblé',
                'facteur_humain': 0.4,
                'facteur_technique': 0.6,
                'duree': '72h',
                'description': 'Compromission comptes utilisateurs, fuite de données'
            },
            'cyber_physique': {
                'nom': '🔌 Intrusion physique',
                'facteur_humain': 0.5,
                'facteur_technique': 0.4,
                'duree': '1 semaine',
                'description': 'Accès non autorisé aux serveurs, sabotage matériel'
            },
            
            # RESSOURCES HUMAINES
            'humain_grève': {
                'nom': '⚡ Grève générale',
                'facteur_humain': 0.2,
                'facteur_technique': 0.9,
                'duree': '2 semaines',
                'description': '80% du personnel absent, mouvements sociaux'
            },
            'humain_pandémie': {
                'nom': '🦠 Pandémie',
                'facteur_humain': 0.3,
                'facteur_technique': 0.8,
                'duree': '1 mois',
                'description': '50% d\'absentéisme, télétravail imposé'
            },
            'humain_départ_masse': {
                'nom': '🏃 Départs simultanés',
                'facteur_humain': 0.2,
                'facteur_technique': 0.7,
                'duree': '3 mois',
                'description': 'Perte des compétences clés, passation impossible'
            },
            'humain_erreur': {
                'nom': '❌ Erreur humaine majeure',
                'facteur_humain': 0.3,
                'facteur_technique': 0.8,
                'duree': '1 semaine',
                'description': 'Manipulation erronée, perte de données critique'
            },
            
            # TECHNIQUE & INFRASTRUCTURE
            'tech_panne_elec': {
                'nom': '⚡ Panne électrique',
                'facteur_humain': 0.9,
                'facteur_technique': 0.2,
                'duree': '72h',
                'description': 'Coupure générale, groupes électrogènes hors service'
            },
            'tech_incendie': {
                'nom': '🔥 Incendie',
                'facteur_humain': 0.6,
                'facteur_technique': 0.2,
                'duree': '1 mois',
                'description': 'Destruction partielle datacenter, perte matérielle'
            },
            'tech_panne_reseau': {
                'nom': '🌍 Panne réseau',
                'facteur_humain': 0.8,
                'facteur_technique': 0.3,
                'duree': '48h',
                'description': 'Fibre optique coupée, indisponibilité totale'
            },
            'tech_obsolescence': {
                'nom': '📉 Obsolescence',
                'facteur_humain': 0.7,
                'facteur_technique': 0.4,
                'duree': 'Permanent',
                'description': 'Matériel non supporté, vulnérabilités critiques'
            },
            
            # CATASTROPHES NATURELLES
            'naturel_inondation': {
                'nom': '🌊 Inondation',
                'facteur_humain': 0.5,
                'facteur_technique': 0.3,
                'duree': '3 semaines',
                'description': 'Locaux inaccessibles, matériel détruit'
            },
            'naturel_seisme': {
                'nom': '🏚️ Séisme',
                'facteur_humain': 0.4,
                'facteur_technique': 0.2,
                'duree': '2 mois',
                'description': 'Bâtiment endommagé, infrastructure instable'
            },
            'naturel_tempete': {
                'nom': '🌪️ Tempête',
                'facteur_humain': 0.6,
                'facteur_technique': 0.4,
                'duree': '1 semaine',
                'description': 'Dégâts toiture, lignes électriques coupées'
            },
            
            # FINANCIER
            'finance_crise': {
                'nom': '📉 Crise financière',
                'facteur_humain': 0.5,
                'facteur_technique': 0.6,
                'duree': '6 mois',
                'description': 'Budget réduit 50%, gel des investissements'
            },
            'finance_fournisseur': {
                'nom': '🏭 Faillite fournisseur',
                'facteur_humain': 0.6,
                'facteur_technique': 0.5,
                'duree': '3 mois',
                'description': 'Fournisseur critique en cessation d\'activité'
            },
            'finance_fraude': {
                'nom': '💰 Fraude interne',
                'facteur_humain': 0.3,
                'facteur_technique': 0.5,
                'duree': '1 mois',
                'description': 'Détournement de fonds, contrôles contournés'
            },
            
            # RÉGLEMENTAIRE
            'legal_conformite': {
                'nom': '📜 Nouvelle réglementation',
                'facteur_humain': 0.5,
                'facteur_technique': 0.5,
                'duree': '30 jours',
                'description': 'Mise en conformité urgente, risques de sanctions'
            },
            'legal_contentieux': {
                'nom': '⚖️ Contentieux majeur',
                'facteur_humain': 0.4,
                'facteur_technique': 0.6,
                'duree': '1 an',
                'description': 'Procès, gel des activités, saisie possible'
            },
            'legal_audit': {
                'nom': '🔍 Audit surprise',
                'facteur_humain': 0.4,
                'facteur_technique': 0.5,
                'duree': '1 semaine',
                'description': 'Contrôle inopiné, sanctions potentielles'
            }
        }
        
        # Si le dispositif n'est pas évalué
        if not self.efficacite_reelle:
            resultats = {}
            for key, scenario in scenarios.items():
                resultats[key] = {
                    'scenario': scenario['nom'],
                    'efficacite': 0,
                    'facteur': 0,
                    'duree': scenario['duree'],
                    'description': scenario['description']
                }
            return resultats
        
        # Calcul pour tous les scénarios
        resultats = {}
        for key, scenario in scenarios.items():
            # Ponderer selon la nature du dispositif
            nature = (self.nature or '').lower()
            
            if 'automatique' in nature or 'technique' in nature or 'logiciel' in nature:
                facteur_global = scenario['facteur_technique']
            elif 'humain' in nature or 'manuel' in nature or 'procédurale' in nature:
                facteur_global = scenario['facteur_humain']
            else:
                facteur_global = (scenario['facteur_humain'] + scenario['facteur_technique']) / 2
            
            efficacite_stress = (self.efficacite_reelle or 0) * facteur_global
            resultats[key] = {
                'scenario': scenario['nom'],
                'efficacite': round(efficacite_stress, 1),
                'facteur': round(facteur_global, 2),
                'duree': scenario['duree'],
                'description': scenario['description']
            }
        
        return resultats

    def get_score_resilience(self):
        """Calcule un score de résilience global"""
        try:
            tests = self.stress_test_avance()
            
            scores = []
            for resultat in tests.values():
                scores.append(resultat['efficacite'])
            
            if not scores:
                return "NON ÉVALUÉ", 0
            
            resilience_moyenne = sum(scores) / len(scores)
            
            if resilience_moyenne >= 4:
                return "🟢 EXCELLENTE", resilience_moyenne
            elif resilience_moyenne >= 3:
                return "🟡 BONNE", resilience_moyenne
            elif resilience_moyenne >= 2:
                return "🟠 MODÉRÉE", resilience_moyenne
            else:
                return "🔴 FAIBLE", resilience_moyenne
        except Exception as e:
            print(f"Erreur calcul résilience: {e}")
            return "ERREUR", 0

    def get_niveau_efficacite(self):
        """Retourne le niveau d'efficacité basé sur l'écart entre attendu et réel"""
        if self.efficacite_attendue and self.efficacite_reelle:
            ecart = self.efficacite_attendue - self.efficacite_reelle
            if ecart <= 0:
                return 'Satisfaisant'
            elif ecart == 1:
                return 'À améliorer'
            else:
                return 'Insuffisant'
        return 'Non évalué'




class DocumentDispositif(db.Model):
    __tablename__ = 'documents_dispositif'
    
    id = db.Column(db.Integer, primary_key=True)
    dispositif_id = db.Column(db.Integer, db.ForeignKey('dispositifs_maitrise.id'), nullable=False)
    nom_fichier = db.Column(db.String(300))
    type_document = db.Column(db.String(100))  # Procédure, Mode opératoire, Fiche de contrôle, etc.
    description = db.Column(db.Text)
    chemin_fichier = db.Column(db.String(500))
    taille = db.Column(db.Integer)  # En octets
    
    uploaded_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'))
    
    # Relations
    dispositif = db.relationship('DispositifMaitrise', back_populates='documents')
    uploader = db.relationship('User')


class VerificationDispositif(db.Model):
    __tablename__ = 'verifications_dispositif'
    
    id = db.Column(db.Integer, primary_key=True)
    dispositif_id = db.Column(db.Integer, db.ForeignKey('dispositifs_maitrise.id'), nullable=False)
    date_verification = db.Column(db.Date, nullable=False)
    type_verification = db.Column(db.String(100))  # Test, Observation, Revue documentaire
    resultat = db.Column(db.String(50))  # Conforme, Non conforme, À corriger
    commentaire = db.Column(db.Text)
    fichiers_preuves = db.Column(db.String(500))  # CSV de chemins de fichiers
    
    verificateur_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'))
    
    # Relations
    dispositif = db.relationship('DispositifMaitrise', back_populates='verifications')
    verificateur = db.relationship('User')


class Article(db.Model):
    __tablename__ = 'articles'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Informations de base
    titre = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(200), unique=True, nullable=False)  # ← OBLIGATOIRE pour l'URL
    accroche = db.Column(db.String(300))
    contenu = db.Column(db.Text, nullable=False)
    excerpt = db.Column(db.String(300))  # Résumé pour les listings
    
    # Images
    image_principale = db.Column(db.String(500), default='/static/images/blog/default-article.jpg')
    image_og = db.Column(db.String(500), default='/static/images/blog/default-og.jpg')
    
    # Catégorie et tags
    categorie_id = db.Column(db.Integer, db.ForeignKey('categories.id'))
    categorie = db.relationship('Categorie', backref='articles')
    tags = db.Column(db.String(500))  # Stocké comme "tag1,tag2,tag3"
    
    # Auteur
    auteur_id = db.Column(db.Integer, db.ForeignKey('auteurs.id'))
    auteur = db.relationship('Auteur', backref='articles')
    
    # Dates (TRÈS IMPORTANT pour le sitemap)
    date_publication = db.Column(db.DateTime, default=datetime.utcnow)
    date_modification = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)  # ← OPTIONNEL mais RECOMMANDÉ
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Statistiques et statut
    est_publie = db.Column(db.Boolean, default=True)  # ← OBLIGATOIRE (pour filtrer)
    est_supprime = db.Column(db.Boolean, default=False)
    nb_vues = db.Column(db.Integer, default=0)
    temps_lecture = db.Column(db.Integer, default=5)  # en minutes
    
    # SEO
    meta_description = db.Column(db.String(300))
    meta_keywords = db.Column(db.String(500))
    
    def __repr__(self):
        return f'<Article {self.titre}>'
    
    @property
    def url(self):
        return f"/blog/{self.slug}"
    
    @property
    def tags_list(self):
        if self.tags:
            return self.tags.split(',')
        return []

class Auteur(db.Model):
    __tablename__ = 'auteurs'
    
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    prenom = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(200), unique=True)
    email = db.Column(db.String(200))
    bio = db.Column(db.Text)
    bio_courte = db.Column(db.String(300))
    fonction = db.Column(db.String(200))
    image = db.Column(db.String(500), default='/static/images/authors/default.jpg')
    experience = db.Column(db.Integer, default=0)  # années d'expérience
    
    def __repr__(self):
        return f'{self.prenom} {self.nom}'
    
    @property
    def nom_complet(self):
        return f"{self.prenom} {self.nom}"


class Categorie(db.Model):
    __tablename__ = 'categories'
    
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False, unique=True)
    slug = db.Column(db.String(200), unique=True)
    description = db.Column(db.String(500))
    
    def __repr__(self):
        return self.nom


class CommentairePlanAction(db.Model):
    __tablename__ = 'commentaires_plan_action'
    
    id = db.Column(db.Integer, primary_key=True)
    plan_action_id = db.Column(db.Integer, db.ForeignKey('plans_action.id'), nullable=False)
    sous_action_id = db.Column(db.Integer, db.ForeignKey('sous_actions.id'), nullable=True)
    utilisateur_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    contenu = db.Column(db.Text, nullable=False)
    type_contenu = db.Column(db.String(20), default='commentaire')  # commentaire, note, mise_a_jour
    est_prive = db.Column(db.Boolean, default=False)
    tags = db.Column(db.JSON)  # ['important', 'question', 'blocage', 'réussite']
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)
    
    # Relations
    plan_action = db.relationship('PlanAction', backref=db.backref('commentaires', lazy=True, cascade='all, delete-orphan'))
    sous_action = db.relationship('SousAction', backref=db.backref('commentaires', lazy=True))
    utilisateur = db.relationship('User')
    
    def to_dict(self):
        return {
            'id': self.id,
            'plan_action_id': self.plan_action_id,
            'sous_action_id': self.sous_action_id,
            'utilisateur': {
                'id': self.utilisateur.id,
                'username': self.utilisateur.username,
                'email': self.utilisateur.email,
                'avatar': f"https://ui-avatars.com/api/?name={self.utilisateur.username}&background=random"
            },
            'contenu': self.contenu,
            'type_contenu': self.type_contenu,
            'est_prive': self.est_prive,
            'tags': self.tags or [],
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'date_formatee': self.created_at.strftime('%d/%m/%Y à %H:%M'),
            'fichiers': [f.to_dict() for f in self.fichiers]
        }

class FichierPlanAction(db.Model):
    __tablename__ = 'fichiers_plan_action'
    
    id = db.Column(db.Integer, primary_key=True)
    commentaire_id = db.Column(db.Integer, db.ForeignKey('commentaires_plan_action.id'), nullable=True)
    plan_action_id = db.Column(db.Integer, db.ForeignKey('plans_action.id'), nullable=False)
    sous_action_id = db.Column(db.Integer, db.ForeignKey('sous_actions.id'), nullable=True)
    nom_fichier = db.Column(db.String(255), nullable=False)
    chemin = db.Column(db.String(500), nullable=False)
    type_fichier = db.Column(db.String(50))
    taille = db.Column(db.Integer)  # en octets
    description = db.Column(db.Text)
    uploaded_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)
    
    # Relations
    commentaire = db.relationship('CommentairePlanAction', backref=db.backref('fichiers', lazy=True, cascade='all, delete-orphan'))
    plan_action = db.relationship('PlanAction', backref=db.backref('fichiers', lazy=True))
    sous_action = db.relationship('SousAction', backref=db.backref('fichiers', lazy=True))
    uploader = db.relationship('User')
    
    def to_dict(self):
        return {
            'id': self.id,
            'nom_fichier': self.nom_fichier,
            'type_fichier': self.type_fichier,
            'taille': self.taille_formatee,
            'description': self.description,
            'uploaded_by': self.uploader.username,
            'uploaded_by_id': self.uploaded_by,
            'created_at': self.created_at.isoformat(),
            'date_formatee': self.created_at.strftime('%d/%m/%Y %H:%M'),
            'url_download': f"/plan-action/fichier/{self.id}/telecharger",
            'url_preview': self.get_preview_url(),
            'icon_class': self.icon_class,
            'extension': self.extension
        }
    
    @property
    def taille_formatee(self):
        if not self.taille:
            return "0 B"
        size = float(self.taille)
        units = ['B', 'KB', 'MB', 'GB', 'TB']
        unit_index = 0
        while size >= 1024 and unit_index < len(units) - 1:
            size /= 1024.0
            unit_index += 1
        return f"{size:.1f} {units[unit_index]}"
    
    @property
    def extension(self):
        if self.nom_fichier and '.' in self.nom_fichier:
            return self.nom_fichier.split('.')[-1].lower()
        return ''
    
    @property
    def icon_class(self):
        icons = {
            'pdf': 'fa-file-pdf text-danger',
            'doc': 'fa-file-word text-primary',
            'docx': 'fa-file-word text-primary',
            'xls': 'fa-file-excel text-success',
            'xlsx': 'fa-file-excel text-success',
            'ppt': 'fa-file-powerpoint text-warning',
            'pptx': 'fa-file-powerpoint text-warning',
            'jpg': 'fa-file-image text-info',
            'jpeg': 'fa-file-image text-info',
            'png': 'fa-file-image text-info',
            'gif': 'fa-file-image text-info',
            'txt': 'fa-file-alt text-secondary',
            'csv': 'fa-file-csv text-success',
            'zip': 'fa-file-archive text-dark',
            'rar': 'fa-file-archive text-dark',
            '7z': 'fa-file-archive text-dark'
        }
        return icons.get(self.extension, 'fa-file text-secondary')
    
    def get_preview_url(self):
        if self.extension in ['jpg', 'jpeg', 'png', 'gif']:
            return f"/static/uploads/plans_action/{self.plan_action_id}/{self.nom_fichier}"
        return None
# ==================== MODÈLES PROGRAMME AUDIT CORRIGÉS ====================

class ProgrammeAudit(db.Model):
    __tablename__ = 'programmes_audit'
    
    # ===== IDENTIFICATION =====
    id = db.Column(db.Integer, primary_key=True)
    reference = db.Column(db.String(50), nullable=False)  # unique=True ENLEVÉ
    nom = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    
    # ===== PÉRIODE =====
    periode = db.Column(db.String(20), nullable=False)  # annuel, triennal
    annee_debut = db.Column(db.Integer, nullable=False)
    annee_fin = db.Column(db.Integer, nullable=False)
    
    # ===== STATUT =====
    statut = db.Column(db.String(20), default='en_elaboration')
    
    # ===== MÉTHODE DE GÉNÉRATION =====
    methode_generation = db.Column(db.String(50), nullable=False)  # manuel, auto_risques, hybride
    
    # ===== CRITÈRES DE GÉNÉRATION (JSON) =====
    criteres_generation = db.Column(db.JSON)
    
    # ===== CONFIGURATION RESSOURCES =====
    frequence_audit = db.Column(db.String(20))  # annuelle, semestrielle, trimestrielle
    duree_moyenne_mission = db.Column(db.Integer)  # en jours
    ressources_disponibles = db.Column(db.Integer)  # Jours/homme disponibles par an
    
    # ===== CONFIGURATION AVANCÉE =====
    capacite_max_trimestre = db.Column(db.Integer, default=30)
    alerte_depassement = db.Column(db.Boolean, default=True)
    auto_repartition = db.Column(db.Boolean, default=True)
    
    # ===== DATES CLÉS =====
    date_approbation = db.Column(db.Date)
    date_mise_en_oeuvre = db.Column(db.Date)
    date_cloture = db.Column(db.Date)
    
    # ===== MÉTADONNÉES =====
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # ===== ARCHIVAGE =====
    is_archived = db.Column(db.Boolean, default=False)
    archived_at = db.Column(db.DateTime)
    archived_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    archive_reason = db.Column(db.Text)
    
    # ===== RELATIONS =====
    createur = db.relationship('User', foreign_keys=[created_by], backref='programmes_crees')
    archiveur = db.relationship('User', foreign_keys=[archived_by], backref='programmes_archives')
    missions = db.relationship(
        'MissionAudit', 
        back_populates='programme', 
        cascade='all, delete-orphan',
        lazy='dynamic'
    )
    client = db.relationship('Client', backref='programmes_audit')
    
    # ===== CONTRAINTE UNIQUE COMPOSITE (AJOUT OBLIGATOIRE) =====
    __table_args__ = (
        db.UniqueConstraint('reference', 'client_id', name='uix_programme_reference_client'),
    )
    
    # ===== MÉTHODE STATIQUE DE GÉNÉRATION (DOIT ÊTRE AVANT LES PROPRIÉTÉS) =====
    @staticmethod
    def generer_reference(client_id):
        """Génère une référence unique PAR CLIENT"""
        from datetime import datetime
        annee = datetime.now().year
        prefixe = f"PROGAUD-{annee}-"
        
        count = ProgrammeAudit.query.filter(
            ProgrammeAudit.reference.like(f'{prefixe}%'),
            ProgrammeAudit.client_id == client_id
        ).count()
        
        return f"{prefixe}{(count + 1):04d}"
    
    # ===== PROPRIÉTÉS CALCULÉES =====
    
    @property
    def nb_missions(self):
        """Nombre total de missions non archivées"""
        return self.missions.filter_by(is_archived=False).count()
    
    @property
    def nb_missions_realisees(self):
        """Nombre de missions terminées"""
        return self.missions.filter_by(
            statut='termine', 
            is_archived=False
        ).count()
    
    @property
    def nb_missions_en_cours(self):
        """Nombre de missions en cours"""
        return self.missions.filter_by(
            statut='en_cours',
            is_archived=False
        ).count()
    
    @property
    def nb_missions_planifiees(self):
        """Nombre de missions planifiées"""
        return self.missions.filter_by(
            statut='planifie',
            is_archived=False
        ).count()
    
    @property
    def nb_missions_reportees(self):
        """Nombre de missions reportées"""
        return self.missions.filter_by(
            statut='reporte',
            is_archived=False
        ).count()
    
    @property
    def progression(self):
        """Progression globale du programme (0-100%)"""
        total = self.nb_missions
        if total == 0:
            return 0
        return int((self.nb_missions_realisees / total) * 100)
    
    @property
    def jours_audit_planifies(self):
        """Total des jours planifiés"""
        missions = self.missions.filter_by(is_archived=False).all()
        return sum(m.duree_estimee or 0 for m in missions)
    
    @property
    def jours_audit_realises(self):
        """Total des jours réellement travaillés"""
        missions = self.missions.filter(
            MissionAudit.duree_reelle.isnot(None),
            MissionAudit.is_archived == False
        ).all()
        return sum(m.duree_reelle or 0 for m in missions)
    
    @property
    def charge_par_annee(self):
        """Dictionnaire {année: charge}"""
        charge = {}
        for mission in self.missions.filter_by(is_archived=False).all():
            annee = mission.annee_prevue
            charge[annee] = charge.get(annee, 0) + (mission.duree_estimee or 0)
        return charge
    
    @property
    def charge_par_trimestre(self):
        """Dictionnaire {'année-Ttrimestre': charge}"""
        charge = {}
        for mission in self.missions.filter_by(is_archived=False).all():
            if mission.annee_prevue and mission.trimestre_prevue:
                key = f"{mission.annee_prevue}-T{mission.trimestre_prevue}"
                charge[key] = charge.get(key, 0) + (mission.duree_estimee or 0)
        return charge
    
    @property
    def charge_par_mois(self):
        """Dictionnaire {'année-mm': charge}"""
        charge = {}
        for mission in self.missions.filter_by(is_archived=False).all():
            if mission.annee_prevue and mission.mois_prevue:
                key = f"{mission.annee_prevue}-{mission.mois_prevue:02d}"
                charge[key] = charge.get(key, 0) + (mission.duree_estimee or 0)
        return charge
    
    @property
    def charge_par_semaine(self):
        """Dictionnaire {'année-Ssemaine': charge}"""
        charge = {}
        for mission in self.missions.filter_by(is_archived=False).all():
            if mission.annee_prevue and mission.semaine_prevue:
                key = f"{mission.annee_prevue}-S{mission.semaine_prevue:02d}"
                charge[key] = charge.get(key, 0) + (mission.duree_estimee or 0)
        return charge
    
    @property
    def depassement_capacite(self):
        """Liste des années où la capacité est dépassée"""
        if not self.ressources_disponibles:
            return []
        
        depassements = []
        for annee, charge in self.charge_par_annee.items():
            if charge > self.ressources_disponibles:
                depassements.append({
                    'annee': annee,
                    'charge': charge,
                    'capacite': self.ressources_disponibles,
                    'depassement': charge - self.ressources_disponibles,
                    'taux': int((charge / self.ressources_disponibles) * 100)
                })
        return depassements
    
    @property
    def depassement_trimestre(self):
        """Liste des trimestres où la capacité max est dépassée"""
        if not self.capacite_max_trimestre:
            return []
        
        depassements = []
        for mission in self.missions.filter_by(is_archived=False).all():
            if (mission.annee_prevue and mission.trimestre_prevue and 
                mission.duree_estimee and mission.duree_estimee > self.capacite_max_trimestre):
                depassements.append({
                    'mission': mission,
                    'annee': mission.annee_prevue,
                    'trimestre': mission.trimestre_prevue,
                    'duree': mission.duree_estimee,
                    'capacite': self.capacite_max_trimestre,
                    'depassement': mission.duree_estimee - self.capacite_max_trimestre
                })
        return depassements
    
    @property
    def missions_par_priorite(self):
        """Dictionnaire {priorite: count}"""
        missions = self.missions.filter_by(is_archived=False).all()
        return {
            'critique': len([m for m in missions if m.priorite == 'critique']),
            'elevee': len([m for m in missions if m.priorite == 'elevee']),
            'moyenne': len([m for m in missions if m.priorite == 'moyenne']),
            'faible': len([m for m in missions if m.priorite == 'faible'])
        }
    
    @property
    def missions_par_statut(self):
        """Dictionnaire {statut: count}"""
        return {
            'planifie': self.nb_missions_planifiees,
            'en_cours': self.nb_missions_en_cours,
            'termine': self.nb_missions_realisees,
            'reporte': self.nb_missions_reportees
        }
    
    @property
    def missions_liste(self):
        """Liste de toutes les missions non archivées (utile pour les templates)"""
        return self.missions.filter_by(is_archived=False).all()
    
    @property
    def missions_avec_retard(self):
        """Liste des missions en retard"""
        return [m for m in self.missions_liste if m.est_en_retard]
    
    @property
    def taux_retard(self):
        """Pourcentage de missions en retard"""
        total = self.nb_missions
        if total == 0:
            return 0
        return int((len(self.missions_avec_retard) / total) * 100)
    
    @property
    def budget_total_estime(self):
        """Budget total estimé"""
        missions = self.missions.filter_by(is_archived=False).all()
        return sum(m.budget_estime or 0 for m in missions)
    
    @property
    def budget_total_reel(self):
        """Budget total réel"""
        missions = self.missions.filter_by(is_archived=False).all()
        return sum(m.budget_reel or 0 for m in missions)
    
    @property
    def ecart_budget(self):
        """Écart entre budget réel et estimé"""
        return self.budget_total_reel - self.budget_total_estime
    
    @property
    def peut_etre_approuve(self):
        """Vérifie si le programme peut être approuvé"""
        if self.statut != 'en_elaboration':
            return False
        if self.nb_missions == 0:
            return False
        return True
    
    @property
    def peut_etre_archive(self):
        """Vérifie si le programme peut être archivé"""
        if self.is_archived:
            return False
        if self.statut == 'actif' and self.nb_missions_realisees == self.nb_missions:
            return True
        return True
    
    @property
    def duree_totale_annees(self):
        """Durée totale du programme en années"""
        return self.annee_fin - self.annee_debut + 1
    
    @property
    def progression_par_annee(self):
        """Dictionnaire {annee: progression}"""
        progression = {}
        for annee in range(self.annee_debut, self.annee_fin + 1):
            missions_annee = [m for m in self.missions_liste if m.annee_prevue == annee]
            total = len(missions_annee)
            if total > 0:
                terminees = len([m for m in missions_annee if m.statut == 'termine'])
                progression[annee] = int((terminees / total) * 100)
            else:
                progression[annee] = 0
        return progression
    
    # ===== MÉTHODES D'INSTANCE =====
    
    def approuver(self, date_approbation=None, commentaire=None):
        """Approuve le programme"""
        self.statut = 'actif'
        self.date_approbation = date_approbation or datetime.now().date()
        self.date_mise_en_oeuvre = datetime.now().date()
        self.updated_at = datetime.now()
    
    def desapprouver(self, raison=None):
        """Désapprouve le programme"""
        self.statut = 'en_elaboration'
        self.date_approbation = None
        self.date_mise_en_oeuvre = None
        self.archive_reason = raison
        self.updated_at = datetime.now()
    
    def archiver(self, raison=None, user_id=None):
        """Archive le programme"""
        self.is_archived = True
        self.statut = 'archive'
        self.archived_at = datetime.now()
        self.archived_by = user_id
        self.archive_reason = raison
        self.updated_at = datetime.now()
    
    def restaurer(self):
        """Restaure un programme archivé"""
        self.is_archived = False
        self.statut = 'en_elaboration'
        self.archived_at = None
        self.archived_by = None
        self.archive_reason = None
        self.updated_at = datetime.now()
    
    def mettre_a_jour_criteres(self, criteres):
        """Met à jour les critères de génération"""
        self.criteres_generation = criteres
        self.updated_at = datetime.now()
    
    def dupliquer(self, nouveau_nom=None, nouvel_utilisateur_id=None):
        """Crée une copie du programme"""
        from copy import deepcopy
        
        nouveau_programme = ProgrammeAudit(
            reference=f"{self.reference}-COPY",
            nom=nouveau_nom or f"Copie de {self.nom}",
            description=self.description,
            periode=self.periode,
            annee_debut=self.annee_debut + 1,
            annee_fin=self.annee_fin + 1,
            methode_generation=self.methode_generation,
            criteres_generation=deepcopy(self.criteres_generation) if self.criteres_generation else None,
            frequence_audit=self.frequence_audit,
            duree_moyenne_mission=self.duree_moyenne_mission,
            ressources_disponibles=self.ressources_disponibles,
            capacite_max_trimestre=self.capacite_max_trimestre,
            alerte_depassement=self.alerte_depassement,
            auto_repartition=self.auto_repartition,
            statut='en_elaboration',
            client_id=self.client_id,
            created_by=nouvel_utilisateur_id or self.created_by
        )
        
        return nouveau_programme
    
    def obtenir_charge_maximale(self):
        """Retourne la charge maximale sur une période"""
        charges = list(self.charge_par_annee.values())
        return max(charges) if charges else 0
    
    def obtenir_periode_plus_chargee(self):
        """Retourne la période (année) la plus chargée"""
        if not self.charge_par_annee:
            return None
        return max(self.charge_par_annee, key=self.charge_par_annee.get)
    
    def obtenir_statistiques_completes(self):
        """Retourne un dictionnaire avec toutes les statistiques"""
        return {
            'general': {
                'reference': self.reference,
                'nom': self.nom,
                'statut': self.statut,
                'periode': self.periode,
                'annees': f"{self.annee_debut}-{self.annee_fin}",
                'methode': self.methode_generation
            },
            'missions': {
                'total': self.nb_missions,
                'planifiees': self.nb_missions_planifiees,
                'en_cours': self.nb_missions_en_cours,
                'terminees': self.nb_missions_realisees,
                'reportees': self.nb_missions_reportees,
                'en_retard': len(self.missions_avec_retard)
            },
            'progression': {
                'globale': self.progression,
                'par_annee': self.progression_par_annee,
                'taux_retard': self.taux_retard
            },
            'ressources': {
                'jours_planifies': self.jours_audit_planifies,
                'jours_realises': self.jours_audit_realises,
                'ressources_disponibles': self.ressources_disponibles,
                'depassements': self.depassement_capacite
            },
            'priorites': self.missions_par_priorite,
            'budget': {
                'estime': self.budget_total_estime,
                'reel': self.budget_total_reel,
                'ecart': self.ecart_budget
            }
        }
    
    def __repr__(self):
        return f'<ProgrammeAudit {self.reference}: {self.nom} [{self.annee_debut}-{self.annee_fin}]>'

class MissionAudit(db.Model):
    __tablename__ = 'missions_audit'
    
    id = db.Column(db.Integer, primary_key=True)
    reference = db.Column(db.String(50), nullable=False)  # ← unique=True ENLEVÉ
    titre = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    
    # Liens
    risque_id = db.Column(db.Integer, db.ForeignKey('risques.id'), nullable=True)
    cartographie_id = db.Column(db.Integer, db.ForeignKey('cartographie.id'), nullable=True)
    programme_id = db.Column(db.Integer, db.ForeignKey('programmes_audit.id'), nullable=False)
    audit_id = db.Column(db.Integer, db.ForeignKey('audits.id'), nullable=True)
    
    # Priorité et risque
    priorite = db.Column(db.String(20))
    niveau_risque_associe = db.Column(db.String(20))
    score_risque = db.Column(db.Integer)
    
    # Planification
    annee_prevue = db.Column(db.Integer, nullable=False)
    trimestre_prevue = db.Column(db.Integer)
    mois_prevue = db.Column(db.Integer)
    semaine_prevue = db.Column(db.Integer)
    date_debut_prevue = db.Column(db.Date)
    date_fin_prevue = db.Column(db.Date)
    duree_estimee = db.Column(db.Integer)
    
    # Exécution
    date_debut_reelle = db.Column(db.Date)
    date_fin_reelle = db.Column(db.Date)
    duree_reelle = db.Column(db.Integer)
    
    # Statut
    statut = db.Column(db.String(20), default='planifie')
    progression = db.Column(db.Integer, default=0)
    
    # Ressources
    responsable_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    equipe_ids = db.Column(db.Text)
    budget_estime = db.Column(db.Float, nullable=True)
    budget_reel = db.Column(db.Float, nullable=True)
    
    # Commentaires
    commentaire_repli = db.Column(db.Text)
    notes_internes = db.Column(db.Text)
    contraintes = db.Column(db.Text)
    
    # Archivage
    is_archived = db.Column(db.Boolean, default=False)
    archived_at = db.Column(db.DateTime)
    archived_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    archive_reason = db.Column(db.Text)
    
    # Métadonnées
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)
    
    # ========== RELATIONS ==========
    # Relations principales
    programme = db.relationship('ProgrammeAudit', back_populates='missions')
    risque = db.relationship('Risque', backref='missions_audit_simple')
    cartographie = db.relationship('Cartographie', backref='missions_audit_simple')
    audit = db.relationship('Audit', backref='mission_origine_simple', foreign_keys=[audit_id])
    
    # Relations utilisateurs
    responsable = db.relationship('User', foreign_keys=[responsable_id], 
                                 backref='missions_responsable_simple')
    createur = db.relationship('User', foreign_keys=[created_by],
                              backref='missions_crees_simple')
    archiveur = db.relationship('User', foreign_keys=[archived_by],
                               backref='missions_archivees_simple')
    
    # Relations plans de repli
    plans_repli_principaux = db.relationship(
        'PlanPluieAudit',
        foreign_keys='PlanPluieAudit.mission_principale_id',
        back_populates='mission_principale',
        cascade='all, delete-orphan',
        lazy='dynamic'
    )
    
    plans_repli_remplacement = db.relationship(
        'PlanPluieAudit',
        foreign_keys='PlanPluieAudit.mission_remplacement_id',
        back_populates='mission_remplacement',
        cascade='all, delete-orphan',
        lazy='dynamic'
    )
    
    # ========== CONTRAINTE UNIQUE COMPOSITE ==========
    __table_args__ = (
        db.UniqueConstraint('reference', 'client_id', name='uix_mission_reference_client'),
    )
    
    # ========== MÉTHODE STATIQUE DE GÉNÉRATION ==========
    @staticmethod
    def generer_reference(client_id):
        """Génère une référence unique PAR CLIENT"""
        from datetime import datetime
        annee = datetime.now().year
        prefixe = f"MISS-{annee}-"
        
        count = MissionAudit.query.filter(
            MissionAudit.reference.like(f'{prefixe}%'),
            MissionAudit.client_id == client_id
        ).count()
        
        return f"{prefixe}{(count + 1):04d}"
    
    # ========== PROPRIÉTÉS CALCULÉES ==========
    @property
    def est_en_retard(self):
        if self.date_fin_prevue and self.statut not in ['termine', 'annule', 'reporte']:
            return datetime.now().date() > self.date_fin_prevue
        return False
    
    @property
    def jours_restants(self):
        if self.date_fin_prevue and self.statut not in ['termine', 'annule', 'reporte']:
            return max(0, (self.date_fin_prevue - datetime.now().date()).days)
        return 0
    
    @property
    def couleur_priorite(self):
        return {
            'critique': 'danger',
            'elevee': 'warning',
            'moyenne': 'info',
            'faible': 'secondary'
        }.get(self.priorite, 'secondary')
    
    @property
    def icone_statut(self):
        return {
            'planifie': 'fa-clock',
            'en_cours': 'fa-play-circle',
            'termine': 'fa-check-circle',
            'reporte': 'fa-calendar-times',
            'annule': 'fa-ban'
        }.get(self.statut, 'fa-question-circle')
    
    @property
    def plan_repli_actif(self):
        """Retourne le plan de repli actif si existant"""
        return self.plans_repli_principaux.filter_by(
            statut='actif',
            is_archived=False
        ).first()
    
    @property
    def get_statut_label(self):
        """Libellé du statut en français"""
        labels = {
            'planifie': 'Planifié',
            'en_cours': 'En cours',
            'termine': 'Terminé',
            'reporte': 'Reporté',
            'annule': 'Annulé'
        }
        return labels.get(self.statut, self.statut)
    
    @property
    def get_priorite_label(self):
        """Libellé de la priorité en français"""
        labels = {
            'critique': 'Critique',
            'elevee': 'Élevée',
            'moyenne': 'Moyenne',
            'faible': 'Faible'
        }
        return labels.get(self.priorite, self.priorite)
    
    @property
    def taux_progression(self):
        """Calcule le taux de progression basé sur les dates"""
        if self.statut == 'termine':
            return 100
        if self.statut == 'planifie':
            return 0
        if self.date_debut_reelle and self.date_fin_prevue:
            today = datetime.now().date()
            if today < self.date_debut_reelle:
                return 0
            if today > self.date_fin_prevue:
                return 100
            total_duree = (self.date_fin_prevue - self.date_debut_reelle).days
            if total_duree <= 0:
                return 0
            duree_ecoulee = (today - self.date_debut_reelle).days
            return min(100, int((duree_ecoulee / total_duree) * 100))
        return self.progression or 0
    
    @property
    def duree_ecart_jours(self):
        """Écart entre durée réelle et estimée (en jours)"""
        if self.duree_reelle and self.duree_estimee:
            return self.duree_reelle - self.duree_estimee
        return None
    
    @property
    def budget_ecart(self):
        """Écart entre budget réel et estimé"""
        if self.budget_reel and self.budget_estime:
            return self.budget_reel - self.budget_estime
        return None
    
    # ========== MÉTHODES D'INSTANCE ==========
    def demarrer(self, date_debut=None):
        """Démarre la mission"""
        if self.statut == 'planifie':
            self.statut = 'en_cours'
            self.date_debut_reelle = date_debut or datetime.now().date()
            self.updated_at = datetime.utcnow()
            return True
        return False
    
    def terminer(self, date_fin=None):
        """Termine la mission"""
        if self.statut in ['planifie', 'en_cours']:
            self.statut = 'termine'
            self.date_fin_reelle = date_fin or datetime.now().date()
            if self.date_debut_reelle and self.date_fin_reelle:
                self.duree_reelle = (self.date_fin_reelle - self.date_debut_reelle).days
            self.progression = 100
            self.updated_at = datetime.utcnow()
            return True
        return False
    
    def reporter(self, nouvelle_date_debut=None, nouvelle_date_fin=None, raison=None):
        """Reporte la mission"""
        if nouvelle_date_debut:
            self.date_debut_prevue = nouvelle_date_debut
        if nouvelle_date_fin:
            self.date_fin_prevue = nouvelle_date_fin
        if raison:
            self.commentaire_repli = raison
        self.statut = 'reporte'
        self.updated_at = datetime.utcnow()
    
    def annuler(self, raison=None):
        """Annule la mission"""
        self.statut = 'annule'
        if raison:
            self.archive_reason = raison
        self.updated_at = datetime.utcnow()
    
    def archiver(self, user_id=None, raison=None):
        """Archive la mission"""
        self.is_archived = True
        self.archived_at = datetime.utcnow()
        self.archived_by = user_id
        if raison:
            self.archive_reason = raison
        self.updated_at = datetime.utcnow()
    
    def restaurer(self):
        """Restaure une mission archivée"""
        self.is_archived = False
        self.archived_at = None
        self.archived_by = None
        self.archive_reason = None
        self.updated_at = datetime.utcnow()
    
    def get_equipe_list(self):
        """Retourne la liste des IDs d'équipe"""
        if self.equipe_ids:
            return [int(id.strip()) for id in self.equipe_ids.split(',') if id.strip()]
        return []
    
    def ajouter_membre_equipe(self, user_id):
        """Ajoute un membre à l'équipe"""
        membres = self.get_equipe_list()
        if user_id not in membres:
            membres.append(user_id)
            self.equipe_ids = ','.join(str(id) for id in membres)
            self.updated_at = datetime.utcnow()
    
    def retirer_membre_equipe(self, user_id):
        """Retire un membre de l'équipe"""
        membres = self.get_equipe_list()
        if user_id in membres:
            membres.remove(user_id)
            self.equipe_ids = ','.join(str(id) for id in membres) if membres else None
            self.updated_at = datetime.utcnow()
    
    # ========== MÉTHODE DE CONVERSION ==========
    def to_dict(self):
        """Convertit la mission en dictionnaire pour API"""
        return {
            'id': self.id,
            'reference': self.reference,
            'titre': self.titre,
            'description': self.description,
            'priorite': self.priorite,
            'priorite_label': self.get_priorite_label,
            'priorite_couleur': self.couleur_priorite,
            'statut': self.statut,
            'statut_label': self.get_statut_label,
            'statut_icone': self.icone_statut,
            'annee_prevue': self.annee_prevue,
            'trimestre_prevue': self.trimestre_prevue,
            'date_debut_prevue': self.date_debut_prevue.isoformat() if self.date_debut_prevue else None,
            'date_fin_prevue': self.date_fin_prevue.isoformat() if self.date_fin_prevue else None,
            'duree_estimee': self.duree_estimee,
            'date_debut_reelle': self.date_debut_reelle.isoformat() if self.date_debut_reelle else None,
            'date_fin_reelle': self.date_fin_reelle.isoformat() if self.date_fin_reelle else None,
            'duree_reelle': self.duree_reelle,
            'progression': self.taux_progression,
            'est_en_retard': self.est_en_retard,
            'jours_restants': self.jours_restants,
            'programme_id': self.programme_id,
            'programme_reference': self.programme.reference if self.programme else None,
            'audit_id': self.audit_id,
            'risque_id': self.risque_id,
            'responsable_id': self.responsable_id,
            'responsable_nom': self.responsable.username if self.responsable else None,
            'budget_estime': self.budget_estime,
            'budget_reel': self.budget_reel,
            'budget_ecart': self.budget_ecart,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'is_archived': self.is_archived
        }
    
    def __repr__(self):
        return f'<MissionAudit {self.reference}: {self.titre[:30]}>'

class PlanPluieAudit(db.Model):
    __tablename__ = 'plans_pluie_audit'
    
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    
    # Missions liées - clés étrangères explicites
    mission_principale_id = db.Column(
        db.Integer, 
        db.ForeignKey('missions_audit.id', name='fk_plan_mission_principale'),
        nullable=True
    )
    mission_remplacement_id = db.Column(
        db.Integer, 
        db.ForeignKey('missions_audit.id', name='fk_plan_mission_remplacement'),
        nullable=True
    )
    
    # Conditions de déclenchement
    condition_type = db.Column(db.String(50))  # retard, indisponibilite, urgence
    condition_seuil = db.Column(db.Integer)
    condition_description = db.Column(db.Text)
    
    # Statut
    statut = db.Column(db.String(20), default='actif')  # actif, declenche, archive
    
    # Déclenchement
    date_declenchement = db.Column(db.DateTime)
    raison_declenchement = db.Column(db.String(100))
    commentaires_declenchement = db.Column(db.Text)
    
    # Archivage
    is_archived = db.Column(db.Boolean, default=False)
    archived_at = db.Column(db.DateTime)
    archived_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    archive_reason = db.Column(db.Text)
    
    # Métadonnées
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)
    
    # ========== RELATIONS CORRIGÉES ==========
    # Relations avec MissionAudit - back_populates explicite
    mission_principale = db.relationship(
        'MissionAudit',
        foreign_keys=[mission_principale_id],
        back_populates='plans_repli_principaux',
        lazy='joined'
    )
    
    mission_remplacement = db.relationship(
        'MissionAudit',
        foreign_keys=[mission_remplacement_id],
        back_populates='plans_repli_remplacement',
        lazy='joined'
    )
    
    # Relations utilisateurs
    createur = db.relationship(
        'User',
        foreign_keys=[created_by],
        backref='plans_pluie_crees'
    )
    
    archiveur = db.relationship(
        'User',
        foreign_keys=[archived_by],
        backref='plans_pluie_archives'
    )
    
    client = db.relationship('Client', backref='plans_repli_audit_simple')
    
    # ========== PROPRIÉTÉS ==========
    @property
    def est_declenchable(self):
        """Vérifie si le plan peut être déclenché"""
        if self.statut != 'actif':
            return False
        if not self.mission_principale:
            return False
        if self.mission_principale.statut in ['termine', 'annule', 'archive']:
            return False
        return True
    
    @property
    def jours_retard_actuel(self):
        """Calcule le retard actuel de la mission principale"""
        if not self.mission_principale or not self.mission_principale.date_fin_prevue:
            return 0
        if self.mission_principale.statut in ['termine', 'annule']:
            return 0
        retard = (datetime.now().date() - self.mission_principale.date_fin_prevue).days
        return max(0, retard)
    
    @property
    def doit_etre_declenche(self):
        """Vérifie si les conditions de déclenchement sont remplies"""
        if not self.est_declenchable:
            return False
        
        if self.condition_type == 'retard':
            return self.jours_retard_actuel >= (self.condition_seuil or 15)
        
        return False
    
    def __repr__(self):
        return f'<PlanPluieAudit {self.id}: {self.nom}>'
    
class JournalAuditProgramme(db.Model):
    __tablename__ = 'journal_audit_programme'
    
    id = db.Column(db.Integer, primary_key=True)
    programme_id = db.Column(db.Integer, db.ForeignKey('programmes_audit.id'), nullable=False)
    action = db.Column(db.String(255), nullable=False)
    details = db.Column(db.Text)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relations
    programme = db.relationship('ProgrammeAudit', backref='journal_audit')
    utilisateur = db.relationship('User', foreign_keys=[user_id])

# models.py - Ajoutez ceci avec vos autres modèles

class ActivityLog(db.Model):
    __tablename__ = 'activity_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    action_type = db.Column(db.String(100))
    description = db.Column(db.Text)
    entity_type = db.Column(db.String(50))
    entity_id = db.Column(db.Integer)
    ip_address = db.Column(db.String(50))
    user_agent = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relation
    user = db.relationship('User', backref='activities')
    
    def __repr__(self):
        return f'<ActivityLog {self.id}: {self.action_type}>'

# ============================================
# MODÈLES POUR COLLECTE MULTI-SOURCES
# ============================================

class SourceDonnee(db.Model):
    """Configuration d'une source de données externe"""
    __tablename__ = 'sources_donnees'
    
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    
    # Type de source
    TYPE_SOURCE = [
        ('api', 'API REST'),
        ('base_donnees', 'Base de données'),
        ('fichier', 'Fichier (CSV/Excel)'),
        ('web_scraping', 'Web Scraping'),
        ('formulaire', 'Formulaire externe'),
        ('iot', 'Capteur IoT'),
        ('erp', 'ERP/CRM'),
        ('autre', 'Autre')
    ]
    type_source = db.Column(db.String(50), nullable=False)
    
    # Configuration de connexion (JSON)
    config_connexion = db.Column(db.JSON, nullable=False, default={})
    
    # Paramètres d'authentification (cryptés)
    auth_config = db.Column(db.JSON, nullable=True)
    
    # Fréquence de rafraîchissement (en secondes)
    frequence_rafraichissement = db.Column(db.Integer, default=86400)  # 24h par défaut
    
    # Dernière exécution
    derniere_execution = db.Column(db.DateTime)
    prochaine_execution = db.Column(db.DateTime)
    statut = db.Column(db.String(50), default='actif')  # actif, inactif, erreur
    
    # Métadonnées
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'))
    
    # Relations
    createur = db.relationship('User', foreign_keys=[created_by])
    kri_associes = db.relationship('SourceKRILink', back_populates='source', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<SourceDonnee {self.nom}>'
    
    def get_decrypted_auth(self):
        """Retourne les authentifiants déchiffrés"""
        if not self.auth_config:
            return None
        from utils.crypt_utils import decrypt_dict
        return decrypt_dict(self.auth_config)


class SourceKRILink(db.Model):
    """Liaison entre une source de données et un KRI"""
    __tablename__ = 'source_kri_links'
    
    id = db.Column(db.Integer, primary_key=True)
    source_id = db.Column(db.Integer, db.ForeignKey('sources_donnees.id'), nullable=False)
    kri_id = db.Column(db.Integer, db.ForeignKey('kri.id'), nullable=False)
    
    # Configuration de l'extraction
    chemin_donnee = db.Column(db.String(500))  # JSON path ou requête
    transformateur = db.Column(db.String(100))  # Nom du transformateur à appliquer
    mapping_config = db.Column(db.JSON, default={})  # Mapping des champs
    
    # Paramètres de validation
    seuil_min = db.Column(db.Float, nullable=True)
    seuil_max = db.Column(db.Float, nullable=True)
    validation_regles = db.Column(db.JSON, default={})
    
    # Active ou non
    est_actif = db.Column(db.Boolean, default=True)
    
    # Métadonnées
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relations
    source = db.relationship('SourceDonnee', back_populates='kri_associes')
    kri = db.relationship('KRI', backref='sources_associees')
    collectes = db.relationship('CollecteDonnee', back_populates='source_link', cascade='all, delete-orphan')
    
    __table_args__ = (
        db.UniqueConstraint('source_id', 'kri_id', name='unique_source_kri'),
    )
    
    def valider_valeur(self, valeur):
        """Valide une valeur selon les règles configurées"""
        resultat = {'valide': True, 'message': ''}
        
        if self.seuil_min is not None and valeur < self.seuil_min:
            resultat['valide'] = False
            resultat['message'] = f"Valeur {valeur} < seuil min {self.seuil_min}"
        
        if self.seuil_max is not None and valeur > self.seuil_max:
            resultat['valide'] = False
            resultat['message'] = f"Valeur {valeur} > seuil max {self.seuil_max}"
        
        return resultat


class CollecteDonnee(db.Model):
    """Historique des collectes automatiques"""
    __tablename__ = 'collectes_donnees'
    
    id = db.Column(db.Integer, primary_key=True)
    source_link_id = db.Column(db.Integer, db.ForeignKey('source_kri_links.id'), nullable=False)
    
    # Données collectées
    valeur = db.Column(db.Float, nullable=False)
    donnees_brutes = db.Column(db.JSON)  # Données originales pour audit
    metadonnees = db.Column(db.JSON)  # Métadonnées de la collecte
    
    # Statut de la collecte
    statut = db.Column(db.String(50), default='succes')  # succes, erreur, avertissement
    message = db.Column(db.Text)  # Message d'erreur ou d'avertissement
    
    # Dates
    date_collecte = db.Column(db.DateTime, default=datetime.utcnow)
    date_valeur = db.Column(db.DateTime)  # Date à laquelle la valeur est valide
    
    # Relations
    source_link = db.relationship('SourceKRILink', back_populates='collectes')
    
    # Créer une mesure KRI associée
    mesure_kri_id = db.Column(db.Integer, db.ForeignKey('mesure_kri.id'), nullable=True)
    mesure_kri = db.relationship('MesureKRI', backref='collecte_source')
    
    def creer_mesure_kri(self):
        """Crée une mesure KRI à partir de cette collecte"""
        if self.mesure_kri_id:
            return self.mesure_kri
        
        from models import MesureKRI
        
        mesure = MesureKRI(
            kri_id=self.source_link.kri_id,
            valeur=self.valeur,
            date_mesure=self.date_valeur or self.date_collecte,
            commentaire=f"Collecte auto: {self.source_link.source.nom}",
            created_by=self.source_link.source.created_by,
            client_id=self.source_link.kri.client_id
        )
        db.session.add(mesure)
        db.session.flush()
        self.mesure_kri_id = mesure.id
        return mesure


class TransformateurDonnee(db.Model):
    """Transformateurs de données personnalisables"""
    __tablename__ = 'transformateurs_donnees'
    
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text)
    
    TYPE_TRANSFORM = [
        ('formule', 'Formule mathématique'),
        ('python', 'Script Python'),
        ('moyenne', 'Moyenne mobile'),
        ('somme', 'Somme'),
        ('comptage', 'Comptage'),
        ('extraction', 'Extraction JSON'),
        ('agregation', 'Agrégation temporelle'),
        ('normalisation', 'Normalisation')
    ]
    type_transform = db.Column(db.String(50), nullable=False)
    
    # Code ou configuration
    code = db.Column(db.Text)  # Pour les scripts Python
    config = db.Column(db.JSON, default={})  # Pour les formules
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    createur = db.relationship('User', foreign_keys=[created_by])
    
    def appliquer(self, donnees, **kwargs):
        """Applique la transformation aux données"""
        if self.type_transform == 'formule':
            return self._appliquer_formule(donnees, **kwargs)
        elif self.type_transform == 'moyenne':
            return self._appliquer_moyenne(donnees, **kwargs)
        elif self.type_transform == 'somme':
            return sum(donnees) if isinstance(donnees, (list, tuple)) else donnees
        elif self.type_transform == 'comptage':
            return len(donnees) if isinstance(donnees, (list, tuple)) else 1
        return donnees
    
    def _appliquer_formule(self, donnees, **kwargs):
        """Applique une formule mathématique"""
        try:
            contexte = {'donnees': donnees, **kwargs}
            return eval(self.config.get('formule', 'donnees'), {"__builtins__": {}}, contexte)
        except Exception as e:
            raise ValueError(f"Erreur formule: {e}")
    
    def _appliquer_moyenne(self, donnees, **kwargs):
        """Calcule la moyenne"""
        if not isinstance(donnees, (list, tuple)):
            return donnees
        return sum(donnees) / len(donnees) if donnees else 0


class AlerteCollecte(db.Model):
    """Alertes liées aux collectes"""
    __tablename__ = 'alertes_collecte'
    
    id = db.Column(db.Integer, primary_key=True)
    collecte_id = db.Column(db.Integer, db.ForeignKey('collectes_donnees.id'), nullable=False)
    type_alerte = db.Column(db.String(50))  # anomalie, seuil, erreur
    niveau = db.Column(db.String(20))  # info, warning, danger
    message = db.Column(db.Text)
    traitee = db.Column(db.Boolean, default=False)
    traitee_par = db.Column(db.Integer, db.ForeignKey('user.id'))
    traitee_le = db.Column(db.DateTime)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    collecte = db.relationship('CollecteDonnee', backref='alertes')
    traiteur = db.relationship('User', foreign_keys=[traitee_par])


# ============================================
# MODULE QUALITÉ - PLAN D'ASSURANCE QUALITÉ
# ============================================
# ============================================
# FICHIERS PLAN QUALITÉ (À PLACER AVANT PlanQualiteFonction)
# ============================================

class FichierPlanQualite(db.Model):
    """Fichiers attachés à un plan qualité"""
    __tablename__ = 'fichiers_plan_qualite'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Liaison
    plan_qualite_id = db.Column(db.Integer, db.ForeignKey('plans_qualite_fonction.id'), nullable=False)
    
    # Informations fichier
    nom_fichier = db.Column(db.String(255), nullable=False)
    nom_unique = db.Column(db.String(255), nullable=False, unique=True)
    chemin_fichier = db.Column(db.String(500), nullable=False)
    type_fichier = db.Column(db.String(100), nullable=False)
    taille = db.Column(db.Integer, nullable=False)
    
    # Métadonnées
    categorie = db.Column(db.String(50), default='document')
    description = db.Column(db.String(500), nullable=True)
    
    # Audit
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    uploaded_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Multi-tenant
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)
    
    # Relations
    plan_qualite = db.relationship('PlanQualiteFonction', back_populates='fichiers')
    uploader = db.relationship('User', foreign_keys=[uploaded_by])
    
    def __repr__(self):
        return f'<FichierPlanQualite {self.nom_fichier}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'nom_fichier': self.nom_fichier,
            'type_fichier': self.type_fichier,
            'taille': self.taille,
            'taille_formatee': self.get_taille_formatee(),
            'categorie': self.categorie,
            'description': self.description,
            'uploaded_at': self.uploaded_at.strftime('%d/%m/%Y %H:%M') if self.uploaded_at else '',
            'uploader': self.uploader.username if self.uploader else 'Inconnu'
        }
    
    def get_taille_formatee(self):
        if self.taille < 1024:
            return f"{self.taille} o"
        elif self.taille < 1024 * 1024:
            return f"{self.taille / 1024:.1f} Ko"
        else:
            return f"{self.taille / (1024 * 1024):.1f} Mo"


# ============================================
# PLAN QUALITÉ FONCTION (APRÈS FichierPlanQualite)
# ============================================

class PlanQualiteFonction(db.Model):
    """Plan d'assurance et d'amélioration qualité pour une fonction spécifique"""
    __tablename__ = 'plans_qualite_fonction'

    id = db.Column(db.Integer, primary_key=True)
    
    # Identifiants et références
    reference = db.Column(db.String(50), unique=True, nullable=False)
    titre = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    
    # Liens vers la structure de l'entreprise
    pole_id = db.Column(db.Integer, db.ForeignKey('poles.id'), nullable=True)
    direction_id = db.Column(db.Integer, db.ForeignKey('direction.id'), nullable=True)
    service_id = db.Column(db.Integer, db.ForeignKey('service.id'), nullable=True)
    
    # Dates et périmètre
    date_debut = db.Column(db.Date, nullable=False)
    date_fin = db.Column(db.Date, nullable=False)
    annee_exercice = db.Column(db.Integer, nullable=False)
    
    # SECTION 1 : ASSURANCE QUALITÉ (PRÉVENTIF)
    procedures_applicables = db.Column(db.Text, nullable=True)
    frequence_controles = db.Column(db.String(50), default='mensuel')
    responsable_conformite_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    documents_reference = db.Column(db.Text, nullable=True)
    controles_cles = db.Column(db.Text, nullable=True)
    niveau_maturite = db.Column(db.String(10), default='3')
    
    # SECTION 2 : AMÉLIORATION QUALITÉ (CORRECTIF)
    objectifs_qualite = db.Column(db.JSON, default=[])
    indicateurs_cles = db.Column(db.JSON, default=[])
    
    # SECTION 3 : REVUE ET AUDIT DU PLAN
    date_prochaine_revue = db.Column(db.Date, nullable=True)
    date_derniere_revue = db.Column(db.Date, nullable=True)
    responsable_revue_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    
    # Statut et validation
    statut = db.Column(db.String(20), default='brouillon')
    est_valide = db.Column(db.Boolean, default=False)
    date_validation = db.Column(db.DateTime, nullable=True)
    valide_par_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    
    # Archivage
    is_archived = db.Column(db.Boolean, default=False)
    archived_at = db.Column(db.DateTime, nullable=True)
    archived_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    archive_reason = db.Column(db.String(255), nullable=True)
    
    # Audit et métadonnées
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Multi-tenant
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)
    
    # ============================================
    # RELATIONS
    # ============================================
    pole = db.relationship('Pole', foreign_keys=[pole_id])
    direction = db.relationship('Direction', foreign_keys=[direction_id])
    service = db.relationship('Service', foreign_keys=[service_id])
    createur = db.relationship('User', foreign_keys=[created_by])
    archive_user = db.relationship('User', foreign_keys=[archived_by])
    validateur = db.relationship('User', foreign_keys=[valide_par_id])
    responsable_conformite = db.relationship('User', foreign_keys=[responsable_conformite_id])
    responsable_revue = db.relationship('User', foreign_keys=[responsable_revue_id])
    
    actions_amelioration = db.relationship('ActionAmeliorationQualite', back_populates='plan_qualite', lazy=True)
    fichiers = db.relationship('FichierPlanQualite', back_populates='plan_qualite', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<PlanQualite {self.reference}: {self.titre}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'reference': self.reference,
            'titre': self.titre,
            'description': self.description,
            'statut': self.statut,
            'est_valide': self.est_valide,
            'date_debut': self.date_debut.isoformat() if self.date_debut else None,
            'date_fin': self.date_fin.isoformat() if self.date_fin else None,
            'date_prochaine_revue': self.date_prochaine_revue.isoformat() if self.date_prochaine_revue else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'procedures_applicables': self.procedures_applicables,
            'frequence_controles': self.frequence_controles,
            'niveau_maturite': self.niveau_maturite,
            'objectifs_qualite': self.objectifs_qualite,
            'indicateurs_cles': self.indicateurs_cles
        }
    
    def archiver(self, user_id, raison="Archivage manuel"):
        self.is_archived = True
        self.archived_at = datetime.utcnow()
        self.archived_by = user_id
        self.archive_reason = raison
        self.statut = 'archive'
        
    def desarchiver(self):
        self.is_archived = False
        self.archived_at = None
        self.archived_by = None
        self.archive_reason = None
        self.statut = 'brouillon'
    
    def valider(self, user_id):
        self.est_valide = True
        self.date_validation = datetime.utcnow()
        self.valide_par_id = user_id
        self.statut = 'actif'
    
    def get_niveau_maturite_label(self):
        niveaux = {
            '1': 'Initial',
            '2': 'Répétable',
            '3': 'Défini',
            '4': 'Géré',
            '5': 'Optimisé'
        }
        return niveaux.get(self.niveau_maturite, 'Non défini')
    
    def get_frequence_controles_label(self):
        frequences = {
            'quotidien': 'Quotidien',
            'hebdomadaire': 'Hebdomadaire',
            'mensuel': 'Mensuel',
            'trimestriel': 'Trimestriel',
            'semestriel': 'Semestriel',
            'annuel': 'Annuel'
        }
        return frequences.get(self.frequence_controles, 'Non défini')
    
    def get_statut_revue(self):
        if not self.date_prochaine_revue:
            return 'non_planifie'
        
        today = datetime.now().date()
        if self.date_prochaine_revue < today:
            return 'retard'
        elif self.date_prochaine_revue <= today + timedelta(days=30):
            return 'proche'
        else:
            return 'ok'
    
    def get_jours_restants_revue(self):
        if not self.date_prochaine_revue:
            return None
        
        today = datetime.now().date()
        if self.date_prochaine_revue < today:
            return - (today - self.date_prochaine_revue).days
        else:
            return (self.date_prochaine_revue - today).days

    def calculer_progression(self):
        """Calcule la progression du plan basée sur les actions d'amélioration"""
        if not self.actions_amelioration:
            return 0
        total = len(self.actions_amelioration)
        if total == 0:
            return 0
        terminees = sum(1 for a in self.actions_amelioration if a.statut == 'terminee')
        return round((terminees / total) * 100, 1)
    
    def get_statut_css(self):
        """Retourne la classe CSS pour le statut"""
        if self.is_archived:
            return 'secondary'
        elif self.statut == 'actif':
            return 'success'
        elif self.statut == 'brouillon':
            return 'warning'
        elif self.statut == 'clos':
            return 'info'
        elif self.statut == 'annule':
            return 'danger'
        return 'secondary'


class CartographieRisqueFonction(db.Model):
    """Cartographie détaillée des risques par fonction d'assurance"""
    __tablename__ = 'cartographie_risques_fonction'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # ============================================
    # IDENTIFICATION
    # ============================================
    pole = db.Column(db.String(100), nullable=False)              # Pôle
    direction = db.Column(db.String(100), nullable=False)         # Direction
    direction_partie_prenante = db.Column(db.String(200))         # Direction partie prenante
    zone_risque_majeur = db.Column(db.String(200), nullable=False) # Zone de Risque majeur
    
    # ============================================
    # ÉVALUATION DU RISQUE
    # ============================================
    impact = db.Column(db.String(50), nullable=False)             # Impact (Fort à éviter, etc.)
    probabilite = db.Column(db.String(50), nullable=False)        # Probabilité (Certain, Probable, Possible)
    niveau_maitrise = db.Column(db.String(50), nullable=False)    # Niveau de maîtrise (Bonne, Faible, Insuffisante)
    typologie_risque = db.Column(db.String(100))                  # Typologie du risque
    
    # ============================================
    # NIVEAUX DE CONTRÔLE
    # ============================================
    niveau_1 = db.Column(db.Text)      # Niveau 1 - Contrôle opérationnel
    niveau_2 = db.Column(db.Text)      # Niveau 2 - Supervision
    niveau_3 = db.Column(db.Text)      # Niveau 3 - Contrôle indépendant
    controle_externe = db.Column(db.Text)  # Contrôle externe (Cours des comptes, DDFIP, etc.)
    controles_prestataires = db.Column(db.Text)  # Contrôles réalisés par prestataires externes
    
    # ============================================
    # HISTORIQUE ET PLANIFICATION
    # ============================================
    anciens_audits = db.Column(db.Text)   # Anciens audits en lien avec le risque
    plan_audit_annuel = db.Column(db.Text) # Plan d'audit annuel
    observations = db.Column(db.Text)      # Observations complémentaires
    
    # ============================================
    # FONCTIONS D'ASSURANCE
    # ============================================
    fonctions_assurance = db.Column(db.String(200))   # Fonctions d'assurance concernées
    pole_audit = db.Column(db.String(100))            # Pôle Audit (IG, etc.)
    pilote = db.Column(db.String(100))                # Pilote de l'action
    
    # ============================================
    # MÉTADONNÉES
    # ============================================
    annee = db.Column(db.Integer, nullable=False)     # Année de la cartographie
    statut = db.Column(db.String(20), default='actif') # actif, archive
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)
    
    # Relations
    createur = db.relationship('User', foreign_keys=[created_by])
    
    def __repr__(self):
        return f'<CartographieRisque {self.pole} - {self.zone_risque_majeur}>'
    
    def get_niveau_risque(self):
        """Calcule le niveau de risque global"""
        # Logique de calcul personnalisable
        impact_score = {'Très fort à éviter': 5, 'Fort à éviter': 4, 'Modéré': 3, 'Faible': 2, 'Très faible': 1}.get(self.impact, 3)
        probabilite_score = {'Certain': 5, 'Très probable': 5, 'Probable': 4, 'Possible': 3, 'Peu probable': 2, 'Très rare': 1}.get(self.probabilite, 3)
        maitrise_score = {'Excellent': 1, 'Bonne': 2, 'Suffisante': 3, 'Faible': 4, 'Insuffisante': 5}.get(self.niveau_maitrise, 3)
        
        score = (impact_score + probabilite_score + maitrise_score) / 3
        if score <= 2:
            return 'Faible', 'success'
        elif score <= 3.5:
            return 'Moyen', 'warning'
        elif score <= 4.5:
            return 'Élevé', 'danger'
        else:
            return 'Critique', 'dark'
        
# ============================================
# ACTIONS AMÉLIORATION QUALITÉ
# ============================================

class ActionAmeliorationQualite(db.Model):
    """Action d'amélioration qualité liée à un plan"""
    __tablename__ = 'actions_amelioration_qualite'

    id = db.Column(db.Integer, primary_key=True)
    reference = db.Column(db.String(50), unique=True, nullable=False)
    intitule = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    
    plan_qualite_id = db.Column(db.Integer, db.ForeignKey('plans_qualite_fonction.id'), nullable=False)
    
    date_echeance = db.Column(db.Date, nullable=False)
    priorite = db.Column(db.String(20), default='moyenne')
    
    statut = db.Column(db.String(20), default='a_faire')
    pourcentage_realisation = db.Column(db.Integer, default=0)
    commentaire_realisation = db.Column(db.Text, nullable=True)
    
    responsable_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    
    is_archived = db.Column(db.Boolean, default=False)
    archived_at = db.Column(db.DateTime, nullable=True)
    archived_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)
    
    # Relations
    plan_qualite = db.relationship('PlanQualiteFonction', back_populates='actions_amelioration')
    responsable = db.relationship('User', foreign_keys=[responsable_id])
    createur = db.relationship('User', foreign_keys=[created_by])
    archive_user = db.relationship('User', foreign_keys=[archived_by])
    
    def __repr__(self):
        return f'<ActionAmelioration {self.reference}: {self.intitule}>'
    
    def est_en_retard(self):
        if self.statut == 'terminee':
            return False
        if self.date_echeance and datetime.utcnow().date() > self.date_echeance:
            return True
        return False


# ============================================
# MODULE FICHE DE CONTRÔLE PAR CAMPAGNE
# ============================================

class CampagneControle(db.Model):
    """Campagne de contrôle - Fiche de contrôle complète"""
    __tablename__ = 'campagnes_controle'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # ============================================
    # IDENTIFICATION
    # ============================================
    nom = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    reference = db.Column(db.String(50), unique=True, nullable=False)
    
    # Organisation
    pole_id = db.Column(db.Integer, db.ForeignKey('poles.id'), nullable=True)
    direction_id = db.Column(db.Integer, db.ForeignKey('direction.id'), nullable=True)
    service_id = db.Column(db.Integer, db.ForeignKey('service.id'), nullable=True)
    
    # ============================================
    # DATES ET STATUT
    # ============================================
    date_debut = db.Column(db.Date, nullable=False)
    date_fin = db.Column(db.Date, nullable=False)
    statut = db.Column(db.String(30), default='en_preparation')  # en_preparation, en_cours, termine, suspendu, annule
    
    # ============================================
    # ACTEURS
    # ============================================
    createur_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    valideur_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    evaluateur_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    
    # ============================================
    # VOLUMES PRÉVISIONNELS
    # ============================================
    volume_previsionnel = db.Column(db.Integer, default=0)  # Nombre total de dossiers à contrôler
    nb_dossiers_prevus = db.Column(db.Integer, default=0)   # Nombre de dossiers prévus
    nb_dossiers_reglement = db.Column(db.Integer, default=0) # Nombre de dossiers règlement à contrôler
    
    # ============================================
    # RÉSULTATS DU CONTRÔLE
    # ============================================
    nb_dossiers_controles = db.Column(db.Integer, default=0)  # Nombre de dossiers réellement contrôlés
    nb_anomalies = db.Column(db.Integer, default=0)           # Nombre de dossiers en anomalie
    nb_conformes = db.Column(db.Integer, default=0)           # Nombre de dossiers conformes
    taux_conformite = db.Column(db.Numeric(5, 2), default=0)  # Taux de conformité (%)
    
    # ============================================
    # LISTES (stockées en JSON)
    # ============================================
    dossiers_reglement_controles = db.Column(db.JSON, default=[])  # Liste des dossiers règlement contrôlés
    motifs_anomalie = db.Column(db.JSON, default=[])               # Liste des motifs d'anomalie
    recommandations = db.Column(db.JSON, default=[])               # Liste des recommandations
    
    # ============================================
    # COMMENTAIRES ET CONCLUSIONS
    # ============================================
    commentaire_general = db.Column(db.Text)
    conclusion = db.Column(db.Text)
    actions_correctives = db.Column(db.Text)
    
    # ============================================
    # ARCHIVAGE
    # ============================================
    is_archived = db.Column(db.Boolean, default=False)
    archived_at = db.Column(db.DateTime, nullable=True)
    archived_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    archive_reason = db.Column(db.String(255), nullable=True)
    
    # ============================================
    # AUDIT
    # ============================================
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)
    
    # ============================================
    # RELATIONS
    # ============================================
    pole = db.relationship('Pole', foreign_keys=[pole_id])
    direction = db.relationship('Direction', foreign_keys=[direction_id])
    service = db.relationship('Service', foreign_keys=[service_id])
    createur = db.relationship('User', foreign_keys=[createur_id])
    valideur = db.relationship('User', foreign_keys=[valideur_id])
    evaluateur = db.relationship('User', foreign_keys=[evaluateur_id])
    archive_user = db.relationship('User', foreign_keys=[archived_by])
    
    fichiers = db.relationship('FichierCampagneControle', back_populates='campagne', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<CampagneControle {self.reference}: {self.nom}>'
    
    def calculer_taux_conformite(self):
        """Calcule le taux de conformité"""
        if self.nb_dossiers_controles > 0:
            self.taux_conformite = round((self.nb_conformes / self.nb_dossiers_controles) * 100, 2)
        else:
            self.taux_conformite = 0
        return self.taux_conformite
    
    def get_avancement(self):
        """Calcule l'avancement de la campagne en pourcentage"""
        if self.nb_dossiers_prevus > 0:
            return round((self.nb_dossiers_controles / self.nb_dossiers_prevus) * 100, 1)
        return 0
    
    def get_statut_css(self):
        """Retourne la classe CSS pour le statut"""
        status_map = {
            'en_preparation': 'secondary',
            'en_cours': 'primary',
            'termine': 'success',
            'suspendu': 'warning',
            'annule': 'danger'
        }
        return status_map.get(self.statut, 'secondary')
    
    def get_statut_label(self):
        """Retourne le libellé du statut"""
        labels = {
            'en_preparation': 'En préparation',
            'en_cours': 'En cours',
            'termine': 'Terminé',
            'suspendu': 'Suspendu',
            'annule': 'Annulé'
        }
        return labels.get(self.statut, self.statut)
    
    def archiver(self, user_id, raison=None):
        """Archive la campagne"""
        self.is_archived = True
        self.archived_at = datetime.utcnow()
        self.archived_by = user_id
        self.archive_reason = raison
        self.statut = 'termine'
    
    def desarchiver(self):
        """Désarchive la campagne"""
        self.is_archived = False
        self.archived_at = None
        self.archived_by = None
        self.archive_reason = None
        self.statut = 'en_preparation'


class FichierCampagneControle(db.Model):
    """Fichiers attachés à une campagne de contrôle"""
    __tablename__ = 'fichiers_campagne_controle'
    
    id = db.Column(db.Integer, primary_key=True)
    campagne_id = db.Column(db.Integer, db.ForeignKey('campagnes_controle.id'), nullable=False)
    
    nom_fichier = db.Column(db.String(255), nullable=False)
    nom_unique = db.Column(db.String(255), nullable=False, unique=True)
    chemin_fichier = db.Column(db.String(500), nullable=False)
    type_fichier = db.Column(db.String(100), nullable=False)
    taille = db.Column(db.Integer, nullable=False)
    
    categorie = db.Column(db.String(50), default='document')  # document, rapport, preuve, autre
    description = db.Column(db.String(500), nullable=True)
    
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    uploaded_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)
    
    # Relations
    campagne = db.relationship('CampagneControle', back_populates='fichiers')
    uploader = db.relationship('User', foreign_keys=[uploaded_by])
    
    def get_taille_formatee(self):
        if self.taille < 1024:
            return f"{self.taille} o"
        elif self.taille < 1024 * 1024:
            return f"{self.taille / 1024:.1f} Ko"
        else:
            return f"{self.taille / (1024 * 1024):.1f} Mo"



# ============================================
# MODULE PLAN DE CONTINUITÉ D'ACTIVITÉ (PCA)
# ============================================

class PlanContinuiteActivite(db.Model):
    """Plan de Continuité d'Activité - PCA"""
    __tablename__ = 'plans_continuite_activite'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # ============================================
    # IDENTIFICATION
    # ============================================
    reference = db.Column(db.String(50), unique=True, nullable=False)
    titre = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    version = db.Column(db.String(20), default='1.0')
    
    # Périmètre
    pole_id = db.Column(db.Integer, db.ForeignKey('poles.id'), nullable=True)
    direction_id = db.Column(db.Integer, db.ForeignKey('direction.id'), nullable=True)
    service_id = db.Column(db.Integer, db.ForeignKey('service.id'), nullable=True)
    processus_critiques = db.Column(db.JSON, default=[])  # Liste des processus critiques
    
    # ============================================
    # DATES
    # ============================================
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)
    date_mise_a_jour = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    date_validite = db.Column(db.Date)  # Date de fin de validité
    date_dernier_test = db.Column(db.Date)  # Date du dernier test
    date_prochain_test = db.Column(db.Date)  # Date du prochain test
    
    # ============================================
    # ACTEURS
    # ============================================
    responsable_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    redacteur_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    valideur_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    equipe_pca = db.Column(db.JSON, default=[])  # Liste des membres de l'équipe PCA
    
    # ============================================
    # ANALYSE D'IMPACT (BIA)
    # ============================================
    bia_realisee = db.Column(db.Boolean, default=False)
    bia_date = db.Column(db.Date)
    delai_arret_max = db.Column(db.String(50))  # Délai d'arrêt maximal (RTO)
    perte_donnees_max = db.Column(db.String(50))  # Perte de données maximale (RPO)
    impacts_critiques = db.Column(db.JSON, default=[])  # Impacts critiques identifiés
    
    # ============================================
    # STRATÉGIES DE CONTINUITÉ
    # ============================================
    strategies = db.Column(db.JSON, default=[])  # Liste des stratégies
    sites_secours = db.Column(db.JSON, default=[])  # Sites de secours
    ressources_alternatives = db.Column(db.JSON, default=[])  # Ressources alternatives
    
    # ============================================
    # PROCÉDURES DE REPRISE
    # ============================================
    procedures_urgence = db.Column(db.Text)  # Procédures d'urgence
    procedures_reprise = db.Column(db.Text)  # Procédures de reprise
    procedures_retour_normal = db.Column(db.Text)  # Procédures de retour à la normale
    
    # ============================================
    # ÉQUIPES ET CONTACTS
    # ============================================
    cellule_crise = db.Column(db.JSON, default=[])  # Membres de la cellule de crise
    contacts_urgence = db.Column(db.JSON, default=[])  # Contacts d'urgence
    fournisseurs_critiques = db.Column(db.JSON, default=[])  # Fournisseurs critiques
    
    # ============================================
    # RESSOURCES CRITIQUES
    # ============================================
    ressources_critiques = db.Column(db.JSON, default=[])  # Ressources critiques (matériel, logiciel, données)
    duree_critique = db.Column(db.String(50))  # Durée critique de reprise
    
    # ============================================
    # EXERCICES ET TESTS
    # ============================================
    periodicite_test = db.Column(db.String(50), default='annuelle')  # Périodicité des tests
    dernier_test = db.Column(db.DateTime)
    prochain_test = db.Column(db.DateTime)
    resultats_tests = db.Column(db.JSON, default=[])  # Historique des tests
    
    # ============================================
    # STATUT
    # ============================================
    statut = db.Column(db.String(30), default='en_redaction')  # en_redaction, en_relecture, valide, obsolète, archive
    niveau_maturite = db.Column(db.Integer, default=1)  # 1-5
    
    # ============================================
    # ARCHIVAGE
    # ============================================
    is_archived = db.Column(db.Boolean, default=False)
    archived_at = db.Column(db.DateTime)
    archived_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    archive_reason = db.Column(db.String(255))
    
    # ============================================
    # AUDIT
    # ============================================
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)
    
    # Relations
    pole = db.relationship('Pole', foreign_keys=[pole_id])
    direction = db.relationship('Direction', foreign_keys=[direction_id])
    service = db.relationship('Service', foreign_keys=[service_id])
    responsable = db.relationship('User', foreign_keys=[responsable_id])
    redacteur = db.relationship('User', foreign_keys=[redacteur_id])
    valideur = db.relationship('User', foreign_keys=[valideur_id])
    createur = db.relationship('User', foreign_keys=[created_by])
    archive_user = db.relationship('User', foreign_keys=[archived_by])
    
    actions = db.relationship('ActionPCA', back_populates='plan', lazy=True, cascade='all, delete-orphan')
    exercices = db.relationship('ExercicePCA', back_populates='plan', lazy=True, cascade='all, delete-orphan')
    documents = db.relationship('DocumentPCA', back_populates='plan', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<PCA {self.reference}: {self.titre}>'
    
    def get_maturite_label(self):
        labels = {1: 'Initial', 2: 'Répétable', 3: 'Défini', 4: 'Géré', 5: 'Optimisé'}
        return labels.get(self.niveau_maturite, 'Non défini')
    
    def get_statut_label(self):
        labels = {
            'en_redaction': 'En rédaction',
            'en_relecture': 'En relecture',
            'valide': 'Validé',
            'obsolète': 'Obsolète',
            'archive': 'Archivé'
        }
        return labels.get(self.statut, self.statut)
    
    def get_statut_css(self):
        css = {
            'en_redaction': 'warning',
            'en_relecture': 'info',
            'valide': 'success',
            'obsolète': 'danger',
            'archive': 'secondary'
        }
        return css.get(self.statut, 'secondary')
    
    def get_taux_realisation(self):
        """Calcule le taux de complétion du PCA"""
        if not self.actions:
            return 0
        total = len(self.actions)
        terminees = len([a for a in self.actions if a.statut == 'termine'])
        return round((terminees / total * 100), 1) if total > 0 else 0
    
    def get_delais_conformite(self):
        """Vérifie si les délais sont conformes"""
        if self.delai_arret_max and self.duree_critique:
            # Logique de calcul
            return True
        return None
    
    def archiver(self, user_id, raison=None):
        self.is_archived = True
        self.archived_at = datetime.utcnow()
        self.archived_by = user_id
        self.archive_reason = raison
        self.statut = 'archive'
    
    def desarchiver(self):
        self.is_archived = False
        self.archived_at = None
        self.archived_by = None
        self.archive_reason = None
        self.statut = 'en_redaction'


class ActionPCA(db.Model):
    """Actions du plan de continuité"""
    __tablename__ = 'actions_pca'
    
    id = db.Column(db.Integer, primary_key=True)
    reference = db.Column(db.String(50), unique=True, nullable=False)
    plan_id = db.Column(db.Integer, db.ForeignKey('plans_continuite_activite.id'), nullable=False)
    
    intitule = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    phase = db.Column(db.String(50), default='preparation')  # preparation, crise, reprise, retour
    
    priorite = db.Column(db.String(20), default='moyenne')  # haute, moyenne, basse
    delai_execution = db.Column(db.String(50))  # délai d'exécution (en heures)
    
    responsable_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    equipe = db.Column(db.JSON, default=[])  # Liste des membres impliqués
    
    date_debut = db.Column(db.Date)
    date_fin_prevue = db.Column(db.Date)
    date_fin_reelle = db.Column(db.Date)
    
    statut = db.Column(db.String(20), default='a_faire')  # a_faire, en_cours, termine, bloque
    pourcentage_realisation = db.Column(db.Integer, default=0)
    commentaire = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)
    
    # Relations
    plan = db.relationship('PlanContinuiteActivite', back_populates='actions')
    responsable = db.relationship('User', foreign_keys=[responsable_id])
    createur = db.relationship('User', foreign_keys=[created_by])
    
    def __repr__(self):
        return f'<ActionPCA {self.reference}>'


class ExercicePCA(db.Model):
    """Exercices et tests du PCA"""
    __tablename__ = 'exercices_pca'
    
    id = db.Column(db.Integer, primary_key=True)
    reference = db.Column(db.String(50), unique=True, nullable=False)
    plan_id = db.Column(db.Integer, db.ForeignKey('plans_continuite_activite.id'), nullable=False)
    
    nom = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    type_exercice = db.Column(db.String(50), default='table_top')  # table_top, technique, grandeur_nature
    
    date_exercice = db.Column(db.DateTime, nullable=False)
    duree = db.Column(db.String(50))  # durée en heures
    
    participants = db.Column(db.JSON, default=[])  # Liste des participants
    observateurs = db.Column(db.JSON, default=[])  # Liste des observateurs
    
    scenario = db.Column(db.Text)  # Scénario de l'exercice
    objectifs = db.Column(db.JSON, default=[])  # Objectifs de l'exercice
    
    resultats = db.Column(db.Text)  # Résultats de l'exercice
    points_forts = db.Column(db.JSON, default=[])
    axes_amelioration = db.Column(db.JSON, default=[])
    actions_correctives = db.Column(db.JSON, default=[])
    
    note = db.Column(db.Integer)  # Note sur 100
    statut = db.Column(db.String(20), default='planifie')  # planifie, realise, annule, reporte
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)
    
    # Relations
    plan = db.relationship('PlanContinuiteActivite', back_populates='exercices')
    createur = db.relationship('User', foreign_keys=[created_by])
    
    def __repr__(self):
        return f'<ExercicePCA {self.reference}>'


class DocumentPCA(db.Model):
    """Documents attachés au PCA"""
    __tablename__ = 'documents_pca'
    
    id = db.Column(db.Integer, primary_key=True)
    plan_id = db.Column(db.Integer, db.ForeignKey('plans_continuite_activite.id'), nullable=False)
    
    nom_fichier = db.Column(db.String(255), nullable=False)
    nom_unique = db.Column(db.String(255), nullable=False, unique=True)
    chemin_fichier = db.Column(db.String(500), nullable=False)
    type_fichier = db.Column(db.String(100), nullable=False)
    taille = db.Column(db.Integer, nullable=False)
    
    categorie = db.Column(db.String(50), default='document')  # document, procedure, schema, rapport
    description = db.Column(db.String(500))
    
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    uploaded_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)
    
    # Relations
    plan = db.relationship('PlanContinuiteActivite', back_populates='documents')
    uploader = db.relationship('User', foreign_keys=[uploaded_by])
    
    def get_taille_formatee(self):
        if self.taille < 1024:
            return f"{self.taille} o"
        elif self.taille < 1024 * 1024:
            return f"{self.taille / 1024:.1f} Ko"
        else:
            return f"{self.taille / (1024 * 1024):.1f} Mo"


# ========================
# MODÈLE INCIDENT (VERSION COMPLÈTE)
# ========================

class Incident(db.Model):
    """Gestion complète des incidents avec workflow avancé"""
    __tablename__ = 'incidents'
    
    # ==================== IDENTIFIANTS DE BASE ====================
    id = db.Column(db.Integer, primary_key=True)
    reference = db.Column(db.String(30), unique=True, nullable=False)
    titre = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    
    # ==================== CLASSIFICATION ====================
    gravite = db.Column(db.String(20), default='moyenne')  # critique, elevee, moyenne, mineure
    type_incident = db.Column(db.String(50))  # securite, conformite, operationnel, technique, juridique
    statut = db.Column(db.String(20), default='ouvert', index=True)  # ouvert, en_cours, resolu, ferme, rejete
    
    # ==================== NIVEAU D'ESCALADE ====================
    niveau_escalade = db.Column(db.Integer, default=1)  # 1, 2, 3
    escalation_auto = db.Column(db.Boolean, default=False)
    escalation_date = db.Column(db.DateTime)
    raison_escalade = db.Column(db.Text)
    
    # ==================== APPROBATION ====================
    approbation_requise = db.Column(db.Boolean, default=False)
    approbation_statut = db.Column(db.String(20), default='en_attente')  # en_attente, approuve, rejete
    approbation_par_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    approbation_date = db.Column(db.DateTime)
    commentaire_approbation = db.Column(db.Text)
    
    # ==================== DATES ====================
    date_occurrence = db.Column(db.DateTime, nullable=False)
    date_detection = db.Column(db.DateTime, default=datetime.utcnow)
    date_resolution = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # ==================== SLA ====================
    sla_heures = db.Column(db.Integer, default=48)
    sla_date_limite = db.Column(db.DateTime)
    sla_viole = db.Column(db.Boolean, default=False)
    
    # ==================== DÉLAIS D'ESCALADE ====================
    delai_escalade_niveau2 = db.Column(db.Integer, default=48)
    delai_escalade_niveau3 = db.Column(db.Integer, default=72)
    
    # ==================== NOTIFICATIONS ====================
    notification_envoyee_niveau2 = db.Column(db.Boolean, default=False)
    notification_envoyee_niveau3 = db.Column(db.Boolean, default=False)
    derniere_action_date = db.Column(db.DateTime, default=datetime.utcnow)
    
    # ==================== LIENS MÉTIER ====================
    risque_id = db.Column(db.Integer, db.ForeignKey('risques.id'))
    dispositif_id = db.Column(db.Integer, db.ForeignKey('dispositifs_maitrise.id'))
    plan_action_id = db.Column(db.Integer, db.ForeignKey('plans_action.id'))
    
    # ==================== ACTEURS ====================
    declare_par_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    responsable_resolution_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    superviseur_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    directeur_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    # ==================== RÉSOLUTION ====================
    cause_racine = db.Column(db.Text)
    actions_correctives = db.Column(db.Text)
    lecons_apprises = db.Column(db.Text)
    commentaire_cloture = db.Column(db.Text)
    
    # ==================== MÉTADONNÉES IA ====================
    analyse_ia = db.Column(db.Text)
    ia_score_confiance = db.Column(db.Float, default=0)
    ia_recommandations = db.Column(db.Text)
    
    # ==================== MULTI-TENANT ====================
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), index=True)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    is_archived = db.Column(db.Boolean, default=False)
    archived_at = db.Column(db.DateTime)
    archived_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    archive_reason = db.Column(db.String(200))
    
    # ==================== RELATIONS CORRIGÉES ====================
    risque = db.relationship('Risque', backref='incidents', foreign_keys=[risque_id])
    dispositif = db.relationship('DispositifMaitrise', backref='incidents', foreign_keys=[dispositif_id])
    plan_action = db.relationship('PlanAction', backref='incidents', foreign_keys=[plan_action_id])
    declare_par = db.relationship('User', foreign_keys=[declare_par_id], backref='incidents_declares')
    responsable = db.relationship('User', foreign_keys=[responsable_resolution_id], backref='incidents_responsables')
    superviseur = db.relationship('User', foreign_keys=[superviseur_id], backref='incidents_supervises')
    directeur = db.relationship('User', foreign_keys=[directeur_id], backref='incidents_directeur')
    approbateur = db.relationship('User', foreign_keys=[approbation_par_id])
    archiveur = db.relationship('User', foreign_keys=[archived_by])
    
    # ==================== GÉNÉRATION DE RÉFÉRENCE ROBUSTE ====================
    @classmethod
    def generer_reference_unique(cls, client_id=None, tentative=0):
        """
        Génère une référence unique pour l'incident avec gestion des conflits
        """
        annee = datetime.utcnow().year
        max_tentatives = 10
        
        # Construire la requête de base
        query = cls.query.filter(cls.reference.like(f'INC-{annee}-%'))
        if client_id:
            query = query.filter(cls.client_id == client_id)
        
        # Compter les incidents existants
        count = query.count()
        
        # Générer le numéro de base
        base_num = count + 1 + tentative
        
        # Générer la référence
        reference = f"INC-{annee}-{base_num:03d}"
        
        # Vérifier si la référence existe déjà
        existing = cls.query.filter_by(reference=reference).first()
        
        if existing and tentative < max_tentatives:
            # Conflit, réessayer avec tentative+1
            return cls.generer_reference_unique(client_id, tentative + 1)
        elif existing:
            # Échec après max_tentatives, utiliser un timestamp
            timestamp = int(datetime.utcnow().timestamp())
            reference = f"INC-{annee}-{timestamp}"
        
        return reference
    
    # Garder la méthode generer_reference pour compatibilité (appelle la nouvelle méthode)
    def generer_reference(self):
        """Méthode de compatibilité - appelle generer_reference_unique"""
        return self.generer_reference_unique(self.client_id)
    
    def __init__(self, **kwargs):
        super(Incident, self).__init__(**kwargs)
        if not self.reference:
            self.reference = self.generer_reference_unique(self.client_id)
        if not self.sla_date_limite and self.sla_heures:
            self.sla_date_limite = datetime.utcnow() + timedelta(hours=self.sla_heures)
    
    # ==================== MÉTHODES D'ESCALADE ====================
    def escalader(self, raison=None, auto=False, user_id=None):
        from services.escalade_service import EscaladeService
        return EscaladeService.escalader(self, auto=auto, raison=raison)
    
    def retro_escalader(self, niveau_cible=1, raison=None):
        from services.escalade_service import EscaladeService
        return EscaladeService.retro_escalader(self, niveau_cible, raison)
    
    def verifier_sla(self):
        from services.escalade_service import EscaladeService
        return EscaladeService.verifier_et_escalader_auto(self)
    
    def peut_escalader(self, user):
        if not user.is_authenticated:
            return False
        if user.role == 'super_admin':
            return True
        if self.niveau_escalade >= 3:
            return False
        if self.is_archived:
            return False
        if self.statut in ['ferme', 'resolu', 'rejete']:
            return False
        if self.responsable_resolution_id == user.id:
            return True
        if self.niveau_escalade == 1 and self.superviseur_id == user.id:
            return True
        if self.niveau_escalade == 2 and self.directeur_id == user.id:
            return True
        return False
    
    # ==================== MÉTHODES D'APPROBATION ====================
    def approuver(self, user_id, commentaire=None):
        self.approbation_statut = 'approuve'
        self.approbation_par_id = user_id
        self.approbation_date = datetime.utcnow()
        self.commentaire_approbation = commentaire
        self.statut = 'ferme'
        self.date_resolution = datetime.utcnow()
        self.updated_at = datetime.utcnow()
    
    def rejeter(self, user_id, commentaire):
        self.approbation_statut = 'rejete'
        self.approbation_par_id = user_id
        self.approbation_date = datetime.utcnow()
        self.commentaire_approbation = commentaire
        self.statut = 'en_cours'
        self.updated_at = datetime.utcnow()
    
    def peut_approuver(self, user):
        if not user.is_authenticated:
            return False
        if user.role == 'super_admin':
            return True
        if not self.approbation_requise:
            return False
        if self.approbation_statut != 'en_attente':
            return False
        if self.superviseur_id == user.id:
            return True
        if self.directeur_id == user.id:
            return True
        return False
    
    # ==================== MÉTHODES D'ARCHIVAGE ====================
    def archiver(self, user_id, raison):
        self.is_archived = True
        self.archived_at = datetime.utcnow()
        self.archived_by = user_id
        self.archive_reason = raison
        self.updated_at = datetime.utcnow()
    
    def desarchiver(self):
        self.is_archived = False
        self.archived_at = None
        self.archived_by = None
        self.archive_reason = None
        self.updated_at = datetime.utcnow()
    
    def peut_archiver(self, user):
        if not user.is_authenticated:
            return False
        if user.role == 'super_admin':
            return True
        if user.is_client_admin:
            return True
        return False
    
    def peut_modifier(self, user):
        if not user.is_authenticated:
            return False
        if user.role == 'super_admin':
            return True
        if user.is_client_admin:
            return True
        if user.id == self.created_by:
            return True
        if user.id == self.responsable_resolution_id:
            return True
        return False
    
    # ==================== MÉTHODES DE CALCUL ====================
    def get_delai_resolution(self):
        if self.date_resolution and self.date_occurrence:
            delta = self.date_resolution - self.date_occurrence
            return delta.days
        return None
    
    def get_heures_restantes_sla(self):
        if self.sla_date_limite and self.statut not in ['ferme', 'resolu']:
            delta = self.sla_date_limite - datetime.utcnow()
            return max(0, delta.total_seconds() / 3600)
        return None
    
    def get_raison_escalade(self):
        if self.raison_escalade:
            return self.raison_escalade
        if self.escalation_auto:
            return f"Escalade automatique - SLA dépassé ({self.sla_heures}h)"
        return "Escalade manuelle"
    
    # ==================== MÉTHODES DE LIBELLÉS ====================
    def get_gravite_label(self):
        labels = {'critique': 'Critique', 'elevee': 'Élevée', 'moyenne': 'Moyenne', 'mineure': 'Mineure'}
        return labels.get(self.gravite, self.gravite)
    
    def get_gravite_color(self):
        colors = {'critique': 'danger', 'elevee': 'warning', 'moyenne': 'info', 'mineure': 'success'}
        return colors.get(self.gravite, 'secondary')
    
    def get_type_label(self):
        labels = {'securite': 'Sécurité', 'conformite': 'Conformité', 'operationnel': 'Opérationnel', 
                  'technique': 'Technique', 'juridique': 'Juridique'}
        return labels.get(self.type_incident, self.type_incident)
    
    def get_statut_label(self):
        labels = {'ouvert': 'Ouvert', 'en_cours': 'En cours', 'resolu': 'Résolu', 'ferme': 'Fermé', 'rejete': 'Rejeté'}
        return labels.get(self.statut, self.statut)
    
    def get_statut_color(self):
        colors = {'ouvert': 'danger', 'en_cours': 'warning', 'resolu': 'info', 'ferme': 'success', 'rejete': 'secondary'}
        return colors.get(self.statut, 'secondary')
    
    def get_niveau_escalade_label(self):
        labels = {1: 'Niveau 1 (Support)', 2: 'Niveau 2 (Superviseur)', 3: 'Niveau 3 (Direction)'}
        return labels.get(self.niveau_escalade, f'Niveau {self.niveau_escalade}')
    
    def get_approbation_statut_label(self):
        labels = {'en_attente': 'En attente', 'approuve': 'Approuvé', 'rejete': 'Rejeté'}
        return labels.get(self.approbation_statut, self.approbation_statut)
    
    # ==================== MÉTHODES IA ====================
    def analyser_avec_ia(self):
        from services.incident_ia_service import IncidentIAService
        return IncidentIAService.analyser_incident(self)
    
    def predire_recurrence(self):
        from services.incident_ia_service import IncidentIAService
        return IncidentIAService.predire_recurrence(self)
    
    # ==================== MÉTHODES DE CONVERSION ====================
    def to_dict(self):
        import json
        return {
            'id': self.id,
            'reference': self.reference,
            'titre': self.titre,
            'description': self.description,
            'gravite': self.gravite,
            'gravite_label': self.get_gravite_label(),
            'gravite_color': self.get_gravite_color(),
            'type_incident': self.type_incident,
            'type_label': self.get_type_label(),
            'statut': self.statut,
            'statut_label': self.get_statut_label(),
            'statut_color': self.get_statut_color(),
            'niveau_escalade': self.niveau_escalade,
            'niveau_escalade_label': self.get_niveau_escalade_label(),
            'raison_escalade': self.get_raison_escalade(),
            'escalation_auto': self.escalation_auto,
            'escalation_date': self.escalade_date.isoformat() if self.escalade_date else None,
            'approbation_requise': self.approbation_requise,
            'approbation_statut': self.approbation_statut,
            'approbation_statut_label': self.get_approbation_statut_label(),
            'date_occurrence': self.date_occurrence.isoformat() if self.date_occurrence else None,
            'date_detection': self.date_detection.isoformat() if self.date_detection else None,
            'date_resolution': self.date_resolution.isoformat() if self.date_resolution else None,
            'delai_resolution': self.get_delai_resolution(),
            'sla_heures': self.sla_heures,
            'sla_date_limite': self.sla_date_limite.isoformat() if self.sla_date_limite else None,
            'sla_viole': self.sla_viole,
            'heures_restantes_sla': self.get_heures_restantes_sla(),
            'risque_id': self.risque_id,
            'dispositif_id': self.dispositif_id,
            'plan_action_id': self.plan_action_id,
            'declare_par': self.declare_par.username if self.declare_par else None,
            'responsable_resolution': self.responsable.username if self.responsable else None,
            'superviseur': self.superviseur.username if self.superviseur else None,
            'directeur': self.directeur.username if self.directeur else None,
            'cause_racine': self.cause_racine,
            'actions_correctives': self.actions_correctives,
            'lecons_apprises': self.lecons_apprises,
            'commentaire_cloture': self.commentaire_cloture,
            'analyse_ia': json.loads(self.analyse_ia) if self.analyse_ia else None,
            'ia_score_confiance': self.ia_score_confiance,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'is_archived': self.is_archived
        }
    
    def __repr__(self):
        return f'<Incident {self.reference}: {self.titre[:30]}>'

# ========================
# MODÈLE TICKET SUPPORT (NOUVEAU)
# ========================

class TicketSupport(db.Model):
    """Interface client pour déclarer des incidents"""
    __tablename__ = 'tickets_support'
    
    id = db.Column(db.Integer, primary_key=True)
    reference = db.Column(db.String(30), unique=True, nullable=False)
    
    # Informations client
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'))
    client_nom = db.Column(db.String(200))
    client_email = db.Column(db.String(120))
    client_telephone = db.Column(db.String(20))
    
    # Contenu du ticket
    sujet = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    pieces_jointes = db.Column(db.Text)  # URLs séparées par des virgules
    
    # Priorité (client)
    priorite_client = db.Column(db.String(20), default='normale')  # basse, normale, haute, critique
    
    # Statut
    statut = db.Column(db.String(20), default='nouveau')  # nouveau, en_cours, traite, ferme
    
    # Liens
    incident_id = db.Column(db.Integer, db.ForeignKey('incidents.id'))
    incident = db.relationship('Incident', backref='ticket')
    
    # Métadonnées
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    traite_par_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    traite_par = db.relationship('User')
    
    def generer_reference(self):
        annee = datetime.utcnow().year
        count = TicketSupport.query.filter(
            TicketSupport.reference.like(f'TKT-{annee}-%')
        ).count()
        return f"TKT-{annee}-{count + 1:04d}"
    
    def to_dict(self):
        return {
            'id': self.id,
            'reference': self.reference,
            'sujet': self.sujet,
            'description': self.description,
            'priorite_client': self.priorite_client,
            'statut': self.statut,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'incident_reference': self.incident.reference if self.incident else None
        }


# ========================
# MODÈLE HISTORIQUE INCIDENT (pour traçabilité)
# ========================

class IncidentHistorique(db.Model):
    """Historique des actions sur les incidents - Version corrigée sans conflit"""
    __tablename__ = 'incidents_historique'
    
    id = db.Column(db.Integer, primary_key=True)
    incident_id = db.Column(db.Integer, db.ForeignKey('incidents.id'), nullable=False)
    action = db.Column(db.String(100), nullable=False)
    details = db.Column(db.Text)
    utilisateur_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # ==================== RELATIONS SIMPLES ET SANS CONFLIT ====================
    # Relation simple UNIDIRECTIONNELLE (seulement depuis l'historique vers l'incident)
    incident = db.relationship('Incident', foreign_keys=[incident_id])
    utilisateur = db.relationship('User', foreign_keys=[utilisateur_id])
    
    # ==================== MÉTHODES ====================
    
    def get_action_label(self):
        """Retourne le libellé de l'action"""
        labels = {
            'creation': 'Création',
            'modification': 'Modification',
            'resolution': 'Résolution',
            'escalade_manuelle': 'Escalade manuelle',
            'escalade_auto': 'Escalade automatique',
            'escalade_niveau_2': 'Escalade niveau 2',
            'escalade_niveau_3': 'Escalade niveau 3',
            'retro_escalade': 'Rétro-escalade',
            'approbation_approuve': 'Approbation acceptée',
            'approbation_rejete': 'Approbation rejetée',
            'archivage': 'Archivage',
            'restauration': 'Restauration',
            'changement_responsable': 'Changement de responsable'
        }
        return labels.get(self.action, self.action.replace('_', ' ').title())
    
    def get_action_icon(self):
        """Retourne l'icône pour l'action"""
        icons = {
            'creation': 'fa-plus-circle',
            'modification': 'fa-edit',
            'resolution': 'fa-check-circle',
            'escalade_manuelle': 'fa-arrow-up',
            'escalade_auto': 'fa-arrow-up',
            'escalade_niveau_2': 'fa-arrow-up',
            'escalade_niveau_3': 'fa-arrow-up',
            'retro_escalade': 'fa-arrow-down',
            'approbation_approuve': 'fa-stamp',
            'approbation_rejete': 'fa-times-circle',
            'archivage': 'fa-archive',
            'restauration': 'fa-undo',
            'changement_responsable': 'fa-user-switch'
        }
        return icons.get(self.action, 'fa-info-circle')
    
    def get_action_color(self):
        """Retourne la couleur pour l'action"""
        colors = {
            'creation': 'success',
            'modification': 'primary',
            'resolution': 'success',
            'escalade_manuelle': 'warning',
            'escalade_auto': 'danger',
            'escalade_niveau_2': 'warning',
            'escalade_niveau_3': 'danger',
            'retro_escalade': 'info',
            'approbation_approuve': 'success',
            'approbation_rejete': 'danger',
            'archivage': 'secondary',
            'restauration': 'info',
            'changement_responsable': 'warning'
        }
        return colors.get(self.action, 'secondary')
    
    def get_formatted_date(self):
        """Retourne la date formatée"""
        if self.created_at:
            return self.created_at.strftime('%d/%m/%Y à %H:%M')
        return 'Date inconnue'
    
    def get_time_ago(self):
        """Retourne le temps écoulé depuis la création"""
        if not self.created_at:
            return "Récemment"
        
        now = datetime.utcnow()
        diff = now - self.created_at
        
        if diff.days > 365:
            years = diff.days // 365
            return f"il y a {years} an{'s' if years > 1 else ''}"
        elif diff.days > 30:
            months = diff.days // 30
            return f"il y a {months} mois"
        elif diff.days > 7:
            weeks = diff.days // 7
            return f"il y a {weeks} semaine{'s' if weeks > 1 else ''}"
        elif diff.days > 0:
            return f"il y a {diff.days} jour{'s' if diff.days > 1 else ''}"
        elif diff.seconds >= 3600:
            hours = diff.seconds // 3600
            return f"il y a {hours} heure{'s' if hours > 1 else ''}"
        elif diff.seconds >= 60:
            minutes = diff.seconds // 60
            return f"il y a {minutes} minute{'s' if minutes > 1 else ''}"
        else:
            return "À l'instant"
    
    def to_dict(self):
        """Convertit l'historique en dictionnaire"""
        return {
            'id': self.id,
            'incident_id': self.incident_id,
            'action': self.action,
            'action_label': self.get_action_label(),
            'action_icon': self.get_action_icon(),
            'action_color': self.get_action_color(),
            'details': self.details,
            'utilisateur_id': self.utilisateur_id,
            'utilisateur_nom': self.utilisateur.username if self.utilisateur else 'Système',
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'date_formatee': self.get_formatted_date(),
            'time_ago': self.get_time_ago()
        }
    
    def __repr__(self):
        return f'<IncidentHistorique {self.id}: {self.action} pour incident {self.incident_id}>'


# ============================================
# WORKFLOW D'APPROBATION POUR LES AUDITS
# ============================================

class WorkflowApprobation(db.Model):
    """Workflow d'approbation pour les audits avec approbateurs spécifiques"""
    __tablename__ = 'workflows_approbation'
    
    id = db.Column(db.Integer, primary_key=True)
    audit_id = db.Column(db.Integer, db.ForeignKey('audits.id'), nullable=False)
    
    # Étape actuelle du workflow
    etape_actuelle = db.Column(db.String(50), default='brouillon')  # brouillon, en_relecture, approuve, valide, rejete
    historique_etapes = db.Column(db.JSON, default=[])
    
    # ============================================
    # APPROBATEURS SPÉCIFIQUES (NOUVEAU)
    # ============================================
    approbateur_niveau1_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    approbateur_niveau2_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    approbateur_niveau1_nom = db.Column(db.String(200), nullable=True)
    approbateur_niveau2_nom = db.Column(db.String(200), nullable=True)
    
    # Dates importantes
    date_envoi_relecture = db.Column(db.DateTime, nullable=True)
    date_approbation_niveau1 = db.Column(db.DateTime, nullable=True)
    date_approbation_niveau2 = db.Column(db.DateTime, nullable=True)
    date_rejet = db.Column(db.DateTime, nullable=True)
    date_validation_finale = db.Column(db.DateTime, nullable=True)
    
    # Commentaires
    commentaire_relecture = db.Column(db.Text, nullable=True)
    commentaire_approbation_niveau1 = db.Column(db.Text, nullable=True)
    commentaire_approbation_niveau2 = db.Column(db.Text, nullable=True)
    commentaire_rejet = db.Column(db.Text, nullable=True)
    
    # Notifications
    notification_envoyee_relecture = db.Column(db.Boolean, default=False)
    notification_envoyee_approbation_niveau1 = db.Column(db.Boolean, default=False)
    notification_envoyee_approbation_niveau2 = db.Column(db.Boolean, default=False)
    
    # Multi-tenant
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relations
    audit = db.relationship('Audit', backref='workflow_approbation', foreign_keys=[audit_id])
    approbateur_niveau1 = db.relationship('User', foreign_keys=[approbateur_niveau1_id], lazy='joined')
    approbateur_niveau2 = db.relationship('User', foreign_keys=[approbateur_niveau2_id], lazy='joined')
    createur = db.relationship('User', foreign_keys=[created_by], lazy='joined')
    
    # ============================================
    # MÉTHODES PRINCIPALES DU WORKFLOW
    # ============================================
    
    def envoyer_en_relecture(self, user_id, commentaire=None):
        """Envoyer l'audit en relecture (Niveau 1)"""
        from datetime import datetime
        
        if self.etape_actuelle != 'brouillon':
            raise ValueError("Seul un audit en brouillon peut être envoyé en relecture")
        
        ancienne_etape = self.etape_actuelle
        self.etape_actuelle = 'en_relecture'
        self.date_envoi_relecture = datetime.utcnow()
        self.commentaire_relecture = commentaire
        
        # Ajouter à l'historique
        self._ajouter_historique(ancienne_etape, 'en_relecture', user_id, commentaire)
        
        # Mettre à jour le statut de l'audit
        if self.audit:
            self.audit.statut = 'en_validation'
            self.audit.sous_statut = 'relecture'
        
        return True
    
    def approuver_niveau1(self, user_id, commentaire=None):
        """Approbation niveau 1 (responsable qualité)"""
        from datetime import datetime
        
        if self.etape_actuelle != 'en_relecture':
            raise ValueError("L'audit doit être en relecture pour être approuvé niveau 1")
        
        ancienne_etape = self.etape_actuelle
        self.etape_actuelle = 'approuve'
        self.date_approbation_niveau1 = datetime.utcnow()
        self.approbateur_niveau1_id = user_id
        self.commentaire_approbation_niveau1 = commentaire
        
        # Récupérer le nom de l'approbateur
        user = User.query.get(user_id)
        if user:
            self.approbateur_niveau1_nom = user.username
        
        self._ajouter_historique(ancienne_etape, 'approuve', user_id, commentaire)
        
        return True
    
    def approuver_niveau2(self, user_id, commentaire=None):
        """Approbation niveau 2 (direction) - Approbation finale"""
        from datetime import datetime
        
        if self.etape_actuelle != 'approuve' and self.etape_actuelle != 'en_relecture':
            raise ValueError("L'audit doit avoir été approuvé niveau 1")
        
        ancienne_etape = self.etape_actuelle
        self.etape_actuelle = 'valide'
        self.date_approbation_niveau2 = datetime.utcnow()
        self.approbateur_niveau2_id = user_id
        self.commentaire_approbation_niveau2 = commentaire
        
        # Récupérer le nom de l'approbateur
        user = User.query.get(user_id)
        if user:
            self.approbateur_niveau2_nom = user.username
        
        self._ajouter_historique(ancienne_etape, 'valide', user_id, commentaire)
        
        # Mettre à jour le statut de l'audit
        if self.audit:
            self.audit.statut = 'termine'
            self.audit.sous_statut = 'valide'
        
        return True
    
    def rejeter(self, user_id, raison):
        """Rejeter l'audit"""
        from datetime import datetime
        
        if self.etape_actuelle not in ['en_relecture', 'approuve']:
            raise ValueError("L'audit doit être en relecture ou en approbation pour être rejeté")
        
        ancienne_etape = self.etape_actuelle
        self.etape_actuelle = 'rejete'
        self.date_rejet = datetime.utcnow()
        self.commentaire_rejet = raison
        
        self._ajouter_historique(ancienne_etape, 'rejete', user_id, raison)
        
        # Remettre en brouillon pour correction
        if self.audit:
            self.audit.statut = 'planifie'
            self.audit.sous_statut = 'correction'
        
        return True
    
    def valider_final(self, user_id, commentaire=None):
        """Validation finale après corrections"""
        from datetime import datetime
        
        if self.etape_actuelle != 'rejete':
            raise ValueError("Seul un audit rejeté peut être validé finalement")
        
        ancienne_etape = self.etape_actuelle
        self.etape_actuelle = 'valide'
        self.date_validation_finale = datetime.utcnow()
        self.commentaire_approbation_niveau2 = commentaire
        
        self._ajouter_historique(ancienne_etape, 'valide', user_id, commentaire)
        
        if self.audit:
            self.audit.statut = 'termine'
            self.audit.sous_statut = 'valide'
        
        return True
    
    def _ajouter_historique(self, ancienne, nouvelle, user_id, commentaire):
        """Ajouter une entrée dans l'historique"""
        from models import User
        from datetime import datetime
        
        if not self.historique_etapes:
            self.historique_etapes = []
        
        # Récupérer le nom de l'utilisateur
        user = User.query.get(user_id)
        utilisateur_nom = user.username if user else 'Système'
        
        self.historique_etapes.append({
            'date': datetime.utcnow().isoformat(),
            'ancienne_etape': ancienne,
            'nouvelle_etape': nouvelle,
            'utilisateur_id': user_id,
            'utilisateur_nom': utilisateur_nom,
            'commentaire': commentaire
        })
        
        # Garder seulement les 50 derniers
        if len(self.historique_etapes) > 50:
            self.historique_etapes = self.historique_etapes[-50:]
    
    # ============================================
    # MÉTHODES POUR LES APPROBATEURS SPÉCIFIQUES
    # ============================================
    
    def set_approbateur_niveau1(self, user_id):
        """Définit l'approbateur niveau 1"""
        from models import User
        
        self.approbateur_niveau1_id = user_id
        if user_id:
            user = User.query.get(user_id)
            self.approbateur_niveau1_nom = user.username if user else None
        else:
            self.approbateur_niveau1_nom = None
    
    def set_approbateur_niveau2(self, user_id):
        """Définit l'approbateur niveau 2"""
        from models import User
        
        self.approbateur_niveau2_id = user_id
        if user_id:
            user = User.query.get(user_id)
            self.approbateur_niveau2_nom = user.username if user else None
        else:
            self.approbateur_niveau2_nom = None
    
    def get_approbateur_niveau1(self):
        """Retourne l'objet User de l'approbateur niveau 1"""
        if self.approbateur_niveau1_id:
            return User.query.get(self.approbateur_niveau1_id)
        return None
    
    def get_approbateur_niveau2(self):
        """Retourne l'objet User de l'approbateur niveau 2"""
        if self.approbateur_niveau2_id:
            return User.query.get(self.approbateur_niveau2_id)
        return None
    
    def get_destinataires_alerte_niveau1(self):
        """Récupère les destinataires pour les alertes niveau 1"""
        # Priorité 1: Approbateur spécifique
        if self.approbateur_niveau1_id:
            user = User.query.get(self.approbateur_niveau1_id)
            return [user] if user else []
        
        # Priorité 2: Approbateurs par rôle
        return User.query.filter(
            User.client_id == self.client_id,
            User.is_active == True,
            User.role.in_(['admin', 'manager', 'responsable_qualite'])
        ).all()
    
    def get_destinataires_alerte_niveau2(self):
        """Récupère les destinataires pour les alertes niveau 2"""
        # Priorité 1: Approbateur spécifique
        if self.approbateur_niveau2_id:
            user = User.query.get(self.approbateur_niveau2_id)
            return [user] if user else []
        
        # Priorité 2: Approbateurs par rôle
        return User.query.filter(
            User.client_id == self.client_id,
            User.is_active == True,
            User.role.in_(['admin', 'directeur', 'direction', 'dg'])
        ).all()
    
    # ============================================
    # MÉTHODES D'AFFICHAGE POUR LES TEMPLATES
    # ============================================
    
    def get_etape_label(self):
        """Retourne le libellé de l'étape actuelle pour l'affichage"""
        labels = {
            'brouillon': '📝 Brouillon',
            'en_relecture': '🔍 En relecture',
            'approuve': '✅ Approuvé (Niveau 1)',
            'valide': '✓ Validé',
            'rejete': '❌ Rejeté'
        }
        return labels.get(self.etape_actuelle, self.etape_actuelle)
    
    def get_etape_label_simple(self):
        """Retourne le libellé simple (sans icône)"""
        labels = {
            'brouillon': 'Brouillon',
            'en_relecture': 'En relecture',
            'approuve': 'Approuvé Niveau 1',
            'valide': 'Validé',
            'rejete': 'Rejeté'
        }
        return labels.get(self.etape_actuelle, self.etape_actuelle)
    
    def get_couleur_etape(self):
        """Retourne la couleur Bootstrap pour l'étape"""
        couleurs = {
            'brouillon': 'secondary',
            'en_relecture': 'warning',
            'approuve': 'info',
            'valide': 'success',
            'rejete': 'danger'
        }
        return couleurs.get(self.etape_actuelle, 'secondary')
    
    def get_etape_icone(self):
        """Retourne l'icône FontAwesome pour l'étape"""
        icones = {
            'brouillon': 'fa-pen',
            'en_relecture': 'fa-eye',
            'approuve': 'fa-stamp',
            'valide': 'fa-check-double',
            'rejete': 'fa-times'
        }
        return icones.get(self.etape_actuelle, 'fa-question-circle')
    
    def get_etape_description(self):
        """Retourne la description de l'étape actuelle"""
        descriptions = {
            'brouillon': 'Rédaction en cours, l\'audit n\'est pas encore soumis à validation',
            'en_relecture': 'En attente de validation par le responsable qualité',
            'approuve': 'Validé niveau 1, en attente de la validation finale de la direction',
            'valide': 'Audit complètement validé et finalisé',
            'rejete': 'Audit rejeté, des corrections sont nécessaires'
        }
        return descriptions.get(self.etape_actuelle, 'Statut inconnu')
    
    def get_progression_pourcentage(self):
        """Retourne le pourcentage de progression du workflow"""
        progression = {
            'brouillon': 0,
            'en_relecture': 33,
            'approuve': 66,
            'valide': 100,
            'rejete': 0
        }
        return progression.get(self.etape_actuelle, 0)
    
    # ============================================
    # MÉTHODES DE VÉRIFICATION DES PERMISSIONS
    # ============================================
    
    def peut_approuver_niveau1(self, user):
        """Vérifie si l'utilisateur peut approuver niveau 1"""
        if not user.is_authenticated:
            return False
        if self.etape_actuelle != 'en_relecture':
            return False
        if user.role == 'super_admin':
            return True
        if user.is_client_admin:
            return True
        if self.approbateur_niveau1_id == user.id:
            return True
        if hasattr(user, 'has_permission') and user.has_permission('can_approve_audit_level1'):
            return True
        return False
    
    def peut_approuver_niveau2(self, user):
        """Vérifie si l'utilisateur peut approuver niveau 2"""
        if not user.is_authenticated:
            return False
        if self.etape_actuelle != 'approuve':
            return False
        if user.role == 'super_admin':
            return True
        if user.is_client_admin:
            return True
        if self.approbateur_niveau2_id == user.id:
            return True
        if hasattr(user, 'has_permission') and user.has_permission('can_approve_audit_level2'):
            return True
        return False
    
    def peut_rejeter(self, user):
        """Vérifie si l'utilisateur peut rejeter l'audit"""
        if not user.is_authenticated:
            return False
        if self.etape_actuelle not in ['en_relecture', 'approuve']:
            return False
        if user.role == 'super_admin':
            return True
        if user.is_client_admin:
            return True
        if self.approbateur_niveau1_id == user.id or self.approbateur_niveau2_id == user.id:
            return True
        return False
    
    def get_jours_dans_etape(self):
        """Retourne le nombre de jours passés dans l'étape actuelle"""
        from datetime import datetime
        
        date_reference = None
        if self.etape_actuelle == 'en_relecture':
            date_reference = self.date_envoi_relecture
        elif self.etape_actuelle == 'approuve':
            date_reference = self.date_approbation_niveau1
        elif self.etape_actuelle == 'rejete':
            date_reference = self.date_rejet
        elif self.etape_actuelle == 'valide':
            date_reference = self.date_approbation_niveau2 or self.date_validation_finale
        
        if date_reference:
            delta = datetime.utcnow() - date_reference
            return delta.days
        return 0
    
    def est_en_retard(self, seuil_jours=7):
        """Vérifie si l'étape actuelle dépasse le seuil de jours"""
        if self.etape_actuelle in ['en_relecture', 'approuve']:
            jours = self.get_jours_dans_etape()
            return jours > seuil_jours
        return False
    
    # ============================================
    # MÉTHODES DE SÉRIALISATION
    # ============================================
    
    def to_dict(self):
        """Convertit l'objet en dictionnaire pour l'API"""
        from models import User
        
        approbateur_niveau1_data = None
        if self.approbateur_niveau1_id:
            user = User.query.get(self.approbateur_niveau1_id)
            if user:
                approbateur_niveau1_data = {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'role': user.role
                }
        
        approbateur_niveau2_data = None
        if self.approbateur_niveau2_id:
            user = User.query.get(self.approbateur_niveau2_id)
            if user:
                approbateur_niveau2_data = {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'role': user.role
                }
        
        return {
            'id': self.id,
            'audit_id': self.audit_id,
            'etape_actuelle': self.etape_actuelle,
            'etape_label': self.get_etape_label(),
            'etape_couleur': self.get_couleur_etape(),
            'etape_icone': self.get_etape_icone(),
            'progression': self.get_progression_pourcentage(),
            'historique': self.historique_etapes,
            'dates': {
                'envoi_relecture': self.date_envoi_relecture.isoformat() if self.date_envoi_relecture else None,
                'approbation_niveau1': self.date_approbation_niveau1.isoformat() if self.date_approbation_niveau1 else None,
                'approbation_niveau2': self.date_approbation_niveau2.isoformat() if self.date_approbation_niveau2 else None,
                'rejet': self.date_rejet.isoformat() if self.date_rejet else None,
                'validation_finale': self.date_validation_finale.isoformat() if self.date_validation_finale else None
            },
            'commentaires': {
                'relecture': self.commentaire_relecture,
                'approbation_niveau1': self.commentaire_approbation_niveau1,
                'approbation_niveau2': self.commentaire_approbation_niveau2,
                'rejet': self.commentaire_rejet
            },
            'approbateurs': {
                'niveau1_id': self.approbateur_niveau1_id,
                'niveau1_nom': self.approbateur_niveau1_nom,
                'niveau1_data': approbateur_niveau1_data,
                'niveau2_id': self.approbateur_niveau2_id,
                'niveau2_nom': self.approbateur_niveau2_nom,
                'niveau2_data': approbateur_niveau2_data
            },
            'est_en_retard': self.est_en_retard(),
            'jours_dans_etape': self.get_jours_dans_etape(),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def __repr__(self):
        return f'<WorkflowApprobation {self.id} - Audit {self.audit_id} - {self.get_etape_label()}>'

# Modèle pour les clés API
class ApiKey(db.Model):
    __tablename__ = 'api_keys'
    
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    api_key = db.Column(db.String(64), unique=True, nullable=False)
    api_secret = db.Column(db.String(128), nullable=False)
    
    # Permissions
    permissions = db.Column(db.JSON, default={
        'read_audits': True,
        'write_audits': False,
        'read_constatations': True,
        'write_constatations': False,
        'read_recommandations': True,
        'write_recommandations': False,
        'read_plans_action': True,
        'write_plans_action': False,
        'read_risques': True,
        'write_risques': False,
        'read_kri': True,
        'write_kri': False,
        'read_veille': True,
        'write_veille': False
    })
    
    # Rate limiting
    rate_limit = db.Column(db.Integer, default=1000)  # Requêtes par heure
    rate_limit_window = db.Column(db.Integer, default=3600)  # Fenêtre en secondes
    
    # Statut
    is_active = db.Column(db.Boolean, default=True)
    expires_at = db.Column(db.DateTime, nullable=True)
    
    # Audit
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_used_at = db.Column(db.DateTime)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    # Relations
    client = db.relationship('Client')
    createur = db.relationship('User', foreign_keys=[created_by])
    
    def generate_keys(self):
        """Générer une nouvelle paire de clés API"""
        self.api_key = secrets.token_urlsafe(32)
        self.api_secret = secrets.token_urlsafe(64)
        return self.api_key, self.api_secret
    
    def verify_signature(self, signature, method, path, body=''):
        """Vérifier la signature HMAC-SHA256"""
        message = f"{method}\n{path}\n{body}\n{self.api_key}"
        expected = hmac.new(
            self.api_secret.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)
    
    def has_permission(self, permission):
        """Vérifier si la clé a une permission"""
        return self.permissions.get(permission, False)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'api_key': self.api_key,
            'permissions': self.permissions,
            'is_active': self.is_active,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


# ============================================
# MODÈLE POUR LES NOTIFICATIONS D'APPROBATION
# ============================================

class AlerteApprobation(db.Model):
    """Alertes d'approbation pour les audits"""
    __tablename__ = 'alertes_approbation'
    
    id = db.Column(db.Integer, primary_key=True)
    audit_id = db.Column(db.Integer, db.ForeignKey('audits.id'), nullable=False)
    
    # Type d'alerte
    type_alerte = db.Column(db.String(50), nullable=False)  # approbation_niveau1, approbation_niveau2, echeance, retard
    
    # Destinataire
    destinataire_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Message
    message = db.Column(db.Text, nullable=False)
    titre = db.Column(db.String(200), nullable=False)
    
    # Statut
    est_lue = db.Column(db.Boolean, default=False)
    est_envoyee = db.Column(db.Boolean, default=False)
    
    # Dates
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)
    date_envoi = db.Column(db.DateTime)
    date_echeance = db.Column(db.DateTime)
    
    # Multi-tenant
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)
    
    # Relations
    audit = db.relationship('Audit', backref='alertes_approbation')
    destinataire = db.relationship('User', foreign_keys=[destinataire_id])


# ============================================
# SERVICE D'ENVOI D'ALERTES
# ============================================
class ServiceAlerteApprobation:
    """Service pour gérer les alertes d'approbation - Version corrigée sans JSON cast"""
    
    @staticmethod
    def verifier_et_envoyer_alertes():
        """Vérifie tous les audits et envoie les alertes nécessaires"""
        aujourdhui = datetime.utcnow().date()
        alertes_envoyees = 0
        
        # 1. Récupérer tous les audits actifs
        audits = Audit.query.filter_by(is_archived=False).all()
        
        for audit in audits:
            workflow = WorkflowApprobation.query.filter_by(audit_id=audit.id).first()
            if not workflow:
                continue
            
            # ============================================
            # 2. Alertes d'approbation selon l'étape du workflow
            # ============================================
            
            if workflow.etape_actuelle == 'en_relecture':
                # ✅ CORRIGÉ : Utiliser le rôle au lieu des permissions JSON
                approbateurs_niveau1 = User.query.filter(
                    User.client_id == audit.client_id,
                    User.is_active == True,
                    User.role.in_(['admin', 'manager', 'responsable_qualite'])
                ).all()
                
                for approbateur in approbateurs_niveau1:
                    ServiceAlerteApprobation._creer_alerte_approbation(
                        audit=audit,
                        destinataire=approbateur,
                        type_alerte='approbation_niveau1',
                        titre=f"🔍 Audit à valider: {audit.reference}",
                        message=f"L'audit '{audit.titre}' est en attente de votre validation (Niveau 1).",
                        workflow=workflow
                    )
                    alertes_envoyees += 1
            
            elif workflow.etape_actuelle == 'approuve':
                # ✅ CORRIGÉ : Utiliser le rôle au lieu des permissions JSON
                approbateurs_niveau2 = User.query.filter(
                    User.client_id == audit.client_id,
                    User.is_active == True,
                    User.role.in_(['admin', 'directeur', 'direction'])
                ).all()
                
                for approbateur in approbateurs_niveau2:
                    ServiceAlerteApprobation._creer_alerte_approbation(
                        audit=audit,
                        destinataire=approbateur,
                        type_alerte='approbation_niveau2',
                        titre=f"✅ Audit à approuver: {audit.reference}",
                        message=f"L'audit '{audit.titre}' est en attente de votre validation finale (Niveau 2).",
                        workflow=workflow
                    )
                    alertes_envoyees += 1
            
            # ============================================
            # 3. Alertes d'échéance pour les recommandations
            # ============================================
            
            echeances_proches = Recommandation.query.filter(
                Recommandation.audit_id == audit.id,
                Recommandation.date_echeance.isnot(None),
                Recommandation.statut != 'termine',
                Recommandation.date_echeance <= aujourdhui + timedelta(days=7),
                Recommandation.date_echeance >= aujourdhui
            ).all()
            
            for reco in echeances_proches:
                jours_restants = (reco.date_echeance - aujourdhui).days
                responsable = reco.responsable
                if responsable:
                    ServiceAlerteApprobation._creer_alerte_approbation(
                        audit=audit,
                        destinataire=responsable,
                        type_alerte='echeance',
                        titre=f"⚠️ Échéance dans {jours_restants} jours",
                        message=f"La recommandation '{reco.description[:100]}...' arrive à échéance le {reco.date_echeance.strftime('%d/%m/%Y')}.",
                        workflow=workflow,
                        date_echeance=reco.date_echeance
                    )
                    alertes_envoyees += 1
            
            # ============================================
            # 4. Alertes de retard
            # ============================================
            
            retards = Recommandation.query.filter(
                Recommandation.audit_id == audit.id,
                Recommandation.date_echeance.isnot(None),
                Recommandation.statut != 'termine',
                Recommandation.date_echeance < aujourdhui
            ).all()
            
            for reco in retards:
                responsable = reco.responsable
                if responsable:
                    jours_retard = (aujourdhui - reco.date_echeance).days
                    ServiceAlerteApprobation._creer_alerte_approbation(
                        audit=audit,
                        destinataire=responsable,
                        type_alerte='retard',
                        titre=f"🔴 RETARD de {jours_retard} jours",
                        message=f"La recommandation '{reco.description[:100]}...' est en retard depuis le {reco.date_echeance.strftime('%d/%m/%Y')}.",
                        workflow=workflow,
                        date_echeance=reco.date_echeance,
                        jours_retard=jours_retard
                    )
                    alertes_envoyees += 1
        
        return alertes_envoyees
    
    @staticmethod
    def _get_approbateurs_niveau1(client_id):
        """Récupère les approbateurs niveau 1 (responsables qualité) - VERSION CORRIGÉE"""
        return User.query.filter(
            User.client_id == client_id,
            User.is_active == True,
            User.role.in_(['admin', 'manager', 'responsable_qualite'])
        ).all()
    
    @staticmethod
    def _get_approbateurs_niveau2(client_id):
        """Récupère les approbateurs niveau 2 (direction) - VERSION CORRIGÉE"""
        return User.query.filter(
            User.client_id == client_id,
            User.is_active == True,
            User.role.in_(['admin', 'directeur', 'direction', 'dg'])
        ).all()
    
    @staticmethod
    def _creer_alerte_approbation(audit, destinataire, type_alerte, titre, message, workflow=None, date_echeance=None, jours_retard=None):
        """Crée une alerte d'approbation et une notification associée"""
        
        # 1. Créer l'alerte dans la base de données
        alerte = AlerteApprobation(
            audit_id=audit.id,
            destinataire_id=destinataire.id,
            type_alerte=type_alerte,
            titre=titre,
            message=message,
            client_id=audit.client_id,
            date_echeance=date_echeance
        )
        db.session.add(alerte)
        
        # 2. Créer une notification dans le système principal
        niveau_urgence = 'urgent' if type_alerte in ['retard', 'approbation_niveau2'] else 'important' if type_alerte == 'approbation_niveau1' else 'normal'
        
        notification = Notification(
            destinataire_id=destinataire.id,
            type_notification='alerte_approbation',
            titre=titre,
            message=message,
            urgence=niveau_urgence,
            entite_type='audit',
            entite_id=audit.id,
            client_id=audit.client_id
        )
        db.session.add(notification)
        
        # 3. Ajouter des métadonnées supplémentaires pour l'affichage
        if workflow:
            notification.donnees_supplementaires = {
                'workflow_etape': workflow.etape_actuelle,
                'audit_reference': audit.reference,
                'audit_titre': audit.titre,
                'type_alerte': type_alerte
            }
            
            if date_echeance:
                notification.donnees_supplementaires['date_echeance'] = date_echeance.isoformat()
            if jours_retard:
                notification.donnees_supplementaires['jours_retard'] = jours_retard
        
        db.session.commit()
        
        return alerte
    
    @staticmethod
    def get_alertes_non_lues(user_id, client_id=None):
        """Récupère les alertes non lues pour un utilisateur"""
        query = AlerteApprobation.query.filter(
            AlerteApprobation.destinataire_id == user_id,
            AlerteApprobation.est_lue == False
        )
        
        if client_id:
            query = query.filter(AlerteApprobation.client_id == client_id)
        
        return query.order_by(AlerteApprobation.date_creation.desc()).all()
    
    @staticmethod
    def get_alertes_par_type(user_id, type_alerte):
        """Récupère les alertes d'un type spécifique"""
        return AlerteApprobation.query.filter(
            AlerteApprobation.destinataire_id == user_id,
            AlerteApprobation.type_alerte == type_alerte,
            AlerteApprobation.est_lue == False
        ).order_by(AlerteApprobation.date_creation.desc()).all()
    
    @staticmethod
    def marquer_alerte_lue(alerte_id, user_id):
        """Marque une alerte comme lue"""
        alerte = AlerteApprobation.query.get(alerte_id)
        if not alerte:
            return False
        
        if alerte.destinataire_id != user_id:
            return False
        
        alerte.est_lue = True
        db.session.commit()
        return True
    
    @staticmethod
    def marquer_toutes_alertes_lues(user_id, client_id=None):
        """Marque toutes les alertes d'un utilisateur comme lues"""
        query = AlerteApprobation.query.filter(
            AlerteApprobation.destinataire_id == user_id,
            AlerteApprobation.est_lue == False
        )
        
        if client_id:
            query = query.filter(AlerteApprobation.client_id == client_id)
        
        count = query.update({'est_lue': True}, synchronize_session=False)
        db.session.commit()
        return count
    
    @staticmethod
    def get_statistiques_alertes(user_id, client_id=None):
        """Retourne les statistiques des alertes pour un utilisateur"""
        query = AlerteApprobation.query.filter(
            AlerteApprobation.destinataire_id == user_id,
            AlerteApprobation.est_lue == False
        )
        
        if client_id:
            query = query.filter(AlerteApprobation.client_id == client_id)
        
        alertes = query.all()
        
        return {
            'total': len(alertes),
            'par_type': {
                'approbation_niveau1': len([a for a in alertes if a.type_alerte == 'approbation_niveau1']),
                'approbation_niveau2': len([a for a in alertes if a.type_alerte == 'approbation_niveau2']),
                'echeance': len([a for a in alertes if a.type_alerte == 'echeance']),
                'retard': len([a for a in alertes if a.type_alerte == 'retard'])
            }
        }

