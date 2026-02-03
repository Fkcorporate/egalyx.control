from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime, date, timezone
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


# -------------------- USER --------------------
class User(UserMixin, db.Model):
    __tablename__ = 'user'
    
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
    

    # AJOUTER CES DEUX CHAMPS :
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'))
    is_client_admin = db.Column(db.Boolean, default=False)
    can_manage_users = db.Column(db.Boolean, default=False)

    can_view_users_list = db.Column(db.Boolean, default=False)
    
    # MODIFIER LA RELATION :
    client = db.relationship('Client', back_populates='utilisateurs')
    
    # Permissions spécifiques (JSON pour flexibilité)
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
            'can_block_users': False,  # Nouveau : Bloquer des utilisateurs
            'can_manage_permissions': False,  # Réactivé pour gestionnaires
            # Permissions spécifiques aux modules
            'module_cartographie': True,
            'module_kri': True,
            'module_audit': True,
            'module_veille': True,
            'module_processus': True,
            'module_questionnaires': True,
            'module_plans_action': True,
            'module_analyse_ia': False
        })
    
    # Relations - CORRECTION : Spécifier foreign_keys
    directions_managees = db.relationship('Direction', 
                                         back_populates='responsable', 
                                         foreign_keys='Direction.responsable_id',  # AJOUTÉ
                                         lazy=True)
    
    services_managees = db.relationship('Service', 
                                       back_populates='responsable', 
                                       foreign_keys='Service.responsable_id',  # AJOUTÉ
                                       lazy=True)
    
    processus_geres = db.relationship('Processus', 
                                     back_populates='responsable', 
                                     foreign_keys='Processus.responsable_id',  # AJOUTÉ
                                     lazy=True)
    
    # Relations avec les directions archivées (séparée)
    directions_archivees = db.relationship('Direction', 
                                         back_populates='archived_by_user', 
                                         foreign_keys='Direction.archived_by',  # AJOUTÉ
                                         lazy=True)
    
    # Relations avec les services archivés (séparée)
    services_archivees = db.relationship('Service', 
                                       back_populates='archived_by_user', 
                                       foreign_keys='Service.archived_by',  # AJOUTÉ
                                       lazy=True)
    
    # Relations avec EvaluationRisque
    evaluations_faites = db.relationship('EvaluationRisque', back_populates='evaluateur_final',
                                        foreign_keys='EvaluationRisque.evaluateur_final_id', lazy=True)
    
    validations_faites = db.relationship('EvaluationRisque', back_populates='validateur',
                                        foreign_keys='EvaluationRisque.validateur_id', lazy=True)
    
    pre_evaluations_faites = db.relationship('EvaluationRisque', back_populates='referent_pre_evaluation',
                                            foreign_keys='EvaluationRisque.referent_pre_evaluation_id', lazy=True)
    
    # Relations avec Cartographie
    cartographies_crees = db.relationship('Cartographie', back_populates='createur',
                                         foreign_keys='Cartographie.created_by', lazy=True)
    
    # Relations avec Risque
    risques_crees = db.relationship('Risque', back_populates='createur',
                                   foreign_keys='Risque.created_by', lazy=True)
    risques_archives = db.relationship('Risque', back_populates='archive_user',
                                       foreign_keys='Risque.archived_by', lazy=True)
    
    # Relations avec KRI
    kris_geres = db.relationship('KRI', back_populates='responsable_mesure', 
                                foreign_keys='KRI.responsable_mesure_id', lazy=True)
    
    kris_crees = db.relationship('KRI', back_populates='createur',
                                foreign_keys='KRI.created_by', lazy=True)
    
    kris_archives = db.relationship('KRI', back_populates='archive_par',
                                   foreign_keys='KRI.archived_by', lazy=True)
    
    # Relations avec Audit
    audits_realises = db.relationship('Audit', back_populates='responsable',
                                     foreign_keys='Audit.responsable_id', lazy=True)
    
    audits_crees = db.relationship('Audit', back_populates='createur',
                                  foreign_keys='Audit.created_by', lazy=True)
    
    # Relations avec autres modèles
    mesures_prises = db.relationship('MesureKRI', back_populates='createur', lazy=True)
    veilles_crees = db.relationship('VeilleReglementaire', back_populates='createur', lazy=True)
    actions_conformite = db.relationship('ActionConformite', back_populates='responsable', lazy=True)
    documents_veille = db.relationship('VeilleDocument', back_populates='uploader', 
                                      foreign_keys='VeilleDocument.uploaded_by', lazy=True)
    
    # Relations avec Logigramme
    logigrammes_crees = db.relationship('ProcessusActivite', back_populates='createur',
                                       foreign_keys='ProcessusActivite.created_by', lazy=True)
    
    # Journal d'activité
    activites = db.relationship('JournalActivite', back_populates='utilisateur',
                               foreign_keys='JournalActivite.utilisateur_id', lazy=True)
    
    # Plans d'action
    plans_action = db.relationship('PlanAction', back_populates='responsable',
                                  foreign_keys='PlanAction.responsable_id', lazy=True)
    
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
    
    notifications_recues = db.relationship('Notification', 
                                          back_populates='destinataire',
                                          foreign_keys='Notification.destinataire_id',
                                          lazy=True,
                                          order_by='Notification.created_at.desc()')

    # Méthodes pour les permissions
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def has_permission(self, permission):
        """Vérifie si l'utilisateur a une permission spécifique - VERSION DÉFINITIVE"""
        
        print(f"🔐 [DEBUG] Vérification permission '{permission}' pour {self.username} (rôle: {self.role}, client_admin: {self.is_client_admin})")
        
        # 1. SUPER ADMIN : TOUJOURS AUTORISÉ (sauf exceptions)
        if self.role == 'super_admin':
            print(f"   ✅ Super admin - accès immédiat")
            return True
        
        # 2. Vérifier si l'utilisateur est un ADMIN CLIENT (deux façons de vérifier)
        is_admin_client = (self.role == 'admin') or (getattr(self, 'is_client_admin', False))
        
        if is_admin_client:
            print(f"   👑 Utilisateur est un ADMIN CLIENT")
            
            # Liste COMPLÈTE des permissions OBLIGATOIRES pour admin client
            permissions_admin_obligatoires = {
                # Tableau de bord et visualisation
                'can_view_dashboard': True,
                'can_view_reports': True,
                'can_view_departments': True,
                'can_view_notifications': True,
                
                # Gestion des risques
                'can_manage_risks': True,
                'can_validate_risks': True,
                
                # Gestion des KRI
                'can_manage_kri': True,
                
                # Gestion des audits
                'can_manage_audit': True,
                'can_confirm_evaluations': True,
                
                # Plans d'action
                'can_manage_action_plans': True,
                'can_view_action_plans': True,
                
                # Gestion des utilisateurs
                'can_view_users_list': True,
                'can_edit_users': True,
                'can_manage_users': True,
                'can_create_users': True,
                'can_deactivate_users': True,
                'can_delete_users': True,
                
                # Gestion des départements
                'can_manage_departments': True,
                'can_access_all_departments': True,
                
                # Administration
                'can_manage_settings': True,
                'can_archive_data': True,
                'can_export_data': True,
                
                # Veille règlementaire (si module activé)
                'can_manage_regulatory': True if self.client and self.client.formule and 
                                               self.client.formule.modules.get('veille_reglementaire', False) else False,
                
                # Processus (si module activé)
                'can_manage_logigram': True if self.client and self.client.formule and 
                                             self.client.formule.modules.get('gestion_processus', False) else False,
                
                # Permissions à TOUJOURS FALSE pour admin client
                'can_manage_clients': False,
                'can_provision_servers': False,
                'can_manage_permissions': True,  # ADMIN client peut gérer les permissions de SES utilisateurs
            }
            
            # Vérifier si la permission est dans la liste des permissions admin obligatoires
            if permission in permissions_admin_obligatoires:
                value = permissions_admin_obligatoires[permission]
                print(f"   📋 Permission admin obligatoire '{permission}': {value}")
                return value
        
        # 3. Vérifier si l'utilisateur est un GESTIONNAIRE (manager)
        # 3. Vérifier si l'utilisateur est un GESTIONNAIRE (manager)
        if self.role == 'manager':
            print(f"   👤 Utilisateur est un GESTIONNAIRE (manager)")
            
            permissions_manager_base = {
                # Visualisation de base
                'can_view_dashboard': True,
                'can_view_reports': True,
                'can_view_departments': True,
                'can_view_notifications': True,
                
                # Gestion des risques
                'can_manage_risks': True,
                'can_validate_risks': True,
                
                # KRI
                'can_manage_kri': True,
                
                # Audit
                'can_manage_audit': True,
                
                # Plans d'action
                'can_view_action_plans': True,
                'can_manage_action_plans': True,
                
                # Accès aux départements
                'can_access_all_departments': True,
                
                # Export
                'can_export_data': True,
                
                # Gestion des utilisateurs - CORRECTION ICI !
                'can_manage_users': True,
                'can_edit_users': True,
                'can_view_users_list': True,
                'can_create_users': True,           # AJOUTÉ
                'can_deactivate_users': True,       # AJOUTÉ
                'can_delete_users': True,           # AJOUTÉ
                'can_manage_permissions': True,     # AJOUTÉ
                
                # Administration limitée
                'can_manage_settings': True,        # Peut gérer certains paramètres
                'can_manage_departments': True,     # Peut gérer les départements
                
                # Permissions réservées aux admin (toujours false pour manager)
                'can_manage_clients': False,
                'can_provision_servers': False,
            }
            
            if permission in permissions_manager_base:
                value = permissions_manager_base[permission]
                print(f"   📋 Permission manager '{permission}': {value}")
                return value
        
        # 4. Vérifier les permissions EXPLICITES dans user.permissions
        if self.permissions and permission in self.permissions:
            value = bool(self.permissions[permission])
            print(f"   📋 Permission explicite dans DB: {value}")
            return value
        
        # 5. Permissions par DÉFAUT selon le rôle (pour les rôles simples)
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
                'can_view_action_plans': True,  # Peut voir les plans qui le concernent
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
                'can_create_users': True,
            }
        }
        
        if self.role in role_defaults and permission in role_defaults[self.role]:
            value = role_defaults[self.role][permission]
            print(f"   📋 Permission par défaut pour rôle '{self.role}': {value}")
            return value
        
        # 6. Vérifier la formule du client pour les permissions liées aux modules
        if self.client and self.client.formule:
            formule = self.client.formule
            
            # Mapping des permissions liées aux modules
            permission_to_module = {
                'can_manage_regulatory': 'veille_reglementaire',
                'can_manage_logigram': 'gestion_processus',
                'can_manage_action_plans': 'audit_interne',
                'can_view_action_plans': 'audit_interne',
                'can_manage_risks': 'cartographie',
                'can_manage_kri': 'suivi_kri',
                'can_manage_audit': 'audit_interne',
            }
            
            if permission in permission_to_module:
                module_name = permission_to_module[permission]
                if module_name in formule.modules:
                    is_module_active = formule.modules[module_name]
                    print(f"   🔍 Permission liée au module '{module_name}': {is_module_active}")
                    
                    # Si le module est activé, la permission est accordée
                    if is_module_active:
                        return True
                    else:
                        print(f"   ❌ Module '{module_name}' désactivé dans la formule")
                        return False
        
        print(f"   ❌ Permission '{permission}' REFUSÉE par défaut")
        return False

    
    def get_allowed_sections(self):
        """Retourne les sections accessibles par l'utilisateur"""
        sections = []
        
        if self.has_permission('can_view_dashboard'):
            sections.append('dashboard')
        
        if self.has_permission('can_manage_risks'):
            sections.extend(['cartographie', 'risques', 'matrices'])
        
        if self.has_permission('can_manage_kri'):
            sections.append('kri')
        
        if self.has_permission('can_manage_audit'):
            sections.extend(['audit', 'plans_action', 'constatations'])
        
        if self.has_permission('can_manage_regulatory'):
            sections.append('veille')
        
        if self.has_permission('can_manage_logigram'):
            sections.append('logigrammes')
        
        if self.has_permission('can_manage_users'):
            sections.append('administration')
        
        if self.has_permission('can_view_reports'):
            sections.append('rapports')
        
        return sections

    # Dans votre modèle User, ajoutez cette méthode :
    def can_manage_user(self, target_user):
        """Vérifie si l'utilisateur peut gérer un autre utilisateur"""
        
        # 1. On ne peut pas gérer soi-même
        if self.id == target_user.id:
            return False
        
        # 2. Vérifier qu'ils sont dans le même client
        if self.client_id != target_user.client_id:
            return False
        
        # 3. SUPER ADMIN : peut gérer tout le monde
        if self.role == 'super_admin':
            return True
        
        # 4. CLIENT ADMIN : peut gérer tout le monde sauf autres admin
        if self.is_client_admin:
            # Un admin client peut gérer tout le monde SAUF :
            # - Lui-même (déjà exclu)
            # - D'autres admin client
            return not target_user.is_client_admin
        
        # 5. GESTIONNAIRE : peut gérer seulement les non-admin et non-gestionnaires
        if self.can_manage_users:
            # Un gestionnaire ne peut pas gérer :
            # - Lui-même (déjà exclu)
            # - Les admin client
            # - Les autres gestionnaires
            return (not target_user.is_client_admin and 
                    not target_user.can_manage_users)
        
        # 6. Par défaut : non
        return False
    
    def get_notification_preference(self, channel, event):
        """Obtenir la préférence de notification (corrigé)"""
        if not self.preferences_notifications:
            return True  # Par défaut, activé
            
        if channel not in self.preferences_notifications:
            return True
            
        return self.preferences_notifications[channel].get(event, True)
    
    def should_receive_notification(self, notification_type, channel='web'):
        """
        Vérifie si l'utilisateur devrait recevoir une notification
        basée sur ses préférences
        """
        # Vérifier si les notifications sont en pause
        if self.preferences_notifications and self.preferences_notifications.get('pause_until'):
            try:
                pause_date = self.preferences_notifications['pause_until']
                if isinstance(pause_date, str):
                    pause_date = datetime.strptime(pause_date, '%Y-%m-%d').date()
                elif isinstance(pause_date, datetime):
                    pause_date = pause_date.date()
                
                if pause_date and pause_date >= datetime.utcnow().date():
                    return False
            except Exception as e:
                print(f"⚠️ Erreur vérification pause: {e}")
        
        # Vérifier la préférence spécifique
        return self.get_notification_preference(channel, notification_type)
    
    def set_notification_preference(self, channel, event, value):
        """Définir une préférence de notification"""
        if channel not in self.preferences_notifications:
            self.preferences_notifications[channel] = {}
        self.preferences_notifications[channel][event] = value
    
    def get_notifications_non_lues_count(self):
        """Compter les notifications non lues"""
        from models import Notification
        return Notification.query.filter_by(
            destinataire_id=self.id,
            est_lue=False
        ).count()

    def get_accessible_data(self):
        """Retourne uniquement les données accessibles par l'utilisateur"""
        if self.role == 'super_admin':
            # Super admin voit tout
            return {}
        
        if self.is_client_admin:
            # Admin client voit les données de son client
            return {'client_id': self.client_id}
        
        # Utilisateur standard voit ses propres données + données de son client
        return {'client_id': self.client_id, 'created_by': self.id}
    
    def can_access_client(self, client_id):
        """Vérifie si l'utilisateur peut accéder à un client"""
        if self.role == 'super_admin':
            return True
        return self.client_id == client_id
    
    def get_notifications_recentes(self, limit=10):
        """Obtenir les notifications récentes"""
        from models import Notification
        return Notification.query.filter_by(
            destinataire_id=self.id
        ).order_by(
            Notification.created_at.desc()
        ).limit(limit).all()
    
    def get_role_display_name(self):
        """Retourne le nom d'affichage du rôle"""
        role_names = {
            'admin': 'Administrateur',
            'manager': 'Manager',
            'auditeur': 'Auditeur',
            'compliance': 'Responsable Conformité',
            'consultant': 'Consultant',
            'utilisateur': 'Utilisateur'
        }
        return role_names.get(self.role, self.role.title())
    
    def update_last_login(self):
        """Met à jour la date de dernière connexion"""
        self.last_login = datetime.utcnow()
        db.session.commit()
    
    def can_access_department(self, department_id):
        """Vérifie si l'utilisateur peut accéder à un département spécifique"""
        if self.has_permission('can_access_all_departments'):
            return True
        
        # Vérifier si l'utilisateur est responsable de ce département
        from models import Direction, Service
        if department_id:
            # Vérifier dans les directions
            direction = Direction.query.get(department_id)
            if direction and direction.responsable_id == self.id:
                return True
            
            # Vérifier dans les services
            service = Service.query.get(department_id)
            if service and service.responsable_id == self.id:
                return True
        
        return False
    
    # NOUVELLES MÉTHODES POUR LES AUDITS
    def can_edit_audit(self, audit):
        """Vérifie si l'utilisateur peut modifier un audit"""
        return (self.role in ['admin', 'referent'] or 
                self.id == audit.responsable_id or 
                self.id == audit.created_by)
    
    def can_edit_plan(self, plan):
        """Vérifie si l'utilisateur peut modifier un plan d'action - VERSION MULTI-TENANT"""
        
        # 1. SUPER ADMIN : peut tout faire
        if self.role == 'super_admin':
            return True
        
        # 2. Récupérer le client_id du plan
        plan_client_id = getattr(plan, 'client_id', None)
        
        # 3. Si le plan n'a pas de client_id, essayer de le trouver via les relations
        if plan_client_id is None:
            # Essayer de trouver le client_id via le risque
            if hasattr(plan, 'risque') and plan.risque:
                plan_client_id = getattr(plan.risque, 'client_id', None)
            # Essayer de trouver via l'audit
            elif hasattr(plan, 'audit') and plan.audit:
                plan_client_id = getattr(plan.audit, 'client_id', None)
            # Essayer de trouver via le créateur
            elif hasattr(plan, 'created_by'):
                createur = User.query.get(plan.created_by)
                if createur:
                    plan_client_id = createur.client_id
        
        # 4. Vérifier que l'utilisateur est dans le même client que le plan
        user_client_id = getattr(self, 'client_id', None)
        
        if plan_client_id is not None and user_client_id != plan_client_id:
            print(f"❌ Rejeté: client mismatch (user: {user_client_id}, plan: {plan_client_id})")
            return False
        
        # 5. ADMIN CLIENT : peut modifier tous les plans de son client
        if self.is_client_admin:
            print(f"✅ Admin client autorisé pour plan {plan.id}")
            return True
        
        # 6. CRÉATEUR DU PLAN : peut modifier
        if hasattr(plan, 'created_by') and self.id == plan.created_by:
            print(f"✅ Créateur du plan autorisé")
            return True
        
        # 7. RESPONSABLE DU PLAN : peut modifier
        if hasattr(plan, 'responsable_id') and self.id == plan.responsable_id:
            print(f"✅ Responsable du plan autorisé")
            return True
        
        # 8. RESPONSABLE DU RISQUE : peut modifier
        if hasattr(plan, 'risque') and plan.risque:
            if hasattr(plan.risque, 'created_by') and self.id == plan.risque.created_by:
                print(f"✅ Créateur du risque autorisé")
                return True
        
        # 9. RESPONSABLE DE L'AUDIT : peut modifier
        if hasattr(plan, 'audit') and plan.audit:
            if hasattr(plan.audit, 'responsable_id') and self.id == plan.audit.responsable_id:
                print(f"✅ Responsable de l'audit autorisé")
                return True
            if hasattr(plan.audit, 'created_by') and self.id == plan.audit.created_by:
                print(f"✅ Créateur de l'audit autorisé")
                return True
        
        # 10. Vérifier la permission can_manage_action_plans
        has_permission = self.has_permission('can_manage_action_plans')
        print(f"📋 Permission can_manage_action_plans: {has_permission}")
        
        return has_permission
    
    def can_add_constatation(self, audit):
        """Vérifie si l'utilisateur peut ajouter une constatation"""
        return (self.role in ['admin', 'referent', 'auditeur'] or 
                self.id == audit.responsable_id or 
                str(self.id) in (audit.equipe_audit_ids or '').split(','))
    
    def can_edit_plan(self, plan):
        """Vérifie si l'utilisateur peut modifier un plan d'action"""
        return (self.role in ['admin', 'referent'] or 
                self.id == plan.responsable_id or 
                self.id == plan.audit.responsable_id)
    
    def get_assigned_departments(self):
        """Retourne les départements assignés à l'utilisateur"""
        from models import Direction, Service
        
        departments = []
        
        # Directions managées
        for direction in self.directions_managees:
            departments.append({
                'id': direction.id,
                'name': direction.nom,
                'type': 'direction'
            })
        
        # Services managés
        for service in self.services_managees:
            departments.append({
                'id': service.id,
                'name': service.nom,
                'type': 'service'
            })
        
        return departments

    def can_add_constatation_audit(self, audit):
        """Vérifie si l'utilisateur peut ajouter une constatation"""
        if self.role == 'super_admin':
            return True
        
        if self.has_permission('can_manage_audit'):
            return True
        
        # Audit en cours et utilisateur fait partie de l'équipe
        if audit.statut in ['en_cours', 'en_redaction']:
            if self.id == audit.created_by:
                return True
            if audit.responsable_id == self.id:
                return True
            if audit.equipe_audit_ids:
                try:
                    equipe_ids = [int(id.strip()) for id in audit.equipe_audit_ids.split(',') if id.strip()]
                    if self.id in equipe_ids:
                        return True
                except (ValueError, AttributeError):
                    pass
        
        return False
    
    def can_add_recommandation(self, audit):
        """Vérifie si l'utilisateur peut ajouter une recommandation"""
        if self.role == 'super_admin':
            return True
        
        if self.has_permission('can_manage_audit'):
            return True
        
        # Audit en cours ou en rédaction
        if audit.statut in ['en_cours', 'en_redaction', 'en_validation']:
            if self.id == audit.created_by:
                return True
            if audit.responsable_id == self.id:
                return True
            if audit.equipe_audit_ids:
                try:
                    equipe_ids = [int(id.strip()) for id in audit.equipe_audit_ids.split(',') if id.strip()]
                    if self.id in equipe_ids:
                        return True
                except (ValueError, AttributeError):
                    pass
        
        return False
    
    def can_edit_audit_detailed(self, audit):
        """Vérifie si l'utilisateur peut modifier l'audit"""
        if self.role == 'super_admin':
            return True
        
        if self.has_permission('can_manage_audit'):
            return True
        
        # Créateur, responsable ou membre de l'équipe
        if self.id == audit.created_by:
            return True
        if self.id == audit.responsable_id:
            return True
        
        # Vérifier si dans l'équipe d'audit
        if audit.equipe_audit_ids:
            try:
                equipe_ids = [int(id.strip()) for id in audit.equipe_audit_ids.split(',') if id.strip()]
                if self.id in equipe_ids:
                    return True
            except (ValueError, AttributeError):
                pass
        
        return False
    def can_modify_user(self, target_user):
        """
        Vérifie si cet utilisateur peut modifier un autre utilisateur
        
        Args:
            target_user: L'utilisateur cible à modifier
        
        Returns:
            bool: True si modification autorisée, False sinon
        """
        
        # 1. On ne peut pas modifier soi-même (sauf profil personnel via autre route)
        # Note: Pour modifier son propre profil, on utilise une route spécifique
        if self.id == target_user.id:
            return False  # Ou True selon votre logique, mais généralement False pour admin
        
        # 2. SUPER ADMIN : peut tout modifier
        if self.role == 'super_admin':
            return True
        
        # 3. Vérifier qu'ils sont dans le même client
        if self.client_id != target_user.client_id:
            return False
        
        # 4. CLIENT ADMIN : peut modifier tout le monde SAUF autres client_admin
        if self.is_client_admin:
            return not target_user.is_client_admin
        
        # 5. GESTIONNAIRE : peut modifier seulement les non-admin et non-gestionnaires
        if self.can_manage_users and self.has_permission('can_edit_users'):
            return not (target_user.is_client_admin or 
                       (target_user.can_manage_users and target_user.id != self.id))
        
        # 6. Par défaut : non
        return False


    def can_archive_audit(self, audit):
        """Vérifie si l'utilisateur peut archiver un audit - VERSION CORRIGÉE"""
        
        # 1. Super admin peut tout faire
        if self.role == 'super_admin':
            return True
        
        # 2. Vérifier si l'audit a un client_id
        audit_client_id = getattr(audit, 'client_id', None)
        user_client_id = getattr(self, 'client_id', None)
        
        # 3. Si l'audit n'a pas de client_id, vérifier par le créateur
        if audit_client_id is None:
            # Vérifier si l'utilisateur est le créateur
            if hasattr(audit, 'created_by') and self.id == audit.created_by:
                return True
            # Vérifier si l'utilisateur est le responsable
            if hasattr(audit, 'responsable_id') and self.id == audit.responsable_id:
                return True
            # Sinon, refuser par sécurité
            return False
        
        # 4. Vérifier que les client_id correspondent
        if audit_client_id != user_client_id:
            return False
        
        # 5. Admin client peut archiver
        if self.is_client_admin:
            return True
        
        # 6. Créateur ou responsable peut archiver
        if self.id == getattr(audit, 'created_by', None) or \
           self.id == getattr(audit, 'responsable_id', None):
            return True
        
        # 7. Vérifier permission can_manage_audit
        return self.has_permission('can_manage_audit')

    def can_restore_audit(self, audit):
        """Vérifie si l'utilisateur peut restaurer un audit"""
        if self.role == 'super_admin':
            return True
        
        # Admin client peut restaurer tous les audits archivés de son client
        if self.is_client_admin:
            return audit.client_id == self.client_id
        
        # Créateur ou responsable de l'audit
        if self.id == audit.created_by or self.id == audit.responsable_id:
            return True
        
        # Vérifier la permission can_manage_audit
        return self.has_permission('can_manage_audit')

    def can_delete_audit(self, audit):
        """Vérifie si l'utilisateur peut supprimer définitivement un audit"""
        # Seuls super_admin et admin client peuvent supprimer définitivement
        if self.role == 'super_admin':
            return True
        
        # Admin client peut supprimer les audits archivés de son client
        if self.is_client_admin:
            return audit.client_id == self.client_id and audit.is_archived
        
        return False
    
    def can_generate_report(self, audit):
        """Vérifie si l'utilisateur peut générer un rapport"""
        if self.role == 'super_admin':
            return True
        
        if self.has_permission('can_export_data') or self.has_permission('can_view_reports'):
            return True
        
        # Créateur, responsable ou membre de l'équipe
        if self.id == audit.created_by:
            return True
        if self.id == audit.responsable_id:
            return True
        
        # Pour les rapports, autoriser aussi les observateurs
        if audit.observateurs_ids:
            try:
                observateur_ids = [int(id.strip()) for id in audit.observateurs_ids.split(',') if id.strip()]
                if self.id in observateur_ids:
                    return True
            except (ValueError, AttributeError):
                pass
        
        return False
    
    def has_role(self, role_name):
        """Vérifie si l'utilisateur a un rôle spécifique"""
        return self.role == role_name
    
    def __repr__(self):
        return f'<User {self.username} ({self.role})>'
    
