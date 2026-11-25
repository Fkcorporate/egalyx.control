
# --- Journal (remplace les anciens print()) : erreurs -> WARNING (journaux du serveur) ; le reste -> DEBUG,
#     visible seulement avec EGALYX_TRACES=1. Ajouté le 18/11/2026 (ménage).
import logging as _logging_journal
import os as _os_journal
_JOURNAL = _logging_journal.getLogger('egalyx.config')
_MOTS_ALERTE = ('\u274c', '\u26a0', 'ERREUR', 'Erreur', 'erreur', 'ERROR', 'Error', 'error', 'Exception', 'chec', 'Traceback', 'CRITIQUE')
if _os_journal.environ.get('EGALYX_TRACES') == '1' and not _JOURNAL.handlers:
    _JOURNAL.setLevel(_logging_journal.DEBUG)
    _h = _logging_journal.StreamHandler()
    _h.setFormatter(_logging_journal.Formatter('%(asctime)s %(name)s %(levelname)s %(message)s'))
    _JOURNAL.addHandler(_h)
    _JOURNAL.propagate = False


def _journal(*args, sep=' ', **_ignore):
    """Ancien print() : écrit dans le journal au lieu de la sortie standard."""
    try:
        texte = sep.join(str(a) for a in args)
    except Exception:  # noqa: BLE001
        return
    if any(m in texte for m in _MOTS_ALERTE) and not texte.lstrip().startswith(('\u2705', '\u2713')):
        _JOURNAL.warning(texte)
    elif _JOURNAL.isEnabledFor(_logging_journal.DEBUG):
        _JOURNAL.debug(texte)
# --- fin du journal
import os
from datetime import timedelta
from urllib.parse import urlparse
from dotenv import load_dotenv

# Charger les variables d'environnement depuis .env
load_dotenv()

# Déterminer si on est sur Render
IS_RENDER = 'RENDER' in os.environ
# Production : sur Render, ou chez un client (installation on-premise) avec EGALYX_PRODUCTION=1.
# Hors production, l'outil démarre en mode développement (débogage, cookies non sécurisés) : jamais chez un client.
EN_PRODUCTION = IS_RENDER or os.environ.get('EGALYX_PRODUCTION') == '1'
# Cookies réservés à HTTPS en production (EGALYX_HTTPS=0 seulement pour un essai sans certificat)
HTTPS = EN_PRODUCTION and os.environ.get('EGALYX_HTTPS', '1') != '0'

