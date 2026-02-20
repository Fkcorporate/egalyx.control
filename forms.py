from flask_wtf import FlaskForm
from wtforms import (
    StringField, TextAreaField, PasswordField, SelectField, IntegerField,
    DateField, FloatField, BooleanField, SubmitField, RadioField, SelectMultipleField,
    FileField, FieldList, FormField, HiddenField, DecimalField, DateTimeField, URLField
)
from wtforms.validators import DataRequired, Email, Length, EqualTo, NumberRange, Optional, ValidationError, URL, Regexp
from flask_wtf.file import FileAllowed, FileRequired, MultipleFileField 
from wtforms.widgets import TextArea, CheckboxInput, ListWidget
import json
from datetime import datetime

# Fonction utilitaire pour convertir en int ou None
def coerce_int_or_none(value):
    if value == '' or value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None

# Widget personnalisé pour les sélections multiples
class MultiCheckboxField(SelectMultipleField):
    widget = ListWidget(prefix_label=False)
    option_widget = CheckboxInput()

# ============================================================================
# VALIDATEURS PERSONNALISÉS
# ============================================================================

def validate_date_echeance(form, field):
    """Valide que la date d'échéance est dans le futur"""
    if field.data and field.data < datetime.now().date():
        raise ValidationError('La date d\'échéance doit être dans le futur')

def validate_pourcentage(form, field):
    """Valide que le pourcentage est entre 0 et 100"""
    if field.data is not None and (field.data < 0 or field.data > 100):
        raise ValidationError('Le pourcentage doit être entre 0 et 100')

def validate_cause_racine(form, field):
    """Valide que la cause racine contient plusieurs niveaux d'analyse"""
    if field.data:
        # Vérifier qu'il y a plusieurs points (approche 5 Why)
        points = field.data.count('\n') + 1
        if points < 3:
            raise ValidationError('Pour une analyse 5 Why, veuillez indiquer au moins 3 niveaux d\'analyse')


class LoginForm(FlaskForm):
    username = StringField('Nom d’utilisateur', validators=[DataRequired()])
    password = PasswordField('Mot de passe', validators=[DataRequired()])
    remember_me = BooleanField('Se souvenir de moi')
    submit = SubmitField('Se connecter')

