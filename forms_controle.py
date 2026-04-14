# forms_controle.py
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed
from wtforms import StringField, TextAreaField, SelectField, DateField, IntegerField, BooleanField, SubmitField, FloatField
from wtforms.validators import DataRequired, Length, Optional, NumberRange
from datetime import datetime, timedelta


class FichierCampagneForm(FlaskForm):
    """Formulaire pour l'upload de fichiers"""
    fichier = FileField('Fichier', validators=[
        FileRequired(message='Veuillez sélectionner un fichier'),
        FileAllowed(['pdf', 'doc', 'docx', 'xls', 'xlsx', 'jpg', 'jpeg', 'png', 'txt'], 
                   'Formats autorisés: PDF, Word, Excel, Images, TXT')
    ])
    categorie = SelectField('Catégorie', choices=[
        ('document', 'Document'),
        ('rapport', 'Rapport'),
        ('preuve', 'Preuve de contrôle'),
        ('autre', 'Autre')
    ], default='document')
    description = TextAreaField('Description', validators=[Optional(), Length(max=500)])
    submit = SubmitField('Uploader')


class CampagneControleForm(FlaskForm):
    """Formulaire complet pour une campagne de contrôle"""
    
    # Identification
    reference = StringField('Référence', validators=[DataRequired(), Length(max=50)])
    nom = StringField('Nom de la campagne', validators=[DataRequired(), Length(max=200)])
    description = TextAreaField('Description', validators=[Optional()])
    
    # Organisation
    type_organisation = SelectField('Type d\'organisation', choices=[
        ('pole', 'Pôle'),
        ('direction', 'Direction'),
        ('service', 'Service')
    ], default='direction')
    pole_id = SelectField('Pôle', coerce=int, choices=[], validators=[Optional()])
    direction_id = SelectField('Direction', coerce=int, choices=[], validators=[Optional()])
    service_id = SelectField('Service', coerce=int, choices=[], validators=[Optional()])
    
    # Dates
    date_debut = DateField('Date de début', validators=[DataRequired()], default=datetime.now().date)
    date_fin = DateField('Date de fin', validators=[DataRequired()], default=(datetime.now() + timedelta(days=30)).date)
    
    # Acteurs
    valideur_id = SelectField('Valideur', coerce=int, choices=[], validators=[Optional()])
    evaluateur_id = SelectField('Évaluateur', coerce=int, choices=[], validators=[Optional()])
    
    # Volumes prévisionnels
    volume_previsionnel = IntegerField('Volume prévisionnel total', validators=[Optional(), NumberRange(min=0)], default=0)
    nb_dossiers_prevus = IntegerField('Nombre de dossiers prévus', validators=[Optional(), NumberRange(min=0)], default=0)
    nb_dossiers_reglement = IntegerField('Nombre de dossiers règlement à contrôler', validators=[Optional(), NumberRange(min=0)], default=0)
    
    # Résultats
    nb_dossiers_controles = IntegerField('Nombre de dossiers contrôlés', validators=[Optional(), NumberRange(min=0)], default=0)
    nb_anomalies = IntegerField('Nombre de dossiers en anomalie', validators=[Optional(), NumberRange(min=0)], default=0)
    nb_conformes = IntegerField('Nombre de dossiers conformes', validators=[Optional(), NumberRange(min=0)], default=0)
    
    # Commentaires
    commentaire_general = TextAreaField('Commentaire général', validators=[Optional()])
    conclusion = TextAreaField('Conclusion', validators=[Optional()])
    actions_correctives = TextAreaField('Actions correctives proposées', validators=[Optional()])
    
    # Statut
    statut = SelectField('Statut', choices=[
        ('en_preparation', 'En préparation'),
        ('en_cours', 'En cours'),
        ('termine', 'Terminé'),
        ('suspendu', 'Suspendu'),
        ('annule', 'Annulé')
    ], default='en_preparation')
    
    submit = SubmitField('Enregistrer')