class Config:
    # ============================================================================
    # CONFIGURATIONS DE BASE
    # ============================================================================
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'votre_cle_secrete_super_securisee_changer_en_production'
    
    # Configuration base de données
    if EN_PRODUCTION and os.environ.get('DATABASE_URL'):
        # Render (et l'on-premise) utilisent PostgreSQL - conversion nécessaire
        DATABASE_URL = os.environ['DATABASE_URL']
        if DATABASE_URL.startswith('postgres://'):
            DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
        SQLALCHEMY_DATABASE_URI = DATABASE_URL
    else:
        # Développement local
        SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///controle_interne.db'
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SQLALCHEMY_SESSION_OPTIONS = {
        "expire_on_commit": False
    }

    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_recycle': 300,
        'pool_pre_ping': True,
        'pool_size': 20,
        'max_overflow': 30
    }

    
    PERMANENT_SESSION_LIFETIME = timedelta(days=1)
    
    # ============================================================================
    # CONFIGURATIONS DES UPLOADS
    # ============================================================================
    if IS_RENDER:
        # Sur Render, utiliser le dossier monté
        BASE_UPLOAD_FOLDER = '/var/data' if os.path.exists('/var/data') else 'uploads'
    else:
        BASE_UPLOAD_FOLDER = 'uploads'
    
    UPLOAD_FOLDER = BASE_UPLOAD_FOLDER
    UPLOAD_FOLDER_AUDIT = os.path.join(BASE_UPLOAD_FOLDER, 'audits')
    UPLOAD_FOLDER_CONSTATATIONS = os.path.join(BASE_UPLOAD_FOLDER, 'constatations')
    UPLOAD_FOLDER_RECOMMANDATIONS = os.path.join(BASE_UPLOAD_FOLDER, 'recommandations')
    UPLOAD_FOLDER_PLANS = os.path.join(BASE_UPLOAD_FOLDER, 'plans_action')
    UPLOAD_FOLDER_VEILLE = os.path.join('static', 'uploads', 'veille')
    UPLOAD_FOLDER_RISQUES = os.path.join(BASE_UPLOAD_FOLDER, 'risques')
    
    # Extensions autorisées
    ALLOWED_EXTENSIONS = {
        'pdf', 'png', 'jpg', 'jpeg', 'gif', 'bmp', 'tiff', 'webp',
        'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'txt',
        'csv', 'json', 'xml', 'zip', 'rar', '7z'
    }
    
    # Taille maximale des fichiers (16MB)
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    
    # ============================================================================
    # CONFIGURATION EMAIL (POUR NOTIFICATIONS)
    # ============================================================================
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'True').lower() in ['true', '1', 't']
    MAIL_USE_SSL = os.environ.get('MAIL_USE_SSL', 'False').lower() in ['true', '1', 't']
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', 'contact.fkcorporate@gmail.com')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')
    # Expéditeur des e-mails : réglable (chez un client, ses propres nom et adresse) ; sinon la valeur historique
    MAIL_DEFAULT_SENDER = ((os.environ.get('MAIL_NOM_EXPEDITEUR') or 'Egalyx Control', os.environ['MAIL_DEFAULT_SENDER'])
                           if os.environ.get('MAIL_DEFAULT_SENDER') else ('FK Corporate Intelligence', 'contact.fkcorporate@gmail.com'))
    
    # ============================================================================
    # CONFIGURATION SECURITÉ
    # ============================================================================
    SESSION_COOKIE_SECURE = HTTPS  # HTTPS uniquement en production (Render ou on-premise)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    REMEMBER_COOKIE_SECURE = HTTPS
    REMEMBER_COOKIE_HTTPONLY = True
    
    # ============================================================================
    # CONFIGURATIONS AUDIT - STATUTS INTELLIGENTS
    # ============================================================================
    AUDIT_STATUTS = [
        ('planifie', 'Planifié'),
        ('en_preparation', 'En préparation'),
        ('en_collecte', 'En collecte'),
        ('en_analyse', 'En analyse'),
        ('en_redaction', 'En rédaction du rapport'),
        ('en_validation', 'En validation'),
        ('clos', 'Clos'),
        ('archive', 'Archivé')
    ]
    
    # ============================================================================
    # CONFIGURATIONS CONSTATATION - WORKFLOW ET CLASSIFICATION
    # ============================================================================
    CONSTATATION_TYPES = [
        ('non_conformite', 'Non-conformité'),
        ('observation', 'Observation'),
        ('opportunite_amelioration', 'Opportunité d\'amélioration'),
        ('conforme', 'Conforme'),
        ('point_fort', 'Point fort')
    ]
    
    CONSTATATION_GRAVITE = [
        ('mineure', 'Mineure'),
        ('moyenne', 'Moyenne'),
        ('majeure', 'Majeure'),
        ('critique', 'Critique')
    ]
    
    CONSTATATION_CRITICITE = [
        ('mineure', 'Mineure'),
        ('majeure', 'Majeure'),
        ('critique', 'Critique')
    ]
    
    # ============================================================================
    # CONFIGURATIONS RECOMMANDATION - TYPOLOGIE ET PRIORISATION
    # ============================================================================
    RECOMMANDATION_TYPES = [
        ('corrective', 'Corrective'),
        ('preventive', 'Préventive'),
        ('amelioration', 'Amélioration'),
        ('optimisation', 'Optimisation')
    ]
    
    RECOMMANDATION_CATEGORIES = [
        ('conformite_reglementaire', 'Conformité réglementaire'),
        ('amelioration_continue', 'Amélioration continue'),
        ('reduction_risque', 'Réduction de risque'),
        ('optimisation_processus', 'Optimisation de processus'),
        ('securite_controle_interne', 'Sécurité / Contrôle interne')
    ]
    
    # ============================================================================
    # CONFIGURATIONS PLAN D'ACTION
    # ============================================================================
    PLAN_ACTION_STATUTS = [
        ('en_attente', 'En attente'),
        ('en_cours', 'En cours'),
        ('termine', 'Terminé'),
        ('retarde', 'Retardé'),
        ('suspendu', 'Suspendu')
    ]
    
    # ============================================================================
    # CONFIGURATIONS ALERTES AUTOMATIQUES
    # ============================================================================
    ALERTE_7J_AVANT_ECHEANCE = True
    ALERTE_ECHEANCE_ATTEINTE = True
    ALERTE_RETARD = True
    
    # ============================================================================
    # CONFIGURATIONS EXPORTS
    # ============================================================================
    EXPORT_LOGO_PATH = 'static/images/logo_entreprise.png'
    EXPORT_SIGNATURE_ENABLED = True
    
    # ============================================================================
    # CONFIGURATION POUR RENDER (PERFORMANCE)
    # ============================================================================
    if EN_PRODUCTION:
        # Désactiver le debug (Render ou on-premise)
        DEBUG = False
        TEMPLATES_AUTO_RELOAD = False
        
        # Optimiser les performances
        JSONIFY_PRETTYPRINT_REGULAR = False
        SEND_FILE_MAX_AGE_DEFAULT = 31536000  # 1 an pour les fichiers statiques
        
        # Configuration Gunicorn
        PREFERRED_URL_SCHEME = 'https'
    else:
        DEBUG = True
        TEMPLATES_AUTO_RELOAD = True
        PREFERRED_URL_SCHEME = 'http'
    
    # ============================================================================
    # CONFIGURATION CACHE
    # ============================================================================
    CACHE_TYPE = 'simple'  # Pour production, utiliser 'redis' ou 'memcached'
    CACHE_DEFAULT_TIMEOUT = 300  # 5 minutes
    
    # ============================================================================
    # CONFIGURATION POUR LES TÂCHES PLANIFIÉES
    # ============================================================================
    SCHEDULER_API_ENABLED = False  # Désactiver l'API du scheduler
    
    # ============================================================================
    # MÉTHODES UTILITAIRES
    # ============================================================================
    
    @staticmethod
    def ensure_upload_folders():
        """Crée tous les dossiers d'upload s'ils n'existent pas"""
        folders = [
            Config.UPLOAD_FOLDER,
            Config.UPLOAD_FOLDER_AUDIT,
            Config.UPLOAD_FOLDER_CONSTATATIONS,
            Config.UPLOAD_FOLDER_RECOMMANDATIONS,
            Config.UPLOAD_FOLDER_PLANS,
            Config.UPLOAD_FOLDER_VEILLE,
            Config.UPLOAD_FOLDER_RISQUES
        ]
        
        for folder in folders:
            if not os.path.exists(folder):
                try:
                    os.makedirs(folder, exist_ok=True)
                    _journal(f"✅ Dossier créé: {folder}")
                except Exception as e:
                    _journal(f"⚠️ Erreur création dossier {folder}: {e}")
    
    @staticmethod
    def get_database_info():
        """Retourne des informations sur la base de données"""
        if 'sqlite' in Config.SQLALCHEMY_DATABASE_URI:
            return "SQLite (développement)"
        elif 'postgresql' in Config.SQLALCHEMY_DATABASE_URI:
            return "PostgreSQL (production)"
        else:
            return "Base de données inconnue"
    
    @staticmethod
    def print_config_summary():
        """Affiche un résumé de la configuration (sans les mots de passe)"""
        _journal("\n" + "="*60)
        _journal("📋 RÉSUMÉ DE LA CONFIGURATION")
        _journal("="*60)
        _journal(f"ENVIRONNEMENT: {('🎯 PRODUCTION (Render)' if IS_RENDER else '🎯 PRODUCTION (on-premise)') if EN_PRODUCTION else '🛠️  DÉVELOPPEMENT'}")
        _journal(f"SECRET_KEY: {'✅ Définie' if Config.SECRET_KEY and len(Config.SECRET_KEY) > 20 else '⚠️  Faible ou non définie'}")
        _journal(f"DATABASE: {Config.get_database_info()}")
        _journal(f"DATABASE_URL: {Config.SQLALCHEMY_DATABASE_URI[:50]}...")
        _journal(f"MAIL_SERVER: {Config.MAIL_SERVER}")
        _journal(f"MAIL_PORT: {Config.MAIL_PORT}")
        _journal(f"MAIL_USERNAME: {Config.MAIL_USERNAME}")
        _journal(f"MAIL_PASSWORD: {'✅ Définie' if Config.MAIL_PASSWORD else '❌ Non définie'}")
        _journal(f"MAIL_DEFAULT_SENDER: {Config.MAIL_DEFAULT_SENDER}")
        _journal(f"UPLOAD_BASE: {Config.BASE_UPLOAD_FOLDER}")
        _journal(f"DEBUG_MODE: {'✅ Activé' if Config.DEBUG else '❌ Désactivé'}")
        _journal(f"HTTPS_ENFORCED: {'✅ Oui' if Config.SESSION_COOKIE_SECURE else '❌ Non'}")
        _journal("="*60)
    
    @staticmethod
    def init_app(app):
        """Initialise l'application avec cette configuration"""
        # Créer les dossiers d'upload
        Config.ensure_upload_folders()
        
        # Afficher le résumé
        Config.print_config_summary()
        
        # Configuration supplémentaire si nécessaire
        if EN_PRODUCTION:
            _journal("🚀 Configuration de production détectée" + (" (Render)" if IS_RENDER else " (on-premise)"))
            # Forcer HTTPS sur Render
            app.config['PREFERRED_URL_SCHEME'] = 'https'
            
            # Configurer le proxy fix pour Flask
            from werkzeug.middleware.proxy_fix import ProxyFix
            app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)