# -------------------- DIRECTION --------------------
class Direction(db.Model):
    __tablename__ = 'direction'
    
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    responsable_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)  # AJOUTÉ pour soft delete
    is_archived = db.Column(db.Boolean, default=False)  # AJOUTÉ pour archiver
    archived_at = db.Column(db.DateTime)  # AJOUTÉ
    archived_by = db.Column(db.Integer, db.ForeignKey('user.id'))  # AJOUTÉ
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)

    # CORRECTION : Définir les relations avec foreign_keys spécifiques
    responsable = db.relationship('User', 
                                 back_populates='directions_managees', 
                                 foreign_keys=[responsable_id])  # AJOUTÉ
    
    archived_by_user = db.relationship('User', 
                                      back_populates='directions_archivees', 
                                      foreign_keys=[archived_by])  # AJOUTÉ
    
    services = db.relationship('Service', back_populates='direction', lazy=True)
    cartographies = db.relationship('Cartographie', back_populates='direction', lazy=True)
    processus = db.relationship('Processus', back_populates='direction', lazy=True)


# -------------------- SERVICE --------------------
class Service(db.Model):
    __tablename__ = 'service'
    
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    direction_id = db.Column(db.Integer, db.ForeignKey('direction.id'))
    responsable_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)  # AJOUTÉ pour soft delete
    is_archived = db.Column(db.Boolean, default=False)  # AJOUTÉ pour archiver
    archived_at = db.Column(db.DateTime)  # AJOUTÉ
    archived_by = db.Column(db.Integer, db.ForeignKey('user.id'))  # AJOUTÉ
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)

    # CORRECTION : Définir les relations avec foreign_keys spécifiques
    direction = db.relationship('Direction', back_populates='services')
    
    responsable = db.relationship('User', 
                                 back_populates='services_managees', 
                                 foreign_keys=[responsable_id])  # AJOUTÉ
    
    archived_by_user = db.relationship('User', 
                                      back_populates='services_archivees', 
                                      foreign_keys=[archived_by])  # AJOUTÉ
    
    processus = db.relationship('Processus', back_populates='service', lazy=True)
    cartographies = db.relationship('Cartographie', back_populates='service', lazy=True)

