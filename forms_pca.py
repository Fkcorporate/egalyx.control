# forms_pca.py
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed
from wtforms import StringField, TextAreaField, SelectField, DateField, DateTimeField, IntegerField, BooleanField, SubmitField, FieldList, FormField, FileField
from wtforms.validators import DataRequired, Length, Optional, NumberRange
from datetime import datetime, timedelta


class PlanContinuiteActiviteForm(FlaskForm):
    """Formulaire PCA complet"""
    
    # Identification
    reference = StringField('Référence', validators=[DataRequired(), Length(max=50)])
    titre = StringField('Titre du plan', validators=[DataRequired(), Length(max=200)])
    description = TextAreaField('Description', validators=[Optional()])
    version = StringField('Version', validators=[Optional(), Length(max=20)], default='1.0')
    
    # Périmètre
    type_organisation = SelectField('Type d\'organisation', choices=[
        ('pole', 'Pôle'),
        ('direction', 'Direction'),
        ('service', 'Service')
    ], default='direction')
    pole_id = SelectField('Pôle', coerce=int, choices=[], validators=[Optional()])
    direction_id = SelectField('Direction', coerce=int, choices=[], validators=[Optional()])
    service_id = SelectField('Service', coerce=int, choices=[], validators=[Optional()])
    processus_critiques = TextAreaField('Processus critiques (un par ligne)', validators=[Optional()])
    
    # Dates
    date_validite = DateField('Date de fin de validité', validators=[Optional()])
    date_dernier_test = DateField('Date du dernier test', validators=[Optional()])
    date_prochain_test = DateField('Date du prochain test', validators=[Optional()])
    
    # Acteurs
    responsable_id = SelectField('Responsable PCA', coerce=int, choices=[], validators=[Optional()])
    redacteur_id = SelectField('Rédacteur', coerce=int, choices=[], validators=[Optional()])
    valideur_id = SelectField('Valideur', coerce=int, choices=[], validators=[Optional()])
    
    # BIA
    bia_realisee = BooleanField('BIA réalisée', default=False)
    bia_date = DateField('Date de la BIA', validators=[Optional()])
    delai_arret_max = StringField('Délai d\'arrêt maximal (RTO)', validators=[Optional(), Length(max=50)])
    perte_donnees_max = StringField('Perte de données maximale (RPO)', validators=[Optional(), Length(max=50)])
    
    # Stratégies
    strategies = TextAreaField('Stratégies de continuité (une par ligne)', validators=[Optional()])
    sites_secours = TextAreaField('Sites de secours (une par ligne)', validators=[Optional()])
    
    # Procédures
    procedures_urgence = TextAreaField('Procédures d\'urgence', validators=[Optional()])
    procedures_reprise = TextAreaField('Procédures de reprise', validators=[Optional()])
    procedures_retour_normal = TextAreaField('Procédures de retour à la normale', validators=[Optional()])
    
    # Ressources
    ressources_critiques = TextAreaField('Ressources critiques (une par ligne)', validators=[Optional()])
    duree_critique = StringField('Durée critique de reprise', validators=[Optional(), Length(max=50)])
    
    # Statut
    statut = SelectField('Statut', choices=[
        ('en_redaction', 'En rédaction'),
        ('en_relecture', 'En relecture'),
        ('valide', 'Validé'),
        ('obsolète', 'Obsolète')
    ], default='en_redaction')
    niveau_maturite = SelectField('Niveau de maturité', choices=[
        (1, '1 - Initial'),
        (2, '2 - Répétable'),
        (3, '3 - Défini'),
        (4, '4 - Géré'),
        (5, '5 - Optimisé')
    ], default=1, coerce=int)
    
    submit = SubmitField('Enregistrer')


class ActionPCAForm(FlaskForm):
    """Formulaire pour les actions PCA"""
    reference = StringField('Référence', validators=[DataRequired(), Length(max=50)])
    intitule = StringField('Intitulé', validators=[DataRequired(), Length(max=200)])
    description = TextAreaField('Description', validators=[Optional()])
    
    phase = SelectField('Phase', choices=[
        ('preparation', 'Préparation'),
        ('crise', 'Gestion de crise'),
        ('reprise', 'Reprise d\'activité'),
        ('retour', 'Retour à la normale')
    ], default='preparation')
    
    priorite = SelectField('Priorité', choices=[
        ('haute', 'Haute'),
        ('moyenne', 'Moyenne'),
        ('basse', 'Basse')
    ], default='moyenne')
    
    delai_execution = StringField('Délai d\'exécution', validators=[Optional(), Length(max=50)])
    
    responsable_id = SelectField('Responsable', coerce=int, choices=[], validators=[Optional()])
    
    date_debut = DateField('Date de début', validators=[Optional()])
    date_fin_prevue = DateField('Date de fin prévue', validators=[Optional()])
    
    statut = SelectField('Statut', choices=[
        ('a_faire', 'À faire'),
        ('en_cours', 'En cours'),
        ('termine', 'Terminé'),
        ('bloque', 'Bloqué')
    ], default='a_faire')
    
    pourcentage_realisation = IntegerField('Avancement (%)', validators=[NumberRange(min=0, max=100)], default=0)
    commentaire = TextAreaField('Commentaire', validators=[Optional()])
    
    submit = SubmitField('Enregistrer')


class ExercicePCAForm(FlaskForm):
    """Formulaire pour les exercices PCA"""
    reference = StringField('Référence', validators=[DataRequired(), Length(max=50)])
    nom = StringField('Nom de l\'exercice', validators=[DataRequired(), Length(max=200)])
    description = TextAreaField('Description', validators=[Optional()])
    
    type_exercice = SelectField('Type d\'exercice', choices=[
        ('table_top', 'Tabletop (sur table)'),
        ('technique', 'Technique'),
        ('grandeur_nature', 'Grandeur nature')
    ], default='table_top')
    
    # CORRECTION ICI : Utiliser DateField au lieu de DateTimeField
    date_exercice = DateField('Date de l\'exercice', validators=[DataRequired()])
    duree = StringField('Durée (heures)', validators=[Optional(), Length(max=50)])
    
    scenario = TextAreaField('Scénario', validators=[Optional()])
    objectifs = TextAreaField('Objectifs (un par ligne)', validators=[Optional()])
    
    submit = SubmitField('Enregistrer')