class UserForm(FlaskForm):
    username = StringField("Nom d'utilisateur", validators=[DataRequired(), Length(min=3, max=80)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    role = SelectField('Rôle', choices=[
        ('utilisateur', 'Utilisateur'),
        ('referent', 'Référent'),
        ('directeur', 'Directeur'),
        ('admin', 'Administrateur')
    ])
    department = StringField('Département')
    is_active = BooleanField('Actif')
    submit = SubmitField('Enregistrer')

class DirectionForm(FlaskForm):
    nom = StringField('Nom de la direction', validators=[DataRequired()])
    description = TextAreaField('Description')
    
    # 🔴 NOUVEAU: Type de responsable (utilisateur ou manuel)
    type_responsable = RadioField('Type de responsable', 
                                 choices=[('utilisateur', 'Sélectionner un utilisateur existant'),
                                          ('manuel', 'Saisir un nom manuellement')],
                                 default='utilisateur')
    
    # Pour la sélection d'utilisateur existant
    responsable_id = SelectField('Sélectionner un responsable', 
                                coerce=coerce_int_or_none, 
                                validators=[Optional()])
    
    # Pour la saisie manuelle
    responsable_nom_manuel = StringField('Nom du responsable', validators=[Optional()])
    
    submit = SubmitField('Créer la direction')
    
    def validate(self, *args, **kwargs):
        if not super().validate(*args, **kwargs):
            return False
        
        # Vérifier qu'au moins un type de responsable est renseigné
        if self.type_responsable.data == 'utilisateur' and (not self.responsable_id.data or self.responsable_id.data == 0):
            self.responsable_id.errors.append('Veuillez sélectionner un responsable ou choisir "Saisie manuelle"')
            return False
        elif self.type_responsable.data == 'manuel' and not self.responsable_nom_manuel.data:
            self.responsable_nom_manuel.errors.append('Veuillez saisir un nom')
            return False
        
        return True



class ServiceForm(FlaskForm):
    nom = StringField('Nom du service', validators=[DataRequired()])
    description = TextAreaField('Description')
    direction_id = SelectField('Direction', coerce=int, validators=[DataRequired()])
    
    # Type de responsable (utilisateur ou manuel)
    type_responsable = RadioField('Type de responsable', 
                                 choices=[('utilisateur', 'Sélectionner un utilisateur existant'),
                                          ('manuel', 'Saisir un nom manuellement')],
                                 default='utilisateur')
    
    # Pour la sélection d'utilisateur existant
    responsable_id = SelectField('Sélectionner un responsable', 
                                coerce=coerce_int_or_none, 
                                validators=[Optional()])
    
    # Pour la saisie manuelle
    responsable_nom_manuel = StringField('Nom du responsable', validators=[Optional()])
    
    # Membres de l'équipe (champ dynamique)
    equipe_membres = TextAreaField('Membres de l\'équipe (un par ligne)', 
                                  validators=[Optional()],
                                  description='Saisissez un nom par ligne')
    
    submit = SubmitField('Créer le service')
    
    # 🔴 CORRECTION: Ajouter *args, **kwargs
    def validate(self, *args, **kwargs):
        if not super().validate(*args, **kwargs):
            return False
        
        # Vérifier qu'au moins un type de responsable est renseigné
        if self.type_responsable.data == 'utilisateur' and (not self.responsable_id.data or self.responsable_id.data == 0):
            self.responsable_id.errors.append('Veuillez sélectionner un responsable ou choisir "Saisie manuelle"')
            return False
        elif self.type_responsable.data == 'manuel' and not self.responsable_nom_manuel.data:
            self.responsable_nom_manuel.errors.append('Veuillez saisir un nom')
            return False
        
        return True
        
class CartographieForm(FlaskForm):
    nom = StringField('Nom de la cartographie', validators=[DataRequired()])
    description = TextAreaField('Description')
    direction_id = SelectField('Direction', coerce=coerce_int_or_none, validators=[Optional()])
    service_id = SelectField('Service', coerce=coerce_int_or_none, validators=[Optional()])
    type_cartographie = RadioField('Type de cartographie', 
                                  choices=[('direction', 'Par Direction'), ('service', 'Par Service')],
                                  default='direction')
    submit = SubmitField('Créer la cartographie')

class RisqueForm(FlaskForm):
    intitule = StringField('Intitulé du risque', validators=[DataRequired()])
    description = TextAreaField('Description', validators=[DataRequired()])
    processus_concerne = StringField('Processus concerné')
    categorie = SelectField('Catégorie', choices=[
        ('', 'Sélectionnez une catégorie'),
        ('operationnel', 'Opérationnel'),
        ('financier', 'Financier'),
        ('juridique', 'Juridique'),
        ('compliance', 'Compliance'),
        ('reputation', 'Réputation'),
        ('strategique', 'Stratégique'),
        ('technologique', 'Technologique'),
        ('humain', 'Ressources Humaines'),
        ('environnemental', 'Environnemental')
    ], validators=[DataRequired()])
    type_risque = SelectField('Type de risque', choices=[
        ('', 'Sélectionnez un type'),
        ('inne', 'Inhérent'),
        ('residuel', 'Résiduel'),
        ('speculatif', 'Spéculatif')
    ], validators=[DataRequired()])
    cause_racine = TextAreaField('Cause racine')
    consequences = TextAreaField('Conséquences')
    submit = SubmitField('Créer le risque')

class EvaluationForm(FlaskForm):
    impact = SelectField('Impact', choices=[
        (0, 'Sélectionnez un niveau'),
        (1, '1 - Négligeable'),
        (2, '2 - Mineur'),
        (3, '3 - Modéré'),
        (4, '4 - Important'),
        (5, '5 - Critique')
    ], coerce=int, validators=[DataRequired()])
    probabilite = SelectField('Probabilité', choices=[
        (0, 'Sélectionnez un niveau'),
        (1, '1 - Très rare'),
        (2, '2 - Rare'),
        (3, '3 - Possible'),
        (4, '4 - Probable'),
        (5, '5 - Certain')
    ], coerce=int, validators=[DataRequired()])
    niveau_maitrise = SelectField('Niveau de maîtrise', choices=[
        (0, 'Sélectionnez un niveau'),
        (1, '1 - Insuffisant'),
        (2, '2 - Faible'),
        (3, '3 - Adéquat'),
        (4, '4 - Bon'),
        (5, '5 - Excellent')
    ], coerce=int, validators=[DataRequired()])
    commentaire = TextAreaField('Commentaire')
    submit = SubmitField('Enregistrer l\'évaluation')

class KRIForm(FlaskForm):
    nom = StringField('Nom du KRI', validators=[DataRequired()])
    description = TextAreaField('Description')
    formule_calcul = StringField('Formule de calcul')
    unite_mesure = StringField('Unité de mesure')
    seuil_cible = FloatField('Seuil cible (pour KPI)', validators=[Optional()])
    seuil_alerte = FloatField("Seuil d'alerte")
    seuil_critique = FloatField('Seuil critique')
    frequence_mesure = SelectField('Fréquence de mesure', choices=[
        ('quotidien', 'Quotidien'),
        ('hebdomadaire', 'Hebdomadaire'),
        ('mensuel', 'Mensuel'),
        ('trimestriel', 'Trimestriel'),
        ('annuel', 'Annuel')
    ])
    responsable_mesure_id = SelectField('Responsable de mesure', coerce=coerce_int_or_none, validators=[Optional()])
    
    # NOUVEAU CHAMP POUR LE SENS D'ÉVALUATION
    sens_evaluation_seuil = SelectField('Sens d\'évaluation du seuil', choices=[
        ('superieur', 'Risque si valeur > seuil'),
        ('inferieur', 'Risque si valeur < seuil')
    ], default='superieur')
    
    submit = SubmitField('Créer le KRI')

class ProcessusForm(FlaskForm):
    nom = StringField('Nom du processus', validators=[DataRequired()])
    description = TextAreaField('Description')
    direction_id = SelectField('Direction', coerce=coerce_int_or_none, validators=[Optional()])
    service_id = SelectField('Service', coerce=coerce_int_or_none, validators=[Optional()])
    responsable_id = SelectField('Responsable', coerce=coerce_int_or_none, validators=[Optional()])
    version = StringField('Version')
    statut = SelectField('Statut', choices=[
        ('actif', 'Actif'),
        ('inactif', 'Inactif'),
        ('archive', 'Archivé')
    ])
    submit = SubmitField('Créer le processus')

class VeilleReglementaireForm(FlaskForm):
    titre = StringField('Titre', validators=[DataRequired()])
    description = TextAreaField('Description')
    reference = StringField('Référence')
    type_reglementation = SelectField('Type', choices=[
        ('', 'Sélectionnez un type'),
        ('loi', 'Loi'),
        ('decret', 'Décret'),
        ('arrete', 'Arrêté'),
        ('norme', 'Norme'),
        ('directive', 'Directive'),
        ('reglement', 'Règlement'),
        ('circulaire', 'Circulaire'),
        ('autre', 'Autre')
    ], validators=[DataRequired()])
    organisme_emetteur = StringField('Organisme émetteur')
    date_publication = DateField('Date de publication', format='%Y-%m-%d')
    date_application = DateField('Date d\'application', format='%Y-%m-%d')
    statut = SelectField('Statut', choices=[
        ('', 'Sélectionnez un statut'),
        ('projet', 'Projet'),
        ('en_vigueur', 'En vigueur'),
        ('abroge', 'Abrogé'),
        ('modifie', 'Modifié'),
        ('en_revision', 'En révision'),
        ('suspendu', 'Suspendu')
    ], validators=[DataRequired()])
    impact_estime = SelectField('Impact estimé', choices=[
        ('', 'Sélectionnez un impact'),
        ('faible', 'Faible'),
        ('moyen', 'Moyen'),
        ('eleve', 'Élevé'),
        ('critique', 'Critique')
    ])
    submit = SubmitField('Enregistrer')

class DocumentVeilleForm(FlaskForm):  # Nouveau
    document = FileField('Document', validators=[
        FileRequired(),
        FileAllowed(['pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'txt', 'jpg', 'png'], 
                   'Types autorisés: PDF, Word, Excel, PowerPoint, images')
    ])
    description = StringField('Description (optionnelle)')
    submit = SubmitField('Téléverser')


class VeilleReglementaireForm(FlaskForm):
    titre = StringField('Titre', validators=[DataRequired()])
    description = TextAreaField('Description')
    reference = StringField('Référence')
    type_reglementation = SelectField('Type', choices=[
        ('', 'Sélectionnez un type'),
        ('loi', 'Loi'),
        ('decret', 'Décret'),
        ('arrete', 'Arrêté'),
        ('norme', 'Norme'),
        ('directive', 'Directive'),
        ('autre', 'Autre')
    ], validators=[DataRequired()])
    organisme_emetteur = StringField('Organisme émetteur')
    date_publication = DateField('Date de publication')
    date_application = DateField('Date d\'application')
    statut = SelectField('Statut', choices=[
        ('', 'Sélectionnez un statut'),
        ('projet', 'Projet'),
        ('en_vigueur', 'En vigueur'),
        ('abroge', 'Abrogé'),
        ('modifie', 'Modifié')
    ], validators=[DataRequired()])
    impact_estime = SelectField('Impact estimé', choices=[
        ('', 'Sélectionnez un impact'),
        ('faible', 'Faible'),
        ('moyen', 'Moyen'),
        ('eleve', 'Élevé')
    ])
    submit = SubmitField('Enregistrer')

class ProcessusForm(FlaskForm):
    nom = StringField('Nom du processus', validators=[DataRequired()])
    description = TextAreaField('Description')
    direction_id = SelectField('Direction', coerce=int)
    service_id = SelectField('Service', coerce=int)
    responsable_id = SelectField('Responsable', coerce=int)
    version = StringField('Version')
    statut = SelectField('Statut', choices=[
        ('', 'Sélectionnez un statut'),
        ('actif', 'Actif'),
        ('developpement', 'En développement'),
        ('inactif', 'Inactif'),
        ('archive', 'Archivé')
    ], validators=[DataRequired()])
    submit = SubmitField('Enregistrer')


# ============================================================================
# FORMULAIRES AUDIT - VERSION AVEC PROCESSUS MODIFIÉE
# ============================================================================

class AuditForm(FlaskForm):
    """Formulaire pour créer et modifier des audits avec toutes les fonctionnalités"""
    # Informations de base
    titre = StringField("Titre de l'audit", validators=[DataRequired()])
    description = TextAreaField("Description")
    type_audit = SelectField(
        "Type d'audit",
        choices=[],  # ← Laisser vide, sera défini dans la vue
        validators=[DataRequired()]
    )
    
    # NOUVEAU : Sélection du processus
    selection_processus = RadioField(
        "Méthode de sélection du processus",
        choices=[
            ('logigramme', 'Sélectionner depuis le logigramme'),
            ('manuel', 'Écrire manuellement'),
            ('aucun', 'Aucun processus spécifique')
        ],
        default='logigramme',
        validators=[DataRequired()]
    )
    
    processus_id = SelectField(
        "Processus audité (logigramme)", 
        coerce=coerce_int_or_none, 
        choices=[],  # ← Laisser vide
        validators=[Optional()]
    )
    
    processus_manuel = StringField(
        "Nom du processus (manuel)",
        validators=[Optional(), Length(max=500)]
    )
    
    # Planning
    date_debut_prevue = DateField(
        "Date de début prévue", 
        format='%Y-%m-%d', 
        validators=[Optional()]
    )
    date_fin_prevue = DateField(
        "Date de fin prévue", 
        format='%Y-%m-%d', 
        validators=[Optional()]
    )
    
    # Organisation
    responsable_id = SelectField(
        "Auditeur responsable", 
        coerce=coerce_int_or_none, 
        choices=[],  # ← Laisser vide
        validators=[Optional()]
    )
    
    # Équipe d'audit améliorée
    equipe_audit_ids = MultiCheckboxField(
        "Auditeurs participants",
        coerce=int,
        choices=[],  # ← Laisser vide
        validators=[Optional()]
    )
    participants_ids = MultiCheckboxField(
        "Participants interviewés",
        coerce=int,
        choices=[],  # ← Laisser vide
        validators=[Optional()]
    )
    observateurs_ids = MultiCheckboxField(
        "Observateurs",
        coerce=int,
        choices=[],  # ← Laisser vide
        validators=[Optional()]
    )
    parties_prenantes = TextAreaField(
        "Parties prenantes supplémentaires",
        description="Liste des personnes ou entités interviewées"
    )
    
    # Informations techniques
    portee = TextAreaField("Portée de l'audit")
    objectifs = TextAreaField("Objectifs")
    criteres = TextAreaField("Critères d'audit")
    
    # Configuration spécifique
    statut = SelectField(
        "Statut initial",
        choices=[
            ('', 'Sélectionnez un statut'),
            ('planifie', 'Planifié'),
            ('en_preparation', 'En préparation'),
            ('en_cours', 'En cours'),
            ('en_redaction', 'En rédaction'),
            ('en_validation', 'En validation'),
            ('clos', 'Clos')
        ],
        default='planifie'
    )
    
    # Sous-statut
    sous_statut = SelectField(
        "Sous-statut",
        choices=[
            ('', 'Sélectionnez un sous-statut'),
            ('planification', 'Planification'),
            ('preparation', 'Préparation'),
            ('collecte', 'Collecte des preuves'),
            ('analyse', 'Analyse'),
            ('redaction', 'Rédaction du rapport'),
            ('validation', 'Validation'),
            ('cloture', 'Clôture')
        ],
        validators=[Optional()]
    )
    
    submit = SubmitField("Enregistrer")
    
    def validate(self, extra_validators=None):
        """Validation personnalisée pour la sélection du processus"""
        if not super().validate():
            return False
        
        # Validation spécifique pour la sélection du processus
        if self.selection_processus.data == 'logigramme':
            if not self.processus_id.data:
                self.processus_id.errors.append('Veuillez sélectionner un processus')
                return False
        elif self.selection_processus.data == 'manuel':
            if not self.processus_manuel.data:
                self.processus_manuel.errors.append('Veuillez saisir un nom de processus')
                return False
            if len(self.processus_manuel.data.strip()) < 3:
                self.processus_manuel.errors.append('Le nom du processus doit contenir au moins 3 caractères')
                return False
        
        return True


class EditAuditForm(FlaskForm):
    """Formulaire pour modifier un audit existant"""
    titre = StringField("Titre de l'audit", validators=[DataRequired()])
    description = TextAreaField("Description")
    
    # Ajouter le champ type_audit
    type_audit = SelectField(
        "Type d'audit",
        choices=[],  # ← Laisser vide, sera défini dans la vue
        validators=[DataRequired()]
    )
    
    # NOUVEAU : Sélection du processus pour modification
    selection_processus = RadioField(
        "Méthode de sélection du processus",
        choices=[
            ('logigramme', 'Sélectionner depuis le logigramme'),
            ('manuel', 'Écrire manuellement'),
            ('aucun', 'Aucun processus spécifique')
        ],
        default='logigramme',
        validators=[DataRequired()]
    )
    
    processus_id = SelectField(
        "Processus audité (logigramme)", 
        coerce=coerce_int_or_none, 
        choices=[],  # ← Laisser vide
        validators=[Optional()]
    )
    
    processus_manuel = StringField(
        "Nom du processus (manuel)",
        validators=[Optional(), Length(max=500)]
    )
    
    # Statuts intelligents
    statut = SelectField(
        "Statut",
        choices=[
            ('planifie', 'Planifié'),
            ('en_preparation', 'En préparation'),
            ('en_collecte', 'En collecte'),
            ('en_analyse', 'En analyse'),
            ('en_redaction', 'En rédaction du rapport'),
            ('en_validation', 'En validation'),
            ('clos', 'Clos')
        ]
    )
    
    # Sous-statut
    sous_statut = SelectField(
        "Sous-statut",
        choices=[
            ('', 'Sélectionnez un sous-statut'),
            ('planification', 'Planification'),
            ('preparation', 'Préparation'),
            ('collecte', 'Collecte des preuves'),
            ('analyse', 'Analyse'),
            ('redaction', 'Rédaction du rapport'),
            ('validation', 'Validation'),
            ('cloture', 'Clôture')
        ],
        validators=[Optional()]
    )
    
    # Organisation
    responsable_id = SelectField(
        "Auditeur responsable", 
        coerce=coerce_int_or_none, 
        validators=[Optional()]
    )
    
    # Équipes
    equipe_audit_ids = MultiCheckboxField(
        "Auditeurs participants",
        coerce=int,
        validators=[Optional()]
    )
    participants_ids = MultiCheckboxField(
        "Participants interviewés",
        coerce=int,
        validators=[Optional()]
    )
    observateurs_ids = MultiCheckboxField(
        "Observateurs",
        coerce=int,
        validators=[Optional()]
    )
    
    # Dates
    date_debut_prevue = DateField(
        "Date de début prévue", 
        format='%Y-%m-%d', 
        validators=[Optional()]
    )
    date_fin_prevue = DateField(
        "Date de fin prévue", 
        format='%Y-%m-%d', 
        validators=[Optional()]
    )
    date_debut_reelle = DateField(
        "Date de début réelle", 
        format='%Y-%m-%d', 
        validators=[Optional()]
    )
    date_fin_reelle = DateField(
        "Date de fin réelle", 
        format='%Y-%m-%d', 
        validators=[Optional()]
    )
    
    # Informations complémentaires
    portee = TextAreaField("Portée de l'audit")
    objectifs = TextAreaField("Objectifs")
    criteres = TextAreaField("Critères d'audit")
    parties_prenantes = TextAreaField(
        "Parties prenantes supplémentaires",
        description="Liste des personnes ou entités interviewées"
    )
    commentaires = TextAreaField("Commentaires généraux")
    
    submit = SubmitField("Mettre à jour l'audit")
    
    def validate(self, extra_validators=None):
        """Validation personnalisée pour la sélection du processus"""
        if not super().validate():
            return False
        
        # Validation spécifique pour la sélection du processus
        if self.selection_processus.data == 'logigramme':
            if not self.processus_id.data:
                self.processus_id.errors.append('Veuillez sélectionner un processus')
                return False
        elif self.selection_processus.data == 'manuel':
            if not self.processus_manuel.data:
                self.processus_manuel.errors.append('Veuillez saisir un nom de processus')
                return False
            if len(self.processus_manuel.data.strip()) < 3:
                self.processus_manuel.errors.append('Le nom du processus doit contenir au moins 3 caractères')
                return False
        
        return True


class ArchiveAuditForm(FlaskForm):
    """Formulaire pour archiver un audit"""
    motif = TextAreaField(
        "Motif de l'archivage",
        validators=[DataRequired()],
        description="Veuillez indiquer la raison de l'archivage"
    )
    conserver_donnees = BooleanField(
        "Conserver toutes les données",
        default=True
    )
    submit = SubmitField("Archiver l'audit")

# ============================================================================
# FORMULAIRES CONSTATATION - VERSION AVEC 5 WHY ET FICHIERS
# ============================================================================
class AuditFilterForm(FlaskForm):
    """Formulaire de filtrage pour les audits"""
    statut = SelectField(
        "Statut",
        choices=[
            ('', 'Tous les statuts'),
            ('planifie', 'Planifié'),
            ('en_cours', 'En cours'),
            ('clos', 'Clos'),
            ('archive', 'Archivé')
        ],
        validators=[Optional()]
    )
    
    type_audit = SelectField(
        "Type d'audit",
        choices=[
            ('', 'Tous les types'),
            ('interne', 'Interne'),
            ('externe', 'Externe'),
            ('qualite', 'Qualité'),
            ('conformite', 'Conformité'),
            ('securite', 'Sécurité')
        ],
        validators=[Optional()]
    )
    
    date_debut_min = DateField(
        "Date début (min)",
        format='%Y-%m-%d',
        validators=[Optional()]
    )
    
    date_debut_max = DateField(
        "Date début (max)",
        format='%Y-%m-%d',
        validators=[Optional()]
    )
    
    # Recherche par processus
    processus_id = SelectField(
        "Processus audité",
        coerce=coerce_int_or_none,
        choices=[],  # ← Laisser vide, sera rempli dans la vue
        validators=[Optional()]
    )
    
    processus_nom = StringField(
        "Nom du processus",
        validators=[Optional()]
    )
    
    responsable_id = SelectField(
        "Responsable",
        coerce=coerce_int_or_none,
        choices=[],  # ← Laisser vide, sera rempli dans la vue
        validators=[Optional()]
    )
    
    submit = SubmitField("Filtrer")


class ConstatationFilterForm(FlaskForm):
    """Formulaire de filtrage pour les constatations"""
    type_constatation = SelectField(
        "Type",
        choices=[
            ('', 'Tous les types'),
            ('non_conformite', 'Non-conformité'),
            ('observation', 'Observation'),
            ('opportunite_amelioration', 'Opportunité d\'amélioration'),
            ('conforme', 'Conforme'),
            ('point_fort', 'Point fort')
        ],
        validators=[Optional()]
    )
    
    gravite = SelectField(
        "Gravité",
        choices=[
            ('', 'Toutes les gravités'),
            ('mineure', 'Mineure'),
            ('moyenne', 'Moyenne'),
            ('majeure', 'Majeure'),
            ('critique', 'Critique')
        ],
        validators=[Optional()]
    )
    
    statut = SelectField(
        "Statut",
        choices=[
            ('', 'Tous les statuts'),
            ('a_analyser', 'À analyser'),
            ('a_valider', 'À valider'),
            ('en_action', 'En action'),
            ('clos', 'Clos')
        ],
        validators=[Optional()]
    )
    
    # Filtre par processus
    processus_concerne = StringField(
        "Processus concerné",
        validators=[Optional()]
    )
    
    # Filtre par période
    date_min = DateField(
        "Date création (min)",
        format='%Y-%m-%d',
        validators=[Optional()]
    )
    
    date_max = DateField(
        "Date création (max)",
        format='%Y-%m-%d',
        validators=[Optional()]
    )
    
    # Filtre par risque
    avec_risque = SelectField(
        "Avec risque associé",
        choices=[
            ('', 'Toutes'),
            ('avec', 'Avec risque'),
            ('sans', 'Sans risque')
        ],
        validators=[Optional()]
    )
    
    submit = SubmitField("Filtrer")

class ExportAuditForm(FlaskForm):
    """Formulaire pour exporter des données d'audit"""
    format_export = SelectField(
        "Format d'export",
        choices=[
            ('pdf', 'PDF'),
            ('excel', 'Excel'),
            ('word', 'Word'),
            ('csv', 'CSV')
        ],
        default='pdf',
        validators=[DataRequired()]
    )
    
    # Sélection des données à exporter
    inclure_audit = BooleanField("Informations audit", default=True)
    inclure_constatations = BooleanField("Constatations", default=True)
    inclure_recommandations = BooleanField("Recommandations", default=True)
    inclure_plans_action = BooleanField("Plans d'action", default=True)
    inclure_preuves = BooleanField("Preuves (liens)", default=False)
    inclure_statistiques = BooleanField("Statistiques", default=True)
    
    # Options de mise en page
    avec_logo = BooleanField("Inclure le logo", default=True)
    avec_pied_page = BooleanField("Pied de page", default=True)
    numeroter_pages = BooleanField("Numéroter les pages", default=True)
    
    # Filtrage pour l'export
    date_min = DateField(
        "Période début",
        format='%Y-%m-%d',
        validators=[Optional()]
    )
    
    date_max = DateField(
        "Période fin",
        format='%Y-%m-%d',
        validators=[Optional()]
    )
    
    submit = SubmitField("Générer l'export")

class ConstatationForm(FlaskForm):
    """Formulaire de constatation avec tous les champs"""
    # Référence et description
    description = TextAreaField('Description', validators=[DataRequired()])
    
    # Classification
    type_constatation = SelectField('Type de constatation', choices=[
        ('', 'Sélectionnez un type'),
        ('non_conformite', 'Non-conformité'),
        ('observation', 'Observation'),
        ('opportunite_amelioration', 'Opportunité d\'amélioration'),
        ('conforme', 'Conforme'),
        ('point_fort', 'Point fort')
    ], validators=[DataRequired()])
    
    gravite = SelectField('Gravité', choices=[
        ('mineure', 'Mineure'),
        ('moyenne', 'Moyenne'),
        ('majeure', 'Majeure'),
        ('critique', 'Critique')
    ], default='moyenne')
    
    criticite = SelectField('Criticité', choices=[
        ('mineure', 'Mineure'),
        ('majeure', 'Majeure'),
        ('critique', 'Critique')
    ], default='mineure')
    
    # NOUVEAU : Sélection du processus pour constatation
    selection_processus_constatation = RadioField(
        "Sélection du processus concerné",
        choices=[
            ('from_audit', 'Utiliser le processus de l\'audit'),
            ('from_logigramme', 'Sélectionner dans le logigramme'),
            ('manuel', 'Écrire manuellement'),
            ('different', 'Processus différent')
        ],
        default='from_audit'
    )
    
    processus_concerne = StringField('Processus impacté', validators=[Optional()])
    
    # Liste des processus pour la sélection
    processus_list = SelectField(
        "Sélectionner un processus",
        choices=[],  # ← Laisser vide, sera rempli dans la vue
        validators=[Optional()]
    )
    
    processus_manuel_constatation = StringField(
        "Nom du processus (saisie manuelle)",
        validators=[Optional(), Length(max=500)]
    )
    
    # Cause racine avec méthode 5 Why
    cause_racine = TextAreaField(
        'Cause racine (méthode 5 Why)',
        description="Analyser la cause racine en posant 5 fois 'Pourquoi?'",
        validators=[validate_cause_racine, Optional()]
    )
    conclusion = TextAreaField(
        'Conclusion (apparaîtra dans le rapport définitif)',
        description="Synthèse et conclusion qui sera incluse dans le rapport final"
    )
    
    commentaires = TextAreaField(
        'Commentaires complémentaires',
        description="Commentaires internes pour l'équipe d'audit"
    )
    
    recommandations_immediates = TextAreaField(
        'Recommandations immédiates',
        description="Actions correctives immédiates proposées"
    )
    
    # Justificatifs et preuves
    documents_justificatifs = TextAreaField('Documents justificatifs')
    preuves = TextAreaField('Preuves collectées')
    
    # Risque associé
    risque_id = SelectField(
        'Risque associé', 
        coerce=coerce_int_or_none, 
        validators=[Optional()]
    )
    
    # Workflow
    statut = SelectField('Statut', choices=[
        ('a_analyser', 'À analyser'),
        ('a_valider', 'À valider'),
        ('en_action', 'En action'),
        ('clos', 'Clos')
    ], default='a_analyser')
    
    # Upload de fichiers
    fichier_preuve = FileField(
        'Ajouter une preuve (PDF, image, Word)',
        validators=[
            Optional(),
            FileAllowed(['pdf', 'png', 'jpg', 'jpeg', 'doc', 'docx'], 
                       'Formats acceptés: PDF, PNG, JPG, DOC, DOCX')
        ]
    )
    
    submit = SubmitField('Enregistrer la constatation')
    
    def validate(self, extra_validators=None):
        """Validation personnalisée pour la sélection du processus de constatation"""
        if not super().validate():
            return False
        
        # Validation spécifique pour la sélection du processus
        if self.selection_processus_constatation.data == 'manuel':
            if not self.processus_manuel_constatation.data:
                self.processus_manuel_constatation.errors.append('Veuillez saisir un nom de processus')
                return False
            if len(self.processus_manuel_constatation.data.strip()) < 3:
                self.processus_manuel_constatation.errors.append('Le nom du processus doit contenir au moins 3 caractères')
                return False
        elif self.selection_processus_constatation.data == 'from_logigramme':
            if not self.processus_list.data:
                self.processus_list.errors.append('Veuillez sélectionner un processus')
                return False
        
        return True


class EditConstatationForm(FlaskForm):
    """Formulaire pour modifier une constatation"""
    description = TextAreaField('Description', validators=[DataRequired()])
    
    type_constatation = SelectField('Type de constatation', choices=[
        ('non_conformite', 'Non-conformité'),
        ('observation', 'Observation'),
        ('opportunite_amelioration', 'Opportunité d\'amélioration'),
        ('conforme', 'Conforme'),
        ('point_fort', 'Point fort')
    ], validators=[DataRequired()])
    
    gravite = SelectField('Gravité', choices=[
        ('mineure', 'Mineure'),
        ('moyenne', 'Moyenne'),
        ('majeure', 'Majeure'),
        ('critique', 'Critique')
    ])
    
    criticite = SelectField('Criticité', choices=[
        ('mineure', 'Mineure'),
        ('majeure', 'Majeure'),
        ('critique', 'Critique')
    ])
    
    # Processus concerné
    selection_processus_constatation = RadioField(
        "Sélection du processus concerné",
        choices=[
            ('keep', 'Conserver le processus actuel'),
            ('from_logigramme', 'Sélectionner dans le logigramme'),
            ('manuel', 'Modifier manuellement'),
            ('from_audit', 'Utiliser le processus de l\'audit')
        ],
        default='keep'
    )
    
    processus_concerne = StringField('Processus impacté', validators=[Optional()])
    
    # Liste des processus pour la sélection
    processus_list = SelectField(
        "Sélectionner un processus",
        choices=[],  # ← Laisser vide, sera rempli dans la vue
        validators=[Optional()]
    )
    
    processus_manuel_constatation = StringField(
        "Nom du processus (modification manuelle)",
        validators=[Optional(), Length(max=500)]
    )
    
    cause_racine = TextAreaField('Cause racine (méthode 5 Why)', validators=[validate_cause_racine, Optional()])
    
    # Workflow
    statut = SelectField('Statut', choices=[
        ('a_analyser', 'À analyser'),
        ('a_valider', 'À valider'),
        ('en_action', 'En action'),
        ('clos', 'Clos')
    ])
    
    # Commentaires supplémentaires
    commentaires = TextAreaField('Commentaires supplémentaires')
    
    # Upload de fichiers supplémentaires
    nouveau_fichier = FileField(
        'Ajouter un nouveau fichier',
        validators=[
            Optional(),
            FileAllowed(['pdf', 'png', 'jpg', 'jpeg', 'doc', 'docx'], 
                       'Formats acceptés: PDF, PNG, JPG, DOC, DOCX')
        ]
    )
    
    submit = SubmitField('Mettre à jour')
    
    def validate(self, extra_validators=None):
        """Validation personnalisée pour la modification du processus"""
        if not super().validate():
            return False
        
        # Validation spécifique pour la sélection du processus
        if self.selection_processus_constatation.data == 'manuel':
            if not self.processus_manuel_constatation.data:
                self.processus_manuel_constatation.errors.append('Veuillez saisir un nom de processus')
                return False
            if len(self.processus_manuel_constatation.data.strip()) < 3:
                self.processus_manuel_constatation.errors.append('Le nom du processus doit contenir au moins 3 caractères')
                return False
        elif self.selection_processus_constatation.data == 'from_logigramme':
            if not self.processus_list.data:
                self.processus_list.errors.append('Veuillez sélectionner un processus')
                return False
        
        return True


# ============================================================================
# FORMULAIRES RECOMMANDATION - VERSION AVEC PRIORISATION ET HISTORIQUE
# ============================================================================
class RecommandationForm(FlaskForm):
    """Formulaire pour créer des recommandations avec typologie avancée"""
    description = TextAreaField(
        "Description de la recommandation", 
        validators=[DataRequired()]
    )
    
    # Typologie avancée
    type_recommandation = SelectField(
        "Type de recommandation",
        choices=[
            ('', 'Sélectionnez un type'),
            ('corrective', 'Corrective'),
            ('preventive', 'Préventive'),
            ('amelioration', 'Amélioration'),
            ('optimisation', 'Optimisation')
        ],
        validators=[DataRequired()]
    )
    
    categorie = SelectField(
        "Catégorie",
        choices=[
            ('', 'Sélectionnez une catégorie'),
            ('conformite_reglementaire', 'Conformité réglementaire'),
            ('amelioration_continue', 'Amélioration continue'),
            ('reduction_risque', 'Réduction de risque'),
            ('optimisation_processus', 'Optimisation de processus'),
            ('securite_controle_interne', 'Sécurité / Contrôle interne'),
            ('performance', 'Amélioration de la performance'),
            ('cout', 'Réduction des coûts')
        ],
        validators=[Optional()]
    )
    
    # Délais
    delai_mise_en_oeuvre = SelectField(
        "Délai de mise en œuvre",
        choices=[
            ('', 'Sélectionnez un délai'),
            ('immediat', 'Immédiat (≤ 15 jours)'),
            ('court_terme', 'Court terme (1-3 mois)'),
            ('moyen_terme', 'Moyen terme (3-6 mois)'),
            ('long_terme', 'Long terme (>6 mois)')
        ]
    )
    
    date_echeance = DateField(
        "Date d'échéance", 
        format='%Y-%m-%d', 
        validators=[Optional(), validate_date_echeance]
    )
    
    # Priorisation automatique
    urgence = SelectField(
        "Niveau d'urgence",
        choices=[
            ('1', 'Très faible'),
            ('2', 'Faible'),
            ('3', 'Moyen'),
            ('4', 'Élevé'),
            ('5', 'Critique')
        ],
        default='3'
    )
    
    impact_operationnel = SelectField(
        "Impact opérationnel",
        choices=[
            ('1', 'Négligeable'),
            ('2', 'Limité'),
            ('3', 'Modéré'),
            ('4', 'Important'),
            ('5', 'Critique')
        ],
        default='3'
    )
    
    # Associations
    constatation_id = SelectField(
        "Constatation associée", 
        coerce=coerce_int_or_none, 
        validators=[Optional()]
    )
    
    risque_id = SelectField(
        "Risque associé", 
        coerce=coerce_int_or_none, 
        validators=[Optional()]
    )
    
    # Responsable
    responsable_id = SelectField(
        "Responsable de mise en œuvre", 
        coerce=coerce_int_or_none, 
        validators=[Optional()]
    )
    
    submit = SubmitField("Ajouter la recommandation")


class EditRecommandationForm(FlaskForm):
    """Formulaire pour modifier une recommandation avec historique"""
    description = TextAreaField("Description", validators=[DataRequired()])
    
    # Statut et avancement
    statut = SelectField(
        "Statut",
        choices=[
            ('a_traiter', 'À traiter'),
            ('en_cours', 'En cours'),
            ('termine', 'Terminé'),
            ('retarde', 'Retardé'),
            ('annule', 'Annulé')
        ]
    )
    
    taux_avancement = IntegerField(
        "Taux d'avancement (%)",
        validators=[Optional(), NumberRange(min=0, max=100), validate_pourcentage],
        default=0
    )
    
    # Délais modifiables
    date_echeance = DateField(
        "Date d'échéance", 
        format='%Y-%m-%d', 
        validators=[Optional(), validate_date_echeance]
    )
    
    # Changement de responsable
    responsable_id = SelectField(
        "Responsable", 
        coerce=coerce_int_or_none, 
        validators=[Optional()]
    )
    
    # Commentaire pour l'historique
    commentaire_modification = TextAreaField(
        "Commentaire sur la modification",
        description="Ce commentaire sera enregistré dans l'historique"
    )
    
    submit = SubmitField("Mettre à jour")


# ============================================================================
# FORMULAIRES PLAN D'ACTION - VERSION AVEC SOUS-ACTIONS ET GANTT
# ============================================================================

class PlanActionForm(FlaskForm):
    """Formulaire pour créer des plans d'action avec sous-actions"""
    # Informations de base
    nom = StringField('Nom du plan', validators=[DataRequired()])
    description = TextAreaField('Description du plan')
    
    # Planning
    date_debut = DateField(
        'Date de début', 
        format='%Y-%m-%d', 
        validators=[Optional()]
    )
    date_fin_prevue = DateField(
        'Date fin prévue', 
        format='%Y-%m-%d', 
        validators=[Optional(), validate_date_echeance]
    )
    
    # Associations multiples
    recommandation_id = SelectField(
        'Recommandation associée', 
        coerce=coerce_int_or_none, 
        validators=[Optional()]
    )
    
    risque_id = SelectField(
        'Risque associé', 
        coerce=coerce_int_or_none, 
        validators=[Optional()]
    )
    
    constatations_ids = MultiCheckboxField(
        'Constatations liées',
        coerce=int,
        validators=[Optional()]
    )
    
    # Responsable
    responsable_id = SelectField(
        'Responsable du plan', 
        coerce=coerce_int_or_none, 
        validators=[Optional()]
    )
    
    # Alertes automatiques
    notifier_7j_avant = BooleanField(
        'Notifier 7 jours avant échéance',
        default=True
    )
    notifier_echeance = BooleanField(
        'Notifier à l\'échéance',
        default=True
    )
    notifier_retard = BooleanField(
        'Notifier en cas de retard',
        default=True
    )
    
    submit = SubmitField('Créer le plan d\'action')


class SousActionForm(FlaskForm):
    """Formulaire pour une sous-action individuelle"""
    description = TextAreaField(
        'Description de la sous-action', 
        validators=[DataRequired()]
    )
    date_debut = DateField(
        'Date de début', 
        format='%Y-%m-%d', 
        validators=[Optional()]
    )
    date_fin_prevue = DateField(
        'Date fin prévue', 
        format='%Y-%m-%d', 
        validators=[Optional(), validate_date_echeance]
    )
    responsable_id = SelectField(
        'Responsable', 
        coerce=coerce_int_or_none, 
        validators=[Optional()]
    )
    pourcentage_realisation = IntegerField(
        'Progression (%)',
        validators=[Optional(), NumberRange(min=0, max=100), validate_pourcentage],
        default=0
    )
    submit = SubmitField('Ajouter la sous-action')


class EditPlanActionForm(FlaskForm):
    """Formulaire pour modifier un plan d'action"""
    nom = StringField('Nom du plan', validators=[DataRequired()])
    description = TextAreaField('Description')
    
    # Statut
    statut = SelectField(
        'Statut',
        choices=[
            ('en_attente', 'En attente'),
            ('en_cours', 'En cours'),
            ('termine', 'Terminé'),
            ('retarde', 'Retardé'),
            ('suspendu', 'Suspendu')
        ]
    )
    
    # Dates réelles
    date_debut_reelle = DateField(
        'Date de début réelle', 
        format='%Y-%m-%d', 
        validators=[Optional()]
    )
    date_fin_reelle = DateField(
        'Date de fin réelle', 
        format='%Y-%m-%d', 
        validators=[Optional()]
    )
    
    # Évaluation finale
    efficacite = SelectField(
        'Efficacité du plan',
        choices=[
            ('', 'Non évalué'),
            ('efficace', 'Efficace'),
            ('partiellement_efficace', 'Partiellement efficace'),
            ('inefficace', 'Inefficace')
        ],
        validators=[Optional()]
    )
    
    score_efficacite = IntegerField(
        'Score d\'efficacité (0-100)',
        validators=[Optional(), NumberRange(min=0, max=100), validate_pourcentage]
    )
    
    commentaire_evaluation = TextAreaField('Commentaire d\'évaluation')
    
    submit = SubmitField('Mettre à jour le plan')


# ============================================================================
# FORMULAIRES RISQUES ET MATRICE
# ============================================================================

class AssociationRisquesForm(FlaskForm):
    """Formulaire pour associer plusieurs risques à un audit"""
    risques_ids = MultiCheckboxField(
        'Sélectionner les risques',
        coerce=int,
        validators=[Optional()]
    )
    
    impact_audit = SelectField(
        'Impact de l\'audit sur le risque',
        choices=[
            ('', 'Sélectionnez un impact'),
            ('aggrave', 'Aggrave le risque'),
            ('reduit', 'Réduit le risque'),
            ('neutre', 'Impact neutre'),
            ('incertain', 'Impact incertain')
        ],
        validators=[Optional()]
    )
    
    commentaire = TextAreaField('Commentaire sur l\'association')
    
    submit = SubmitField('Associer les risques')


class MatriceMaturiteForm(FlaskForm):
    """Formulaire pour la matrice de maturité/conformité"""
    exigence = StringField(
        'Exigence réglementaire',
        validators=[DataRequired()]
    )
    
    niveau_conformite = SelectField(
        'Niveau de conformité',
        choices=[
            ('conforme', 'Conforme'),
            ('partiellement_conforme', 'Partiellement conforme'),
            ('non_conforme', 'Non conforme'),
            ('non_applicable', 'Non applicable')
        ],
        validators=[DataRequired()]
    )
    
    commentaire = TextAreaField('Commentaires')
    
    risques_associes = TextAreaField('Risques associés')
    
    submit = SubmitField('Ajouter à la matrice')


# FORMULAIRES SIMPLIFIÉS POUR LES ROUTES EXISTANTES
# ============================================================================
class SimpleAuditForm(FlaskForm):
    """Formulaire simple pour créer un audit (compatible)"""
    titre = StringField("Titre de l'audit", validators=[DataRequired()])
    description = TextAreaField("Description")
    type_audit = SelectField(
        "Type d'audit",
        choices=[
            ('', 'Sélectionnez un type'),
            ('interne', 'Interne'),
            ('externe', 'Externe'),
            ('qualite', 'Qualité'),
            ('conformite', 'Conformité'),
            ('securite', 'Sécurité'),
            ('performance', 'Performance'),
            ('financier', 'Financier'),
            ('operationnel', 'Opérationnel'),
            ('systeme', 'Système')
        ],
        validators=[DataRequired()]
    )
    
    # SUPPRIMEZ CE processus_id (première occurrence) et gardez celui d'en bas
    
    responsable_id = SelectField(
        "Responsable", 
        coerce=coerce_int_or_none, 
        validators=[Optional()]
    )
    date_debut_prevue = DateField(
        "Date de début prévue", 
        format='%Y-%m-%d', 
        validators=[Optional()]
    )
    date_fin_prevue = DateField(
        "Date de fin prévue", 
        format='%Y-%m-%d', 
        validators=[Optional()]
    )
    portee = TextAreaField("Portée de l'audit")
    objectifs = TextAreaField("Objectifs")
    criteres = TextAreaField("Critères")
    parties_prenantes = TextAreaField("Parties prenantes")
    
    # AJOUTEZ CES CHAMPS :
    statut = SelectField(
        "Statut",
        choices=[
            ('planifie', 'Planifié'),
            ('en_cours', 'En cours'),
            ('termine', 'Terminé'),
            ('annule', 'Annulé'),
            ('archive', 'Archivé')
        ],
        default='planifie',
        validators=[Optional()]
    )
    
    sous_statut = SelectField(
        "Sous-statut",
        choices=[
            ('preparation', 'Préparation'),
            ('collecte', 'Collecte'),
            ('analyse', 'Analyse'),
            ('redaction', 'Rédaction'),
            ('validation', 'Validation'),
            ('cloture', 'Clôturé')
        ],
        validators=[Optional()]
    )
    
    equipe_audit_ids = SelectMultipleField(
        "Équipe d'audit",
        coerce=int,
        validators=[Optional()]
    )
    
    participants_ids = SelectMultipleField(
        "Participants",
        coerce=int,
        validators=[Optional()]
    )
    
    observateurs_ids = SelectMultipleField(
        "Observateurs",
        coerce=int,
        validators=[Optional()]
    )
    
    # NOUVEAUX CHAMPS POUR LA SÉLECTION DE PROCESSUS
    selection_processus = RadioField(
        "Méthode de sélection du processus",
        choices=[
            ('logigramme', 'Sélectionner depuis le logigramme'),
            ('manuel', 'Écrire manuellement'),
            ('aucun', 'Aucun processus spécifique')
        ],
        default='logigramme',
        validators=[DataRequired()]
    )
    
    # CHAMP POUR LOGIGRAMME (gardez celui-ci, supprimez celui du haut)
    processus_id = SelectField(
        "Processus audité (logigramme)", 
        coerce=coerce_int_or_none, 
        choices=[],  # ← IMPORTANT: laisser vide, sera rempli dans la vue
        validators=[Optional()]
    )
    
    processus_manuel = StringField(
        "Nom du processus (manuel)",
        validators=[Optional(), Length(max=500)]
    )
    
    submit = SubmitField("Enregistrer")
    
    def validate(self, extra_validators=None):
        """Validation personnalisée pour la sélection du processus"""
        if not super().validate():
            return False
        
        # Validation spécifique pour la sélection du processus
        if self.selection_processus.data == 'logigramme':
            if not self.processus_id.data:
                self.processus_id.errors.append('Veuillez sélectionner un processus')
                return False
        elif self.selection_processus.data == 'manuel':
            if not self.processus_manuel.data:
                self.processus_manuel.errors.append('Veuillez saisir un nom de processus')
                return False
            if len(self.processus_manuel.data.strip()) < 3:
                self.processus_manuel.errors.append('Le nom du processus doit contenir au moins 3 caractères')
                return False
        
        return True
# ============================================================================
# FORMULAIRES COMMENTAIRES ET NOTIFICATIONS
# ============================================================================

class CommentaireForm(FlaskForm):
    """Formulaire pour ajouter des commentaires sur les modules"""
    contenu = TextAreaField(
        'Votre commentaire',
        validators=[DataRequired()],
        description="Ce commentaire sera visible par tous les membres de l'équipe d'audit"
    )
    
    type_entite = HiddenField()  # 'audit', 'constatation', 'recommandation', 'plan_action'
    entite_id = HiddenField()
    
    submit = SubmitField('Ajouter le commentaire')


class NotificationPreferencesForm(FlaskForm):
    """Formulaire pour les préférences de notifications"""
    
    # Section Email
    email_nouvelle_constatation = BooleanField(
        'Nouvelle constatation',
        description='Recevoir un email lorsqu\'une nouvelle constatation est créée',
        default=True
    )
    email_nouvelle_recommandation = BooleanField(
        'Nouvelle recommandation',
        description='Recevoir un email lorsqu\'une nouvelle recommandation est créée',
        default=True
    )
    email_nouveau_plan = BooleanField(
        'Nouveau plan d\'action',
        description='Recevoir un email lorsqu\'un nouveau plan d\'action est créé',
        default=True
    )
    email_echeance_7j = BooleanField(
        'Échéance dans 7 jours',
        description='Recevoir un email 7 jours avant une échéance',
        default=True
    )
    email_echeance_3j = BooleanField(
        'Échéance dans 3 jours',
        description='Recevoir un email 3 jours avant une échéance',
        default=True
    )
    email_echeance_1j = BooleanField(
        'Échéance dans 1 jour',
        description='Recevoir un email 1 jour avant une échéance',
        default=True
    )
    email_retard = BooleanField(
        'Plan en retard',
        description='Recevoir un email lorsqu\'un plan d\'action est en retard',
        default=True
    )
    email_validation_requise = BooleanField(
        'Validation requise',
        description='Recevoir un email lorsqu\'une validation est requise',
        default=True
    )
    email_kri_alerte = BooleanField(
        'Alerte KRI',
        description='Recevoir un email lors d\'une alerte KRI',
        default=True
    )
    email_veille_nouvelle = BooleanField(
        'Nouvelle veille réglementaire',
        description='Recevoir un email lors d\'une nouvelle veille réglementaire',
        default=False
    )
    
    # Fréquence des emails de synthèse
    frequence_email = SelectField(
        'Fréquence des emails de synthèse',
        choices=[
            ('immediat', 'Immédiat (à chaque notification)'),
            ('quotidien', 'Quotidien'),
            ('hebdomadaire', 'Hebdomadaire'),
            ('mensuel', 'Mensuel'),
            ('jamais', 'Jamais')
        ],
        default='quotidien'
    )
    
    # Section Web/Application
    web_nouvelle_constatation = BooleanField(
        'Notifications web pour nouvelle constatation',
        default=True
    )
    web_nouvelle_recommandation = BooleanField(
        'Notifications web pour nouvelle recommandation',
        default=True
    )
    web_nouveau_plan = BooleanField(
        'Notifications web pour nouveau plan d\'action',
        default=True
    )
    web_echeance_7j = BooleanField(
        'Notifications web pour échéance dans 7 jours',
        default=True
    )
    web_echeance_3j = BooleanField(
        'Notifications web pour échéance dans 3 jours',
        default=True
    )
    web_echeance_1j = BooleanField(
        'Notifications web pour échéance dans 1 jour',
        default=True
    )
    web_retard = BooleanField(
        'Notifications web pour plan en retard',
        default=True
    )
    web_validation_requise = BooleanField(
        'Notifications web pour validation requise',
        default=True
    )
    web_kri_alerte = BooleanField(
        'Notifications web pour alerte KRI',
        default=True
    )
    web_veille_nouvelle = BooleanField(
        'Notifications web pour nouvelle veille réglementaire',
        default=True
    )
    web_audit_demarre = BooleanField(
        'Notifications web pour audit démarré',
        default=True
    )
    web_audit_termine = BooleanField(
        'Notifications web pour audit terminé',
        default=True
    )
    
    # Options générales
    pause_until = DateField(
        'Mettre en pause les notifications jusqu\'à',
        format='%Y-%m-%d',
        validators=[Optional()],
        description='Mettre en pause toutes les notifications jusqu\'à cette date'
    )
    
    submit = SubmitField('Enregistrer les préférences')

    def populate_from_user(self, user):
        """
        Remplit le formulaire avec les préférences de l'utilisateur
        Version CORRIGÉE qui gère tous les champs
        """
        if not hasattr(user, 'preferences_notifications'):
            return
        
        prefs = user.preferences_notifications or {}
        
        try:
            # 1. Remplir les préférences EMAIL
            email_prefs = prefs.get('email', {})
            
            # CORRECTION : vérifier chaque champ individuellement
            email_fields = [
                'nouvelle_constatation', 'nouvelle_recommandation', 'nouveau_plan',
                'echeance_7j', 'echeance_3j', 'echeance_1j', 'retard',
                'validation_requise', 'kri_alerte', 'veille_nouvelle'
            ]
            
            for field_name in email_fields:
                form_field_name = f'email_{field_name}'
                if hasattr(self, form_field_name):
                    field_value = email_prefs.get(field_name, True)  # Default to True
                    getattr(self, form_field_name).data = field_value
                else:
                    print(f"⚠️ Champ manquant dans le formulaire: {form_field_name}")
            
            # 2. Remplir les préférences WEB
            web_prefs = prefs.get('web', {})
            
            web_fields = [
                'nouvelle_constatation', 'nouvelle_recommandation', 'nouveau_plan',
                'echeance_7j', 'echeance_3j', 'echeance_1j', 'retard',
                'validation_requise', 'kri_alerte', 'veille_nouvelle',
                'audit_demarre', 'audit_termine'
            ]
            
            for field_name in web_fields:
                form_field_name = f'web_{field_name}'
                if hasattr(self, form_field_name):
                    field_value = web_prefs.get(field_name, True)  # Default to True
                    getattr(self, form_field_name).data = field_value
                else:
                    print(f"⚠️ Champ manquant dans le formulaire: {form_field_name}")
            
            # 3. Remplir la fréquence (champ existant dans le formulaire corrigé)
            if hasattr(self, 'frequence_email'):
                self.frequence_email.data = prefs.get('frequence_email', 'quotidien')
            
            # 4. Remplir la date de pause
            if hasattr(self, 'pause_until'):
                pause_date = prefs.get('pause_until')
                if pause_date:
                    try:
                        if isinstance(pause_date, str):
                            self.pause_until.data = datetime.strptime(pause_date, '%Y-%m-%d').date()
                        elif isinstance(pause_date, datetime):
                            self.pause_until.data = pause_date.date()
                    except Exception as e:
                        print(f"⚠️ Erreur conversion date pause: {e}")
            
        except Exception as e:
            print(f"❌ Erreur dans populate_from_user: {e}")
            import traceback
            traceback.print_exc()

    def save_to_user(self, user):
        """
        Sauvegarde les préférences du formulaire dans l'utilisateur
        """
        if not hasattr(user, 'preferences_notifications'):
            user.preferences_notifications = {}
        
        prefs = user.preferences_notifications.copy() if user.preferences_notifications else {}
        
        # 1. Sauvegarder les préférences EMAIL
        if 'email' not in prefs:
            prefs['email'] = {}
        
        email_fields = [
            'nouvelle_constatation', 'nouvelle_recommandation', 'nouveau_plan',
            'echeance_7j', 'echeance_3j', 'echeance_1j', 'retard',
            'validation_requise', 'kri_alerte', 'veille_nouvelle'
        ]
        
        for field_name in email_fields:
            form_field_name = f'email_{field_name}'
            if hasattr(self, form_field_name):
                prefs['email'][field_name] = getattr(self, form_field_name).data
        
        # 2. Sauvegarder les préférences WEB
        if 'web' not in prefs:
            prefs['web'] = {}
        
        web_fields = [
            'nouvelle_constatation', 'nouvelle_recommandation', 'nouveau_plan',
            'echeance_7j', 'echeance_3j', 'echeance_1j', 'retard',
            'validation_requise', 'kri_alerte', 'veille_nouvelle',
            'audit_demarre', 'audit_termine'
        ]
        
        for field_name in web_fields:
            form_field_name = f'web_{field_name}'
            if hasattr(self, form_field_name):
                prefs['web'][field_name] = getattr(self, form_field_name).data
        
        # 3. Sauvegarder la fréquence
        if hasattr(self, 'frequence_email'):
            prefs['frequence_email'] = self.frequence_email.data
        
        # 4. Sauvegarder la date de pause
        if hasattr(self, 'pause_until'):
            if self.pause_until.data:
                prefs['pause_until'] = self.pause_until.data.isoformat()
            elif 'pause_until' in prefs:
                del prefs['pause_until']
        
        user.preferences_notifications = prefs
        return True
                
# ============================================================================
# FORMULAIRES EXPORT ET RAPPORTS
# ============================================================================

class ExportRapportForm(FlaskForm):
    """Formulaire pour configurer l'export de rapport"""
    format_export = SelectField(
        'Format d\'export',
        choices=[
            ('pdf', 'PDF'),
            ('word', 'Word (.docx)'),
            ('excel', 'Excel (.xlsx)')
        ],
        default='pdf'
    )
    
    sections = MultiCheckboxField(
        'Sections à inclure',
        choices=[
            ('informations', 'Informations générales'),
            ('constatations', 'Constatations'),
            ('recommandations', 'Recommandations'),
            ('plans_action', 'Plans d\'action'),
            ('matrice_maturite', 'Matrice de maturité'),
            ('statistiques', 'Statistiques'),
            ('synthèse', 'Synthèse et conclusions')
        ],
        default=['informations', 'constatations', 'recommandations', 'plans_action', 'synthèse']
    )
    
    inclure_logo = BooleanField('Inclure le logo', default=True)
    inclure_signature = BooleanField('Inclure une zone de signature', default=True)
    
    submit = SubmitField('Générer le rapport')


# ============================================================================
# FORMULAIRES IA ET ANALYSE AVANCÉE (PREMIUM)
# ============================================================================

class AnalyseIAForm(FlaskForm):
    """Formulaire pour l'analyse IA des constatations"""
    analyse_causes_racines = BooleanField(
        'Analyser les causes racines',
        default=True,
        description="L'IA suggérera les causes probables"
    )
    
    suggerer_recommandations = BooleanField(
        'Suggérer des recommandations',
        default=True,
        description="L'IA proposera des recommandations basées sur les constatations"
    )
    
    identifier_risques = BooleanField(
        'Identifier les risques impactés',
        default=True,
        description="L'IA identifiera les risques potentiellement impactés"
    )
    
    profondeur_analyse = SelectField(
        'Profondeur de l\'analyse',
        choices=[
            ('rapide', 'Analyse rapide'),
            ('standard', 'Analyse standard'),
            ('approfondie', 'Analyse approfondie')
        ],
        default='standard'
    )
    
    submit = SubmitField('Lancer l\'analyse IA')


class ChecklistAuditForm(FlaskForm):
    """Formulaire pour sélectionner une checklist métier"""
    type_checklist = SelectField(
        'Type de checklist',
        choices=[
            ('', 'Sélectionnez un type'),
            ('finance', 'Audit Finance'),
            ('rh', 'Audit Ressources Humaines'),
            ('it', 'AudIT Informatique'),
            ('qualite', 'Audit Qualité'),
            ('securite', 'Audit Sécurité'),
            ('achats', 'Audit Achats'),
            ('production', 'Audit Production')
        ],
        validators=[DataRequired()]
    )
    
    appliquer_template = BooleanField(
        'Appliquer le template',
        default=True,
        description="Crée automatiquement des constatations types basées sur la checklist"
    )
    
    customiser = BooleanField(
        'Personnaliser la checklist',
        default=False,
        description="Modifier les éléments de la checklist avant application"
    )
    
    submit = SubmitField('Utiliser cette checklist')


# ============================================================================
# FORMULAIRES CONFIGURATION AUDIT
# ============================================================================

class ConfigurationAuditForm(FlaskForm):
    """Configuration des paramètres d'audit"""
    nom_config = StringField('Nom de la configuration', validators=[DataRequired()])
    type_audit = SelectField(
        'Type d\'audit cible',
        choices=[
            ('interne', 'Interne'),
            ('externe', 'Externe'),
            ('qualite', 'Qualité'),
            ('conformite', 'Conformité')
        ],
        validators=[DataRequired()]
    )
    duree_standard = IntegerField(
        'Durée standard (jours)',
        validators=[DataRequired(), NumberRange(min=1, max=365)],
        default=30
    )
    seuil_gravite_min = IntegerField(
        'Seuil gravité minimum',
        validators=[DataRequired(), NumberRange(min=1, max=10)],
        default=3
    )
    seuil_gravite_max = IntegerField(
        'Seuil gravité maximum',
        validators=[DataRequired(), NumberRange(min=1, max=10)],
        default=5
    )
    categories_audit = TextAreaField(
        'Catégories d\'audit',
        description="Une catégorie par ligne"
    )
    submit = SubmitField('Enregistrer')


class TemplateConstatationForm(FlaskForm):
    """Template de constatation"""
    reference = StringField('Référence', validators=[DataRequired()])
    titre = StringField('Titre', validators=[DataRequired()])
    description = TextAreaField('Description', validators=[DataRequired()])
    type_constatation = SelectField(
        'Type de constatation',
        choices=[
            ('non_conformite', 'Non-conformité'),
            ('observation', 'Observation'),
            ('opportunite_amelioration', 'Opportunité d\'amélioration')
        ],
        validators=[DataRequired()]
    )
    gravite_defaut = SelectField(
        'Gravité par défaut',
        choices=[
            ('mineure', 'Mineure'),
            ('moyenne', 'Moyenne'),
            ('majeure', 'Majeure'),
            ('critique', 'Critique')
        ],
        default='moyenne'
    )
    processus_concerne = StringField('Processus concerné')
    cause_racine_typique = TextAreaField('Cause racine typique')
    recommandation_standard = TextAreaField('Recommandation standard')
    est_actif = BooleanField('Actif', default=True)
    submit = SubmitField('Créer le template')


# ============================================================================
# FORMULAIRES EXISTANTS (POUR COMPATIBILITÉ)
# ============================================================================

class EtapePlanActionForm(FlaskForm):
    """Formulaire pour les étapes de plan d'action (version simple)"""
    description = TextAreaField('Description de l\'étape', validators=[DataRequired()])
    date_echeance = DateField('Date d\'échéance', format='%Y-%m-%d', validators=[Optional(), validate_date_echeance])
    responsable_id = SelectField(
        'Responsable', 
        coerce=coerce_int_or_none, 
        validators=[Optional()]
    )
    submit = SubmitField('Ajouter l\'étape')


class ActionConformiteForm(FlaskForm):
    description = TextAreaField('Description', validators=[DataRequired()])
    responsable_id = SelectField(
        'Responsable', 
        coerce=coerce_int_or_none, 
        validators=[DataRequired()]
    )
    date_echeance = DateField("Date d'échéance", validators=[DataRequired(), validate_date_echeance])
    statut = SelectField('Statut', choices=[
        ('a_faire', 'À faire'),
        ('en_cours', 'En cours'),
        ('termine', 'Terminé'),
        ('retarde', 'Retardé')
    ])
    commentaire = TextAreaField('Commentaire')
    submit = SubmitField('Ajouter l\'action')


# ============================================================================
# FORMULAIRES SIMPLIFIÉS POUR LES ROUTES EXISTANTES
# ============================================================================

class SimpleAuditForm(FlaskForm):
    """Formulaire simple pour créer un audit (compatible)"""
    titre = StringField("Titre de l'audit", validators=[DataRequired()])
    description = TextAreaField("Description")
    type_audit = SelectField(
        "Type d'audit",
        choices=[
            ('', 'Sélectionnez un type'),
            ('interne', 'Interne'),
            ('externe', 'Externe'),
            ('qualite', 'Qualité'),
            ('conformite', 'Conformité'),
            ('securite', 'Sécurité'),
            ('financier', 'Financier'),
            ('operationnel', 'Opérationnel')
        ],
        validators=[DataRequired()]
    )
    processus_id = SelectField(
        "Processus audité", 
        coerce=coerce_int_or_none, 
        validators=[Optional()]
    )
    responsable_id = SelectField(
        "Responsable", 
        coerce=coerce_int_or_none, 
        validators=[Optional()]
    )
    date_debut_prevue = DateField(
        "Date de début prévue", 
        format='%Y-%m-%d', 
        validators=[Optional()]
    )
    date_fin_prevue = DateField(
        "Date de fin prévue", 
        format='%Y-%m-%d', 
        validators=[Optional()]
    )
    portee = TextAreaField("Portée de l'audit")
    objectifs = TextAreaField("Objectifs")
    criteres = TextAreaField("Critères")
    submit = SubmitField("Créer l'audit")


class SimpleRecommandationForm(FlaskForm):
    """Formulaire simple pour créer des recommandations (compatible)"""
    description = TextAreaField("Description", validators=[DataRequired()])
    type_recommandation = SelectField(
        "Type de recommandation",
        choices=[
            ('', 'Sélectionnez un type'),
            ('corrective', 'Corrective'),
            ('preventive', 'Préventive'),
            ('amelioration', 'Amélioration')
        ],
        validators=[DataRequired()]
    )
    delai_mise_en_oeuvre = SelectField(
        "Délai de mise en œuvre",
        choices=[
            ('', 'Sélectionnez un délai'),
            ('immediat', 'Immédiat'),
            ('court_terme', 'Court terme (1-3 mois)'),
            ('moyen_terme', 'Moyen terme (3-6 mois)'),
            ('long_terme', 'Long terme (>6 mois)')
        ]
    )
    date_echeance = DateField(
        "Date d'échéance", 
        format='%Y-%m-%d', 
        validators=[Optional(), validate_date_echeance]
    )
    constatation_id = SelectField(
        "Constatation associée", 
        coerce=coerce_int_or_none, 
        validators=[Optional()]
    )
    risque_id = SelectField(
        "Risque associé", 
        coerce=coerce_int_or_none, 
        validators=[Optional()]
    )
    responsable_id = SelectField(
        "Responsable", 
        coerce=coerce_int_or_none, 
        validators=[Optional()]
    )
    submit = SubmitField("Ajouter la recommandation")


class SimplePlanActionForm(FlaskForm):
    """Formulaire simple pour créer des plans d'action (compatible)"""
    nom = StringField('Nom du plan', validators=[DataRequired()])
    description = TextAreaField('Description')
    date_debut = DateField('Date de début', format='%Y-%m-%d', validators=[Optional()])
    date_fin_prevue = DateField('Date fin prévue', format='%Y-%m-%d', validators=[Optional(), validate_date_echeance])
    recommandation_id = SelectField(
        'Recommandation associée', 
        coerce=coerce_int_or_none, 
        validators=[Optional()]
    )
    risque_id = SelectField(
        'Risque associé', 
        coerce=coerce_int_or_none, 
        validators=[Optional()]
    )
    responsable_id = SelectField(
        'Responsable', 
        coerce=coerce_int_or_none, 
        validators=[Optional()]
    )
    submit = SubmitField('Créer le plan d\'action')


class SimpleConstatationForm(FlaskForm):
    """Formulaire simple pour créer des constatations (compatible)"""
    description = TextAreaField('Description', validators=[DataRequired()])
    type_constatation = SelectField('Type de constatation', choices=[
        ('', 'Sélectionnez un type'),
        ('conformite', 'Conformité'),
        ('non_conformite', 'Non-conformité'),
        ('observation', 'Observation'),
        ('recommandation', 'Recommandation')
    ], validators=[DataRequired()])
    gravite = SelectField('Gravité', choices=[
        ('mineure', 'Mineure'),
        ('moyenne', 'Moyenne'),
        ('majeure', 'Majeure'),
        ('critique', 'Critique')
    ], default='moyenne')
    processus_concerne = StringField('Processus concerné')
    cause_racine = TextAreaField('Cause racine', validators=[validate_cause_racine, Optional()])
    preuves = TextAreaField('Preuves/Justificatifs')
    risque_id = SelectField('Risque associé', coerce=coerce_int_or_none, validators=[Optional()])
    submit = SubmitField('Ajouter la constatation')

class ArchiveRisqueForm(FlaskForm):
    reason = TextAreaField('Motif de l\'archivage', validators=[DataRequired()])
    submit = SubmitField('Archiver le risque')

class SousEtapeForm(FlaskForm):
    nom = StringField('Nom de la sous-étape', validators=[DataRequired()])
    description = TextAreaField('Description')
    ordre = IntegerField('Ordre', validators=[DataRequired(), NumberRange(min=1)])
    responsable_id = SelectField('Responsable', coerce=coerce_int_or_none, validators=[Optional()])
    duree_estimee = StringField('Durée estimée')
    inputs = StringField('Inputs')
    outputs = StringField('Outputs')
    submit = SubmitField('Enregistrer')

class ZoneRisqueForm(FlaskForm):
    nom = StringField('Nom de la zone de risque', validators=[DataRequired()])
    description = TextAreaField('Description du risque')
    type_risque = SelectField('Type de risque', choices=[
        ('', 'Sélectionnez un type'),
        ('transition', 'Risque de Transition'),
        ('validation', 'Risque de Validation'),
        ('communication', 'Risque de Communication'),
        ('delai', 'Risque de Délai'),
        ('qualite', 'Risque de Qualité'),
        ('conformite', 'Risque de Conformité'),
        ('autre', 'Autre Risque')
    ], validators=[DataRequired()])
    niveau_risque = SelectField('Niveau de risque', choices=[
        ('', 'Sélectionnez un niveau'),
        ('faible', 'Faible'),
        ('moyen', 'Moyen'),
        ('eleve', 'Élevé'),
        ('critique', 'Critique')
    ], validators=[DataRequired()])
    impact = TextAreaField('Impact potentiel')
    mesures_controle = TextAreaField('Mesures de contrôle')
    etape_source_id = SelectField('Étape source', coerce=coerce_int_or_none, validators=[DataRequired()])
    etape_cible_id = SelectField('Étape cible', coerce=coerce_int_or_none, validators=[DataRequired()])
    responsable_id = SelectField('Responsable', coerce=coerce_int_or_none, validators=[Optional()])
    submit = SubmitField('Ajouter la zone de risque')

class ControleForm(FlaskForm):
    nom = StringField('Nom du contrôle', validators=[DataRequired()])
    description = TextAreaField('Description')
    type_controle = SelectField('Type de contrôle', choices=[
        ('', 'Sélectionnez un type'),
        ('preventif', 'Contrôle Préventif'),
        ('detectif', 'Contrôle Détectif'),
        ('correctif', 'Contrôle Correctif')
    ], validators=[DataRequired()])
    frequence = SelectField('Fréquence', choices=[
        ('', 'Sélectionnez une fréquence'),
        ('continu', 'Continu'),
        ('quotidien', 'Quotidien'),
        ('hebdomadaire', 'Hebdomadaire'),
        ('mensuel', 'Mensuel'),
        ('trimestriel', 'Trimestriel'),
        ('annuel', 'Annuel'),
        ('ponctuel', 'Ponctuel')
    ])
    etape_id = SelectField('Étape associée', coerce=coerce_int_or_none, validators=[Optional()])
    responsable_id = SelectField('Responsable', coerce=coerce_int_or_none, validators=[Optional()])
    statut = SelectField('Statut', choices=[
        ('actif', 'Actif'),
        ('inactif', 'Inactif'),
        ('en_revision', 'En révision')
    ])
    submit = SubmitField('Ajouter le contrôle')

class EtapeProcessusForm(FlaskForm):
    """Formulaire pour la création et modification d'étapes de processus"""
    nom = StringField('Nom de l\'étape', validators=[DataRequired()])
    description = TextAreaField('Description', validators=[Optional()])
    type_etape = SelectField('Type d\'étape', 
                           choices=[
                               ('action', 'Action'),
                               ('decision', 'Décision'),
                               ('debut', 'Début'),
                               ('fin', 'Fin'),
                               ('risque', 'Risque'),
                               ('controle', 'Contrôle')
                           ],
                           default='action')
    responsable_id = SelectField('Responsable', coerce=int, validators=[Optional()])
    duree_estimee = StringField('Durée estimée', validators=[Optional()])
    inputs = TextAreaField('Inputs', validators=[Optional()])
    outputs = TextAreaField('Outputs', validators=[Optional()])
    position_x = IntegerField('Position X', default=0, validators=[Optional()])
    position_y = IntegerField('Position Y', default=0, validators=[Optional()])
    couleur = StringField('Couleur', default='#007bff', validators=[Optional()])

# ============================================================================
# FORMULAIRES POUR LE MODULE AUDIT
# ============================================================================

class ConfigurationAuditForm(FlaskForm):
    nom_config = StringField('Nom de la configuration', validators=[DataRequired()])
    type_audit = SelectField('Type d\'audit', choices=[
        ('', 'Sélectionnez un type'),
        ('interne', 'Interne'),
        ('externe', 'Externe'), 
        ('qualite', 'Qualité'),
        ('conformite', 'Conformité'),
        ('securite', 'Sécurité'),
        ('financier', 'Financier'),
        ('operationnel', 'Opérationnel')
    ], validators=[DataRequired()])
    duree_standard = IntegerField('Durée standard (jours)', default=30)
    seuil_gravite_min = IntegerField('Seuil de gravité minimum', default=3)
    seuil_gravite_max = IntegerField('Seuil de gravité maximum', default=5)
    submit = SubmitField('Enregistrer')

class TemplateConstatationForm(FlaskForm):
    reference = StringField('Référence', validators=[DataRequired()])
    titre = StringField('Titre', validators=[DataRequired()])
    description = TextAreaField('Description')
    type_constatation = SelectField('Type de constatation', choices=[
        ('', 'Sélectionnez un type'),
        ('conformite', 'Conformité'),
        ('non_conformite', 'Non-conformité'),
        ('observation', 'Observation'),
        ('recommandation', 'Recommandation'),
        ('amelioration', 'Amélioration')
    ], validators=[DataRequired()])
    gravite_defaut = SelectField('Gravité par défaut', choices=[
        ('mineure', 'Mineure'),
        ('moyenne', 'Moyenne'),
        ('majeure', 'Majeure'), 
        ('critique', 'Critique')
    ], default='moyenne')
    processus_concerne = StringField('Processus concerné')
    cause_racine_typique = TextAreaField('Cause racine typique')
    recommandation_standard = TextAreaField('Recommandation standard')
    submit = SubmitField('Créer le template')

# Ajoutez à la fin de votre forms.py


class LogigrammeForm(FlaskForm):
    """Formulaire pour créer/modifier un logigramme"""
    nom = StringField(
        "Nom du processus",
        validators=[DataRequired(), Length(min=3, max=200)],
        description="Nom du processus à représenter"
    )
    
    description = TextAreaField(
        "Description du processus",
        validators=[Optional(), Length(max=2000)],
        description="Décrivez les objectifs et les étapes clés du processus"
    )
    
    direction_id = SelectField(
        "Direction associée",
        coerce=coerce_int_or_none,
        choices=[],  # ← Laisser vide, sera rempli dans la vue
        validators=[Optional()]
    )
    
    service_id = SelectField(
        "Service associé",
        coerce=coerce_int_or_none,
        choices=[],  # ← Laisser vide, sera rempli dans la vue
        validators=[Optional()]
    )
    
    version = StringField(
        "Version",
        default="1.0",
        validators=[Optional(), Length(max=20)]
    )
    
    est_actif = BooleanField(
        "Processus actif",
        default=True
    )
    
    submit = SubmitField("Enregistrer le processus")


class ElementLogigrammeForm(FlaskForm):
    """Formulaire pour ajouter/modifier un élément dans un logigramme"""
    type_element = SelectField(
        "Type d'élément",
        choices=[
            ('debut', 'Début'),
            ('action', 'Action'),
            ('controle', 'Contrôle'),
            ('decision', 'Décision'),
            ('risque', 'Risque'),
            ('document', 'Document'),
            ('fin', 'Fin')
        ],
        validators=[DataRequired()]
    )
    
    libelle = StringField(
        "Libellé",
        validators=[DataRequired(), Length(min=2, max=500)]
    )
    
    description = TextAreaField(
        "Description",
        validators=[Optional(), Length(max=2000)]
    )
    
    responsable_id = SelectField(
        "Responsable",
        coerce=coerce_int_or_none,
        choices=[],  # ← Laisser vide, sera rempli dans la vue
        validators=[Optional()]
    )
    
    # Coordonnées
    position_x = IntegerField(
        "Position X",
        default=0,
        validators=[Optional()]
    )
    
    position_y = IntegerField(
        "Position Y",
        default=0,
        validators=[Optional()]
    )
    
    # Style
    couleur = StringField(
        "Couleur",
        default="#3498db",
        validators=[Optional(), Length(max=20)]
    )
    
    # Pour les éléments de risque
    risque_id = SelectField(
        "Risque associé",
        coerce=coerce_int_or_none,
        choices=[],  # ← Laisser vide, sera rempli dans la vue
        validators=[Optional()]
    )
    
    # Pour les éléments de contrôle
    controle_id = SelectField(
        "Contrôle associé",
        coerce=coerce_int_or_none,
        choices=[],  # ← Laisser vide, sera rempli dans la vue
        validators=[Optional()]
    )
    
    submit = SubmitField("Enregistrer l'élément")


class LienLogigrammeForm(FlaskForm):
    """Formulaire pour créer/modifier un lien dans un logigramme"""
    element_source_id = SelectField(
        "Élément source",
        coerce=int,
        choices=[],  # ← Laisser vide, sera rempli dans la vue
        validators=[DataRequired()]
    )
    
    element_cible_id = SelectField(
        "Élément cible",
        coerce=int,
        choices=[],  # ← Laisser vide, sera rempli dans la vue
        validators=[DataRequired()]
    )
    
    libelle = StringField(
        "Libellé du lien",
        validators=[Optional(), Length(max=200)]
    )
    
    condition = TextAreaField(
        "Condition",
        validators=[Optional(), Length(max=500)],
        description="Condition pour suivre ce chemin (ex: Si approuvé, Si rejeté)"
    )
    
    # Style
    type_ligne = SelectField(
        "Type de ligne",
        choices=[
            ('simple', 'Simple'),
            ('fleche', 'Flèche'),
            ('pointille', 'Pointillé')
        ],
        default='fleche'
    )
    
    couleur = StringField(
        "Couleur",
        default="#95a5a6",
        validators=[Optional(), Length(max=20)]
    )
    
    submit = SubmitField("Enregistrer le lien")



class ConfigurationChampForm(FlaskForm):
    nom_technique = StringField('Nom technique', validators=[DataRequired(), Length(max=100)])
    nom_affichage = StringField('Nom d\'affichage', validators=[DataRequired(), Length(max=200)])
    type_champ = SelectField('Type de champ', choices=[
        ('texte', 'Texte court'),
        ('textarea', 'Texte long'),
        ('select', 'Liste déroulante'),
        ('multiselect', 'Liste multiple'),
        ('checkbox', 'Case à cocher'),
        ('radio', 'Boutons radio'),
        ('date', 'Date'),
        ('fichier', 'Fichier'),
        ('nombre', 'Nombre')
    ], validators=[DataRequired()])
    est_obligatoire = BooleanField('Champ obligatoire')
    est_actif = BooleanField('Actif', default=True)
    est_recherchable = BooleanField('Recherchable', default=False)  # Ajoutez cette ligne
    ordre_affichage = IntegerField('Ordre d\'affichage', default=0)
    section = SelectField('Section', choices=[
        ('general', 'Informations générales'),
        ('analyse', 'Analyse du risque'),
        ('evaluation', 'Évaluation'),
        ('documentation', 'Documentation'),
        ('personnalise', 'Personnalisé')
    ])
    aide_texte = TextAreaField('Texte d\'aide')
    valeurs_possibles = TextAreaField('Valeurs possibles (une par ligne)')
    regex_validation = StringField('Expression régulière de validation')
    submit = SubmitField('Enregistrer')

class ConfigurationListeForm(FlaskForm):
    nom_technique = StringField('Nom technique', validators=[DataRequired(), Length(max=100)])
    nom_affichage = StringField('Nom d\'affichage', validators=[DataRequired(), Length(max=200)])
    est_multiple = BooleanField('Sélection multiple')
    valeurs = TextAreaField('Valeurs (format: valeur|libellé)', validators=[DataRequired()])
    valeurs_par_defaut = TextAreaField('Valeurs par défaut (une par ligne)')
    est_actif = BooleanField('Actif', default=True)
    submit = SubmitField('Enregistrer')


class ChampPersonnaliseForm(FlaskForm):
    """Formulaire dynamique généré à partir de la configuration"""
    def __init__(self, *args, **kwargs):
        super(ChampPersonnaliseForm, self).__init__(*args, **kwargs)
        
    # Les champs seront ajoutés dynamiquement


class UploadFichierForm(FlaskForm):
    fichier = FileField('Fichier', validators=[DataRequired()])
    categorie = SelectField('Catégorie', choices=[
        ('document', 'Document'),
        ('image', 'Image'),
        ('analyse', 'Analyse'),
        ('autre', 'Autre')
    ])
    description = TextAreaField('Description')
    submit = SubmitField('Téléverser')


# ========================
# FORMULAIRES QUESTIONNAIRE
# ========================

class QuestionnaireForm(FlaskForm):
    titre = StringField('Titre du questionnaire', validators=[DataRequired()])
    description = TextAreaField('Description')
    code = StringField('Code unique', validators=[DataRequired()])
    instructions = TextAreaField('Instructions pour les répondants')
    est_actif = BooleanField('Actif')
    est_public = BooleanField('Public (accessible sans connexion)')
    
    # CORRECTION ICI : Changer le format pour accepter le format HTML5
    date_debut = DateTimeField('Date de début', format='%Y-%m-%dT%H:%M', validators=[Optional()])
    date_fin = DateTimeField('Date de fin', format='%Y-%m-%dT%H:%M', validators=[Optional()])
    
    temps_estime = IntegerField('Temps estimé (minutes)', validators=[Optional(), NumberRange(min=1)])
    redirection_url = StringField('URL de redirection après soumission', validators=[Optional(), URL()])
    
    # Configuration avancée
    autoriser_sauvegarde_partielle = BooleanField('Autoriser sauvegarde partielle', default=True)
    afficher_barre_progression = BooleanField('Afficher barre de progression', default=True)
    afficher_numero_questions = BooleanField('Afficher numéros questions', default=True)
    randomiser_questions = BooleanField('Randomiser ordre des questions')
    randomiser_options = BooleanField('Randomiser ordre des options')
    limit_une_reponse = BooleanField('Limiter à une réponse par personne')
    collecter_email = BooleanField('Collecter email du répondant')
    collecter_nom = BooleanField('Collecter nom du répondant')
    notification_email = BooleanField('Notifications par email')
    email_notification = StringField('Email pour notifications', validators=[Optional(), Email()])
    confirmation_message = TextAreaField('Message de confirmation')
    
    submit = SubmitField('Enregistrer')


class CategorieQuestionnaireForm(FlaskForm):
    titre = StringField('Titre de la catégorie', validators=[DataRequired()])
    description = TextAreaField('Description')
    ordre = IntegerField('Ordre', default=0, validators=[Optional(), NumberRange(min=0)])
    submit = SubmitField('Enregistrer')


class QuestionForm(FlaskForm):
    texte = TextAreaField('Question', validators=[DataRequired()], render_kw={"rows": 3})
    description = TextAreaField('Description')
    type = SelectField('Type de question', choices=[
        ('text', 'Texte court'),
        ('textarea', 'Texte long'),
        ('radio', 'Choix unique'),
        ('checkbox', 'Choix multiple'),
        ('select', 'Liste déroulante'),
        ('date', 'Date'),
        ('email', 'Email'),
        ('number', 'Nombre'),
        ('range', 'Échelle'),
        ('matrix', 'Matrice'),
        ('file', 'Fichier'),
        ('rating', 'Évaluation'),
        ('yesno', 'Oui/Non')
    ], validators=[DataRequired()])
    ordre = IntegerField('Ordre', default=0, validators=[Optional(), NumberRange(min=0)])
    est_obligatoire = BooleanField('Obligatoire')
    placeholder = StringField('Placeholder')
    taille_min = IntegerField('Taille minimale', validators=[Optional(), NumberRange(min=1)])
    taille_max = IntegerField('Taille maximale', validators=[Optional(), NumberRange(min=1)])
    valeurs_min = FloatField('Valeur minimale', validators=[Optional()])
    valeurs_max = FloatField('Valeur maximale', validators=[Optional()])
    pas = FloatField('Pas', validators=[Optional(), NumberRange(min=0.01)])
    unite = StringField('Unité')
    echelle_min = IntegerField('Échelle min', default=1, validators=[Optional(), NumberRange(min=1)])
    echelle_max = IntegerField('Échelle max', default=5, validators=[Optional(), NumberRange(min=1)])
    libelle_min = StringField('Libellé min')
    libelle_max = StringField('Libellé max')
    submit = SubmitField('Enregistrer')


class OptionQuestionForm(FlaskForm):
    valeur = StringField('Valeur', validators=[DataRequired()])
    texte = StringField('Texte affiché', validators=[DataRequired()])
    ordre = IntegerField('Ordre', default=0, validators=[Optional(), NumberRange(min=0)])
    score = FloatField('Score (si applicable)', validators=[Optional()])
    est_autre = BooleanField('Option "Autre"')
    submit = SubmitField('Ajouter')


class ConditionQuestionForm(FlaskForm):
    question_parent_id = SelectField('Question parente', coerce=int, validators=[DataRequired()])
    operateur = SelectField('Opérateur', choices=[
        ('equals', 'Égal à'),
        ('not_equals', 'Différent de'),
        ('contains', 'Contient'),
        ('not_contains', 'Ne contient pas'),
        ('greater_than', 'Supérieur à'),
        ('less_than', 'Inférieur à'),
        ('greater_equal', 'Supérieur ou égal à'),
        ('less_equal', 'Inférieur ou égal à')
    ], validators=[DataRequired()])
    valeur = StringField('Valeur', validators=[DataRequired()])
    submit = SubmitField('Ajouter condition')


class ImportQuestionnaireForm(FlaskForm):
    fichier = FileField('Fichier JSON', validators=[FileRequired()])
    importer_categories = BooleanField('Importer catégories', default=True)
    importer_questions = BooleanField('Importer questions', default=True)
    importer_options = BooleanField('Importer options', default=True)
    submit = SubmitField('Importer')


class ExportQuestionnaireForm(FlaskForm):
    format = SelectField('Format', choices=[
        ('json', 'JSON (Structure complète)'),
        ('csv_reponses', 'CSV (Réponses)'),
        ('excel_reponses', 'Excel (Réponses)'),
        ('pdf', 'PDF (Rapport)')
    ], validators=[DataRequired()])
    date_debut = DateField('Date début', validators=[Optional()])
    date_fin = DateField('Date fin', validators=[Optional()])
    inclure_questions = BooleanField('Inclure questions', default=True)
    inclure_reponses = BooleanField('Inclure réponses', default=True)
    submit = SubmitField('Exporter')

class AnalyseIAForm(FlaskForm):
    """Formulaire pour configurer l'analyse IA"""
    type_analyse = SelectField(
        "Type d'analyse",
        choices=[
            ('recommandations', 'Génération de recommandations'),
            ('causes_racines', 'Analyse des causes racines'),
            ('risques_potentiels', 'Identification des risques potentiels'),
            ('complet', 'Analyse complète')
        ],
        default='complet',
        validators=[DataRequired()]
    )
    
    portee_analyse = SelectField(
        "Portée de l'analyse",
        choices=[
            ('constatations', 'Uniquement les constatations'),
            ('recommandations', 'Recommandations existantes'),
            ('processus', 'Analyse du processus audité'),
            ('complet', 'Analyse complète de l\'audit')
        ],
        default='constatations'
    )
    
    niveau_detail = SelectField(
        "Niveau de détail",
        choices=[
            ('sommaire', 'Sommaire (rapide)'),
            ('standard', 'Standard'),
            ('detaillée', 'Détaillée (plus long)')
        ],
        default='standard'
    )
    
    inclure_exemples = BooleanField("Inclure des exemples concrets", default=True)
    generer_actions = BooleanField("Générer des actions immédiates", default=True)
    
    submit = SubmitField("Lancer l'analyse IA")



class UploadFichierRapportForm(FlaskForm):
    """Formulaire pour uploader un fichier de rapport"""
    fichier = FileField('Fichier', validators=[
        DataRequired(message="Sélectionnez un fichier"),
        FileAllowed(['pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'jpg', 'jpeg', 'png', 'txt', 'zip', 'rar'], 
                   'Types autorisés: PDF, Word, Excel, PowerPoint, images, texte, archives')
    ])
    description = TextAreaField('Description', validators=[
        Optional(),
        Length(max=500, message="Description trop longue (max 500 caractères)")
    ])
    submit = SubmitField('Uploader le fichier')
    
class CommentaireSousActionForm(FlaskForm):
    contenu = TextAreaField('Commentaire', validators=[DataRequired()], 
                           render_kw={"rows": 4, "placeholder": "Ajouter un commentaire, une note ou une mise à jour..."})
    type_contenu = SelectField('Type', choices=[
        ('commentaire', 'Commentaire général'),
        ('note', 'Note importante'),
        ('mise_a_jour', 'Mise à jour de progression'),
        ('question', 'Question'),
        ('blocage', 'Signalement de blocage'),
        ('reussite', 'Succès accompli')
    ], default='commentaire')
    est_prive = BooleanField('Commentaire privé (visible seulement pour les administrateurs et le responsable)')
    tags = StringField('Tags (séparés par des virgules)', 
                      render_kw={"placeholder": "important, question, blocage..."})
    fichiers = MultipleFileField('Fichiers joints')
    submit = SubmitField('Publier')


# ==================== FORMULAIRES ====================

class ProgrammeAuditForm(FlaskForm):
    """Formulaire pour créer/modifier un programme d'audit"""
    
    nom = StringField('Nom du programme', validators=[DataRequired()])
    description = TextAreaField('Description')
    periode = SelectField('Période', choices=[
        ('annuel', 'Annuel'),
        ('triennal', 'Triennal (3 ans)')
    ], validators=[DataRequired()])
    annee_debut = SelectField('Année de début', validators=[DataRequired()])
    annee_fin = SelectField('Année de fin', validators=[DataRequired()])
    
    # Méthode de génération
    methode_generation = SelectField('Méthode de génération', choices=[
        ('manuel', 'Manuel - Je créerai les missions moi-même'),
        ('auto_risques', 'Automatique - Basé sur la cartographie des risques'),
        ('hybride', 'Hybride - Automatique avec ajustements manuels')
    ], validators=[DataRequired()])
    
    # Critères pour génération automatisée
    seuil_critique = BooleanField('Inclure les risques Critiques', default=True)
    seuil_eleve = BooleanField('Inclure les risques Élevés', default=True)
    inclure_risques_moyens = BooleanField('Inclure les risques Moyens', default=False)
    frequence_audit_risque = SelectField('Fréquence d\'audit par niveau', choices=[
        ('annuelle_critique', 'Annuelle pour risques critiques'),
        ('semestrielle_critique', 'Semestrielle pour risques critiques'),
        ('triennal_tous', 'Tous les 3 ans pour tous les risques')
    ])
    prioriser_processus_critiques = BooleanField('Prioriser les processus critiques', default=True)
    
    # Configuration
    frequence_audit = SelectField('Fréquence générale d\'audit', choices=[
        ('annuelle', 'Annuelle'),
        ('semestrielle', 'Semestrielle'),
        ('trimestrielle', 'Trimestrielle')
    ])
    duree_moyenne_mission = IntegerField('Durée moyenne d\'une mission (jours)', 
                                         default=5, validators=[NumberRange(min=1, max=30)])
    ressources_disponibles = IntegerField('Ressources disponibles (jours/homme par an)', 
                                         default=100, validators=[NumberRange(min=10, max=1000)])
    
    submit = SubmitField('Créer le programme')


class MissionAuditForm(FlaskForm):
    """Formulaire pour créer/modifier une mission d'audit"""
    
    titre = StringField('Titre de la mission', validators=[DataRequired()])
    description = TextAreaField('Description')
    
    # Lien avec risque
    risque_id = SelectField('Risque associé', coerce=int, choices=[])
    priorite = SelectField('Priorité', choices=[
        ('critique', 'Critique'),
        ('elevee', 'Élevée'),
        ('moyenne', 'Moyenne'),
        ('faible', 'Faible')
    ])
    
    # Planification
    annee_prevue = SelectField('Année prévue', choices=[], validators=[DataRequired()])
    trimestre_prevue = SelectField('Trimestre prévu', choices=[
        (1, '1er trimestre'),
        (2, '2ème trimestre'),
        (3, '3ème trimestre'),
        (4, '4ème trimestre')
    ])
    date_debut_prevue = DateField('Date de début prévue', format='%Y-%m-%d')
    date_fin_prevue = DateField('Date de fin prévue', format='%Y-%m-%d')
    duree_estimee = IntegerField('Durée estimée (jours)', validators=[NumberRange(min=1, max=60)])
    
    # Ressources
    responsable_id = SelectField('Responsable', coerce=int, choices=[])
    equipe_ids = SelectMultipleField('Équipe d\'audit', coerce=int, choices=[])
    
    submit = SubmitField('Enregistrer')


class PlanPluieForm(FlaskForm):
    """Formulaire pour créer un plan de repli"""
    
    nom = StringField('Nom du plan de repli', validators=[DataRequired()])
    description = TextAreaField('Description')
    
    mission_principale_id = SelectField('Mission principale', coerce=int, choices=[], validators=[DataRequired()])
    mission_remplacement_id = SelectField('Mission de remplacement', coerce=int, choices=[], validators=[DataRequired()])
    
    condition_type = SelectField('Condition de déclenchement', choices=[
        ('retard', 'Retard de plus de X jours'),
        ('indisponibilite', 'Indisponibilité des ressources'),
        ('urgence', 'Situation d\'urgence')
    ])
    condition_seuil = IntegerField('Seuil (jours)', default=15)
    condition_description = TextAreaField('Description de la condition')
    
    submit = SubmitField('Créer le plan de repli')

# ==================== FORMULAIRES ====================

class ProgrammeAuditForm(FlaskForm):
    """Formulaire pour créer/modifier un programme d'audit"""
    
    nom = StringField('Nom du programme', validators=[DataRequired()])
    description = TextAreaField('Description')
    periode = SelectField('Période', choices=[
        ('annuel', 'Annuel'),
        ('triennal', 'Triennal (3 ans)')
    ], validators=[DataRequired()])
    annee_debut = SelectField('Année de début', validators=[DataRequired()])
    annee_fin = SelectField('Année de fin', validators=[DataRequired()])
    
    # Méthode de génération
    methode_generation = SelectField('Méthode de génération', choices=[
        ('manuel', 'Manuel - Je créerai les missions moi-même'),
        ('auto_risques', 'Automatique - Basé sur la cartographie des risques'),
        ('hybride', 'Hybride - Automatique avec ajustements manuels')
    ], validators=[DataRequired()])
    
    # Critères pour génération automatisée
    seuil_critique = BooleanField('Inclure les risques Critiques', default=True)
    seuil_eleve = BooleanField('Inclure les risques Élevés', default=True)
    inclure_risques_moyens = BooleanField('Inclure les risques Moyens', default=False)
    frequence_audit_risque = SelectField('Fréquence d\'audit par niveau', choices=[
        ('annuelle_critique', 'Annuelle pour risques critiques'),
        ('semestrielle_critique', 'Semestrielle pour risques critiques'),
        ('triennal_tous', 'Tous les 3 ans pour tous les risques')
    ])
    prioriser_processus_critiques = BooleanField('Prioriser les processus critiques', default=True)
    
    # Configuration
    frequence_audit = SelectField('Fréquence générale d\'audit', choices=[
        ('annuelle', 'Annuelle'),
        ('semestrielle', 'Semestrielle'),
        ('trimestrielle', 'Trimestrielle')
    ])
    duree_moyenne_mission = IntegerField('Durée moyenne d\'une mission (jours)', 
                                         default=5, validators=[NumberRange(min=1, max=30)])
    ressources_disponibles = IntegerField('Ressources disponibles (jours/homme par an)', 
                                         default=100, validators=[NumberRange(min=10, max=1000)])
    
    submit = SubmitField('Créer le programme')


class MissionAuditForm(FlaskForm):
    """Formulaire pour créer/modifier une mission d'audit"""
    
    titre = StringField('Titre de la mission', validators=[DataRequired()])
    description = TextAreaField('Description')
    
    # Lien avec risque
    risque_id = SelectField('Risque associé', coerce=int, choices=[])
    priorite = SelectField('Priorité', choices=[
        ('critique', 'Critique'),
        ('elevee', 'Élevée'),
        ('moyenne', 'Moyenne'),
        ('faible', 'Faible')
    ])
    
    # Planification
    annee_prevue = SelectField('Année prévue', choices=[], validators=[DataRequired()])
    trimestre_prevue = SelectField('Trimestre prévu', choices=[
        (1, '1er trimestre'),
        (2, '2ème trimestre'),
        (3, '3ème trimestre'),
        (4, '4ème trimestre')
    ])
    date_debut_prevue = DateField('Date de début prévue', format='%Y-%m-%d')
    date_fin_prevue = DateField('Date de fin prévue', format='%Y-%m-%d')
    duree_estimee = IntegerField('Durée estimée (jours)', validators=[NumberRange(min=1, max=60)])
    
    # Ressources
    responsable_id = SelectField('Responsable', coerce=int, choices=[])
    equipe_ids = SelectMultipleField('Équipe d\'audit', coerce=int, choices=[])
    
    submit = SubmitField('Enregistrer')


class PlanPluieForm(FlaskForm):
    """Formulaire pour créer un plan de repli"""
    
    nom = StringField('Nom du plan de repli', validators=[DataRequired()])
    description = TextAreaField('Description')
    
    mission_principale_id = SelectField('Mission principale', coerce=int, choices=[], validators=[DataRequired()])
    mission_remplacement_id = SelectField('Mission de remplacement', coerce=int, choices=[], validators=[DataRequired()])
    
    condition_type = SelectField('Condition de déclenchement', choices=[
        ('retard', 'Retard de plus de X jours'),
        ('indisponibilite', 'Indisponibilité des ressources'),
        ('urgence', 'Situation d\'urgence')
    ])
    condition_seuil = IntegerField('Seuil (jours)', default=15)
    condition_description = TextAreaField('Description de la condition')
    
    submit = SubmitField('Créer le plan de repli')