# -------------------- CARTOGRAPHIE --------------------
# Dans models.py, dans la classe Cartographie, ajoutez :

class Cartographie(db.Model):
    __tablename__ = 'cartographie'
    
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    direction_id = db.Column(db.Integer, db.ForeignKey('direction.id'))
    service_id = db.Column(db.Integer, db.ForeignKey('service.id'))
    type_cartographie = db.Column(db.String(50), default='direction')
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # NOUVEAUX CHAMPS POUR L'ARCHIVAGE
    is_archived = db.Column(db.Boolean, default=False)
    archived_at = db.Column(db.DateTime)
    archived_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    archive_reason = db.Column(db.Text)
    
    # Relations
    direction = db.relationship('Direction', back_populates='cartographies')
    service = db.relationship('Service', back_populates='cartographies')
    createur = db.relationship('User', foreign_keys=[created_by])
    archive_user = db.relationship('User', foreign_keys=[archived_by])
    risques = db.relationship('Risque', back_populates='cartographie')
    campagnes = db.relationship('CampagneEvaluation', back_populates='cartographie', cascade='all, delete-orphan')
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)

# -------------------- RISQUE --------------------
class Risque(db.Model):
    __tablename__ = 'risques'
    id = db.Column(db.Integer, primary_key=True)
    cartographie_id = db.Column(db.Integer, db.ForeignKey('cartographie.id'))
    reference = db.Column(db.String(50), unique=True, nullable=False)
    intitule = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text)
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

    cartographie = db.relationship('Cartographie', back_populates='risques')
    createur = db.relationship('User', foreign_keys=[created_by], back_populates='risques_crees')
    archive_user = db.relationship('User', foreign_keys=[archived_by], back_populates='risques_archives')
    evaluations = db.relationship('EvaluationRisque', back_populates='risque', lazy=True)
    
    # CORRECTION: Relation KRI avec primaryjoin explicite
    kri = db.relationship('KRI', back_populates='risque', uselist=False, lazy=True,
                         primaryjoin='Risque.id == KRI.risque_id')
    
    dispositifs_maitrise = db.relationship('DispositifMaitrise', 
                                          back_populates='risque',
                                          cascade='all, delete-orphan',
                                          lazy=True)