class ProductionConfig(Config):
    """Configuration pour la production sur Render"""
    
    # Désactiver le debug
    DEBUG = False
    TESTING = False
    
    # Sécurité renforcée
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # Performance database
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 20,           # Nombre de connexions dans le pool
        'max_overflow': 30,        # Connexions supplémentaires temporaires
        'pool_recycle': 3600,      # Recycler les connexions toutes les heures
        'pool_pre_ping': True,     # Vérifier la connexion avant utilisation
        'pool_timeout': 30,        # Timeout pour obtenir une connexion
        'connect_args': {
            'connect_timeout': 10,
            'keepalives': 1,
            'keepalives_idle': 30,
            'keepalives_interval': 10,
            'keepalives_count': 5
        }
    }
    
    # Cache Redis (nécessite Redis sur Render)
    REDIS_URL = os.environ.get('REDIS_URL')
    if REDIS_URL:
        CACHE_TYPE = 'redis'
        CACHE_REDIS_URL = REDIS_URL
        CACHE_DEFAULT_TIMEOUT = 300
    else:
        CACHE_TYPE = 'simple'
    
    # Configuration uploads sur le disque monté
    if os.path.exists('/var/data'):
        BASE_UPLOAD_FOLDER = '/var/data'
    else:
        BASE_UPLOAD_FOLDER = 'uploads'
    
    # Configuration email
    MAIL_SERVER = 'smtp.gmail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    
    # Logging
    LOG_LEVEL = 'WARNING'
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # Rate limiting (à implémenter avec Flask-Limiter)
    RATELIMIT_ENABLED = True
    RATELIMIT_DEFAULT = "200 per hour"
    
    @staticmethod
    def init_app(app):
        """Initialisation spécifique à la production"""
        Config.init_app(app)
        
        # Configurer le logging
        import logging
        from logging.handlers import RotatingFileHandler
        
        # Créer le dossier de logs
        if not os.path.exists('logs'):
            os.makedirs('logs')
        
        file_handler = RotatingFileHandler(
            'logs/app.log',
            maxBytes=10485760,  # 10MB
            backupCount=10
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.WARNING)
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.WARNING)
        
        # Forcer HTTPS
        app.config['PREFERRED_URL_SCHEME'] = 'https'
