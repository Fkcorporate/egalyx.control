# forms/notification_forms.py
from flask_wtf import FlaskForm
from wtforms import BooleanField, SelectField, DateTimeLocalField, TextAreaField, SelectMultipleField, IntegerField, TimeField
from wtforms.validators import Optional, NumberRange, ValidationError
from datetime import datetime

class NotificationPreferencesForm(FlaskForm):
    """
    Formulaire complet pour les préférences de notifications
    """
    
    # ==================== SECTION WEB ====================
    web_nouvelle_constatation = BooleanField('📝 Nouvelles constatations', 
        description="Recevoir des notifications lors de la création d'une nouvelle constatation")
    
    web_nouvelle_recommandation = BooleanField('💡 Nouvelles recommandations', 
        description="Recevoir des notifications lors de la création d'une nouvelle recommandation")
    
    web_nouveau_plan = BooleanField('📋 Nouveaux plans d\'action', 
        description="Recevoir des notifications lors de la création d'un nouveau plan d'action")
    
    web_echeance_7j = BooleanField('📅 Échéances (7 jours)', 
        description="Recevoir des notifications 7 jours avant une échéance")
    
    web_echeance_3j = BooleanField('📅 Échéances (3 jours)', 
        description="Recevoir des notifications 3 jours avant une échéance")
    
    web_echeance_1j = BooleanField('📅 Échéances (1 jour)', 
        description="Recevoir des notifications 1 jour avant une échéance")
    
    web_retard = BooleanField('⚠️ Retards', 
        description="Recevoir des notifications pour les retards")
    
    web_validation_requise = BooleanField('✅ Validations requises', 
        description="Recevoir des notifications lorsqu'une validation est requise")
    
    web_kri_alerte = BooleanField('📊 Alertes KRI', 
        description="Recevoir des notifications pour les alertes KRI")
    
    web_veille_nouvelle = BooleanField('⚖️ Nouvelles veilles réglementaires', 
        description="Recevoir des notifications pour les nouvelles veilles")
    
    web_audit_demarre = BooleanField('🚀 Audits démarrés', 
        description="Recevoir des notifications lorsqu'un audit démarre")
    
    web_audit_termine = BooleanField('🏁 Audits terminés', 
        description="Recevoir des notifications lorsqu'un audit est terminé")
    
    web_risque_evalue = BooleanField('⚠️ Risques évalués', 
        description="Recevoir des notifications pour les évaluations de risque")
    
    web_systeme = BooleanField('⚙️ Notifications système', 
        description="Recevoir des notifications système importantes")
    
    # ==================== SECTION EMAIL ====================
    email_nouvelle_constatation = BooleanField('📝 Nouvelles constatations', 
        description="Recevoir des emails pour les nouvelles constatations")
    
    email_nouvelle_recommandation = BooleanField('💡 Nouvelles recommandations', 
        description="Recevoir des emails pour les nouvelles recommandations")
    
    email_nouveau_plan = BooleanField('📋 Nouveaux plans d\'action', 
        description="Recevoir des emails pour les nouveaux plans d'action")
    
    email_echeance_7j = BooleanField('📅 Échéances (7 jours)', 
        description="Recevoir des emails 7 jours avant une échéance")
    
    email_echeance_3j = BooleanField('📅 Échéances (3 jours)', 
        description="Recevoir des emails 3 jours avant une échéance")
    
    email_echeance_1j = BooleanField('📅 Échéances (1 jour)', 
        description="Recevoir des emails 1 jour avant une échéance")
    
    email_retard = BooleanField('⚠️ Retards', 
        description="Recevoir des emails pour les retards")
    
    email_validation_requise = BooleanField('✅ Validations requises', 
        description="Recevoir des emails pour les validations requises")
    
    email_kri_alerte = BooleanField('📊 Alertes KRI', 
        description="Recevoir des emails pour les alertes KRI")
    
    email_veille_nouvelle = BooleanField('⚖️ Nouvelles veilles', 
        description="Recevoir des emails pour les nouvelles veilles")
    
    # Fréquence des emails
    frequence_email = SelectField('📧 Fréquence des emails', 
        choices=[
            ('immediat', 'Immédiat (à chaque notification)'),
            ('quotidien', 'Quotidien (résumé journalier)'),
            ('hebdomadaire', 'Hebdomadaire (résumé hebdomadaire)'),
            ('jamais', 'Jamais (aucun email)')
        ],
        default='quotidien',
        description="Fréquence à laquelle vous souhaitez recevoir les emails de notification")
    
    # ==================== SECTION PUSH ====================
    push_urgence = BooleanField('🚨 Notifications urgentes', 
        description="Recevoir des notifications push pour les alertes urgentes")
    
    push_important = BooleanField('⚠️ Notifications importantes', 
        description="Recevoir des notifications push pour les alertes importantes")
    
    push_normal = BooleanField('📱 Notifications normales', 
        description="Recevoir des notifications push pour les alertes normales")
    
    # ==================== SECTION PAUSE ====================
    pause_notifications = BooleanField('⏸️ Mettre en pause toutes les notifications', 
        description="Suspendre temporairement toutes les notifications")
    
    pause_until = DateTimeLocalField('🔄 Reprendre après le', 
        format='%Y-%m-%dT%H:%M', 
        validators=[Optional()],
        description="Date et heure à laquelle reprendre les notifications")
    
    # ==================== SECTION ZONES DE SILENCE ====================
    silence_zones = TextAreaField('🌙 Zones de silence', 
        render_kw={
            'placeholder': 'Ex: 22:00-07:00 (nuit), 12:00-14:00 (pause déjeuner), weekend',
            'rows': 3
        },
        description="Périodes où vous ne souhaitez pas recevoir de notifications")
    
    # ==================== SECTION LIMITES ====================
    max_daily_notifications = IntegerField('📈 Maximum de notifications par jour', 
        default=50,
        validators=[Optional(), NumberRange(min=1, max=500)],
        description="Limite du nombre de notifications reçues par jour")
    
    notification_retention_days = IntegerField('🗑️ Conservation des notifications (jours)', 
        default=30,
        validators=[Optional(), NumberRange(min=1, max=365)],
        description="Durée de conservation des notifications dans l'historique")
    
    # ==================== SECTION PERSONNALISATION ====================
    notification_sound = BooleanField('🔔 Son de notification', 
        default=True,
        description="Activer le son pour les nouvelles notifications")
    
    notification_vibration = BooleanField('📳 Vibration', 
        default=False,
        description="Activer la vibration pour les notifications importantes")
    
    notification_popup = BooleanField('💬 Fenêtres pop-up', 
        default=True,
        description="Afficher des fenêtres pop-up pour les notifications importantes")
    
    def validate_pause_until(self, field):
        """Valider que la date de reprise est dans le futur"""
        if field.data and field.data < datetime.now():
            raise ValidationError('La date de reprise doit être dans le futur')