# -------------------- EVALUATION RISQUE (CORRIGÉ) --------------------
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
    reference = db.Column(db.String(50), unique=True, nullable=False)
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
    processus_id = db.Column(db.Integer, db.ForeignKey('processus.id'))
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
    
    # Membres externes
    membres_externes = db.Column(db.JSON, nullable=True, default=list)
    
    # CORRECTION : UNE SEULE RELATION POUR LE CREATEUR
    createur = db.relationship('User', foreign_keys=[created_by])
    
    # Responsable
    responsable = db.relationship('User', foreign_keys=[responsable_id], 
                                  backref='audits_dont_je_suis_responsable')
    
    # Archiveur
    archiveur = db.relationship('User', foreign_keys=[archived_by], 
                               backref='audits_que_jai_archives')
    
    # Processus
    processus = db.relationship('Processus', backref='audits')
    
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
    
    
    # Méthodes pour gérer l'équipe
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
    
    # Calcul des statistiques
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

    @property
    def processus_audite_display(self):
        """Retourne le nom du processus audité pour l'affichage"""
        if self.processus:
            return self.processus.nom
        elif self.processus_concerne:  # Champ manuel
            return self.processus_concerne
        return None
    
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
    reference = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text, nullable=False)
    type_constatation = db.Column(db.String(50), nullable=False)
    gravite = db.Column(db.String(50))
    # Nouveaux champs
    criticite = db.Column(db.String(50))  # mineure, majeure, critique
    processus_concerne = db.Column(db.String(200))
    cause_racine = db.Column(db.Text)  # Méthode 5 Why
    documents_justificatifs = db.Column(db.Text)
    # Workflow intelligent
    statut = db.Column(db.String(50), default='a_analyser')  # a_analyser, a_valider, en_action, clos
    # Fichiers joints
    fichiers_ids = db.Column(db.String(500))  # Références aux fichiers
    preuves = db.Column(db.Text)
    audit_id = db.Column(db.Integer, db.ForeignKey('audits.id'), nullable=False)  # 'audits.id'
    risque_id = db.Column(db.Integer, db.ForeignKey('risques.id'))
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_archived = db.Column(db.Boolean, default=False)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)
    
    # Relations corrigées
    audit = db.relationship('Audit', back_populates='constatations')
    risque = db.relationship('Risque', backref='constatations')
    createur = db.relationship('User', foreign_keys=[created_by])
    recommandations = db.relationship('Recommandation', back_populates='constatation', lazy=True)
    processus_concerne = db.Column(db.String(500))  # Augmenter la longueur
    conclusion = db.Column(db.Text)  # Pour le rapport définitif
    commentaires = db.Column(db.Text)  # Commentaires internes
    recommandations_immediates = db.Column(db.Text)  # Actions immédiates proposées
    
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
    
    def set_processus(self, processus_id=None, nom_manuel=None, from_audit=False):
        """Définit le processus concerné"""
        if from_audit and self.audit:
            # Utiliser le processus de l'audit
            self.processus_concerne = self.audit.processus_audite_display
        elif nom_manuel:
            self.processus_concerne = nom_manuel
        elif processus_id:
            # Récupérer le nom du processus
            processus = Processus.query.get(processus_id)
            if processus:
                self.processus_concerne = processus.nom
    
    @property
    def get_preuves_list(self):
        """Retourne la liste des preuves sous forme de liste Python"""
        if self.preuves:
            # Si les preuves sont stockées séparées par des virgules
            return [p.strip() for p in self.preuves.split(',') if p.strip()]
        return []
    
    def get_fichiers_list(self):
        """Retourne la liste des IDs de fichiers"""
        if self.fichiers_ids:
            try:
                return [int(id.strip()) for id in self.fichiers_ids.split(',') if id.strip()]
            except (ValueError, AttributeError):
                return []
        return []
    
    @property
    def nb_preuves(self):
        """Retourne le nombre de preuves"""
        return len(self.get_preuves_list)
    
    @property
    def nb_fichiers(self):
        """Retourne le nombre de fichiers joints"""
        return len(self.get_fichiers_list())
    
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
    
    def ajouter_preuve(self, nom_fichier):
        """Ajoute une preuve à la constatation"""
        if not self.preuves:
            self.preuves = nom_fichier
        else:
            preuves_list = self.get_preuves_list
            if nom_fichier not in preuves_list:
                preuves_list.append(nom_fichier)
                self.preuves = ','.join(preuves_list)
    
    def supprimer_preuve(self, nom_fichier):
        """Supprime une preuve de la constatation"""
        if self.preuves:
            preuves_list = self.get_preuves_list
            if nom_fichier in preuves_list:
                preuves_list.remove(nom_fichier)
                self.preuves = ','.join(preuves_list) if preuves_list else None
                return True
        return False
    
    def archiver(self, utilisateur_id=None):
        """Archive la constatation"""
        self.is_archived = True
        self.updated_at = datetime.utcnow()
    
    def restaurer(self):
        """Restaurer une constatation archivée"""
        self.is_archived = False
        self.updated_at = datetime.utcnow()
    
    def __repr__(self):
        return f'<Constatation {self.reference}: {self.description[:50]}...>'

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
    reference = db.Column(db.String(50), nullable=False)
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
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))  # CORRIGÉ
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),  # CORRIGÉ
                          onupdate=lambda: datetime.now(timezone.utc))  # CORRIGÉ
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)
    
    # Relations
    audit = db.relationship('Audit', back_populates='recommandations')
    constatation = db.relationship('Constatation', back_populates='recommandations')
    risque = db.relationship('Risque', backref='recommandations')
    responsable = db.relationship('User', foreign_keys=[responsable_id])
    createur = db.relationship('User', foreign_keys=[created_by])
    plan_action = db.relationship('PlanAction', back_populates='recommandation', uselist=False, lazy=True)
    historique = db.relationship('HistoriqueRecommandation', backref='recommandation', lazy=True, cascade='all, delete-orphan')
    client = db.relationship('Client')
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.calculer_score_priorite()
    
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
    def est_en_retard(self):
        if not self.date_echeance or self.statut == 'termine':
            return False
        return datetime.now(timezone.utc).date() > self.date_echeance  # CORRIGÉ
    
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
                'date': datetime.now(timezone.utc).isoformat()  # CORRIGÉ
            },
            utilisateur_id=utilisateur_id
        )
        db.session.add(historique)
        
        if nouveau_statut == 'termine':
            self.taux_avancement = 100
    
    def mettre_a_jour_avancement(self, nouveau_taux, utilisateur_id):
        ancien_taux = self.taux_avancement
        self.taux_avancement = min(100, max(0, nouveau_taux))
        
        historique = HistoriqueRecommandation(
            recommandation_id=self.id,
            action='mise_a_jour_avancement',
            details={
                'ancien_taux': ancien_taux,
                'nouveau_taux': self.taux_avancement,
                'date': datetime.now(timezone.utc).isoformat()  # CORRIGÉ
            },
            utilisateur_id=utilisateur_id
        )
        db.session.add(historique)
        
        if self.taux_avancement == 100 and self.statut != 'termine':
            self.statut = 'termine'
    
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

# -------------------- PLAN ACTION - CORRIGÉ ET COMPLET --------------------
class PlanAction(db.Model):
    __tablename__ = 'plans_action'
    
    id = db.Column(db.Integer, primary_key=True)
    reference = db.Column(db.String(50), nullable=False)
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
    
    # Colonnes d'archivage - LA NOUVELLE COLONNE EST AJOUTÉE
    is_archived = db.Column(db.Boolean, default=False)
    archived_at = db.Column(db.DateTime)
    archived_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    archive_reason = db.Column(db.Text)  # Cette colonne existe déjà dans votre base
    statut_archive = db.Column(db.String(20), default='actif')  # NOUVELLE COLONNE
    
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)
    
    # Relations multiples
    audit_id = db.Column(db.Integer, db.ForeignKey('audits.id'), nullable=True)
    recommandation_id = db.Column(db.Integer, db.ForeignKey('recommandations.id'), nullable=True)
    risque_id = db.Column(db.Integer, db.ForeignKey('risques.id'), nullable=True)
    dispositif_id = db.Column(db.Integer, db.ForeignKey('dispositifs_maitrise.id'), nullable=True)
    constatations_ids = db.Column(db.String(500))
    responsable_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    # Relations
    audit = db.relationship('Audit', back_populates='plans_action')
    recommandation = db.relationship('Recommandation', back_populates='plan_action')
    risque = db.relationship('Risque', backref='plans_action')
    dispositif = db.relationship('DispositifMaitrise', foreign_keys=[dispositif_id])
    responsable = db.relationship('User', foreign_keys=[responsable_id])
    createur = db.relationship('User', foreign_keys=[created_by])
    sous_actions = db.relationship('SousAction', backref='plan_action', lazy=True, cascade='all, delete-orphan')
    
    # REMARQUE : N'ÉCRIVEZ PAS @property pour is_archived car c'est une vraie colonne
    
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
    
    # Dans votre modèle PlanAction
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
            'client_id': self.client_id,
            'progression_reelle': self.progression_reelle,
            'est_en_retard': self.est_en_retard,
            'couleur_statut': self.couleur_statut,
            'is_archived': self.is_archived,
            'statut_archive': self.statut_archive,
            'archived_at': self.archived_at.isoformat() if self.archived_at else None,
            'archived_by': self.archived_by,
            'priorite': self.priorite,
            'archive_reason': self.archive_reason
        }
    
    def __repr__(self):
        return f'<PlanAction {self.reference}: {self.nom}>'

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
    
    def terminer(self):
        """Termine la sous-action"""
        self.statut = 'termine'
        self.pourcentage_realisation = 100
        self.date_fin_reelle = datetime.utcnow().date()
        self.updated_at = datetime.utcnow()

# -------------------- ETAPE PLAN ACTION - CORRIGÉ --------------------
class EtapePlanAction(db.Model):
    __tablename__ = 'etapes_plan_action'
    
    id = db.Column(db.Integer, primary_key=True)
    plan_action_id = db.Column(db.Integer, db.ForeignKey('plans_action.id'), nullable=False)  # 'plans_action.id'
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

# -------------------- ETAPE PLAN ACTION - CORRIGÉ --------------------
class EtapePlanAction(db.Model):
    __tablename__ = 'etapes_plan_action'
    
    id = db.Column(db.Integer, primary_key=True)
    plan_action_id = db.Column(db.Integer, db.ForeignKey('plans_action.id'), nullable=False)  # 'plans_action.id'
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
    db_password = db.Column(db.String(500))  # Crypté

    # Configuration serveur
    server_ip = db.Column(db.String(50))
    server_port = db.Column(db.Integer, default=22)
    server_ssh_user = db.Column(db.String(50))
    server_ssh_key = db.Column(db.Text)  # Clé SSH privée cryptée
    
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
    reference = db.Column(db.String(50), unique=True, nullable=False)
    nom = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text)
    type_dispositif = db.Column(db.String(100))
    nature = db.Column(db.String(100))
    frequence = db.Column(db.String(100))
    responsable_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    direction_id = db.Column(db.Integer, db.ForeignKey('direction.id'))
    service_id = db.Column(db.Integer, db.ForeignKey('service.id'))
    commentaire_evaluation = db.Column(db.Text)  # Commentaire de l'évaluation
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
    plan_action_id = db.Column(db.Integer, db.ForeignKey('plans_action.id'))
    
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
    
    # CORRECTION : Supprimez back_populates ou changez pour backref
    plan_action = db.relationship('PlanAction', foreign_keys=[plan_action_id])  # Simple relation
    
    createur = db.relationship('User', foreign_keys=[created_by])
    archive_user = db.relationship('User', foreign_keys=[archived_by])
    client = db.relationship('Client')
    
    # Documentation
    documents = db.relationship('DocumentDispositif', back_populates='dispositif', cascade='all, delete-orphan')
    verifications = db.relationship('VerificationDispositif', back_populates='dispositif', cascade='all, delete-orphan')
    
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
        """
        details = {}
        
        # Réduction max selon type
        reduction_max_par_type = {
            'Préventif': 75, 'Détectif': 60, 'Correctif': 45, 'Dirigeant': 30
        }
        
        type_dispositif = self.type_dispositif or 'Correctif'
        details['reduction_max_type'] = reduction_max_par_type.get(type_dispositif, 45)
        details['type'] = type_dispositif
        
        # Scores
        details['efficacite'] = self.efficacite_reelle or 0
        details['couverture'] = self.couverture or 0
        details['efficacite_norm'] = (self.efficacite_reelle or 0) / 5
        details['couverture_norm'] = (self.couverture or 0) / 5
        
        # Score de base pondéré (60% efficacité, 40% couverture)
        details['score_pondere'] = (details['efficacite_norm'] * 60) + (details['couverture_norm'] * 40)
        details['reduction_calcul'] = (details['score_pondere'] / 100) * details['reduction_max_type']
        
        # Facteurs plus réalistes
        facteurs_nature = {
            'Automatique': 1.0, 'Technique': 0.95, 'Procédurale': 0.85,
            'Organisationnelle': 0.80, 'Humaine': 0.75
        }
        facteurs_frequence = {
            'Permanente': 1.0, 'Continue': 0.95, 'Temps réel': 0.95,
            'Quotidienne': 0.90, 'Hebdomadaire': 0.85, 'Mensuelle': 0.75,
            'Trimestrielle': 0.65, 'Annuelle': 0.55
        }
        
        details['facteur_nature'] = facteurs_nature.get(self.nature or 'Procédurale', 0.85)
        details['nature'] = self.nature or 'Procédurale'
        details['facteur_frequence'] = facteurs_frequence.get(self.frequence or 'Mensuelle', 0.75)
        details['frequence'] = self.frequence or 'Mensuelle'
        
        # Réduction finale
        details['reduction_finale'] = details['reduction_calcul'] * details['facteur_nature'] * details['facteur_frequence']
        
        # Garantir un minimum pour dispositif parfait
        if details['efficacite'] == 5 and details['couverture'] == 5:
            details['reduction_finale'] = max(details['reduction_finale'], details['reduction_max_type'] * 0.8)
            details['garantie_minimum'] = True
        else:
            details['garantie_minimum'] = False
        
        # Limiter au maximum du type
        details['reduction_finale'] = min(details['reduction_finale'], details['reduction_max_type'])
        details['reduction_finale'] = round(details['reduction_finale'], 1)
        
        return details
    
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

