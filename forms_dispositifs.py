# forms_dispositifs.py 

from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, DateField, IntegerField, FileField, HiddenField, SubmitField  # AJOUTEZ HiddenField
from wtforms.validators import DataRequired, Optional, Length, NumberRange
from flask_wtf.file import FileAllowed

class DispositifMaitriseForm(FlaskForm):
    """Formulaire pour créer/modifier un dispositif de maîtrise"""
    nom = StringField('Nom du dispositif', validators=[
        DataRequired(message='Le nom est obligatoire'),
        Length(max=300, message='Maximum 300 caractères')
    ])
    
    description = TextAreaField('Description', validators=[
        Optional(),
        Length(max=2000, message='Maximum 2000 caractères')
    ])
    
    type_dispositif = SelectField('Type de dispositif', choices=[
        ('', '-- Sélectionner --'),
        ('Préventif', 'Préventif'),
        ('Détectif', 'Détectif'),
        ('Correctif', 'Correctif'),
        ('Dirigeant', 'Dirigeant')
    ], validators=[DataRequired(message='Le type est obligatoire')])
    
    nature = SelectField('Nature', choices=[
        ('', '-- Sélectionner --'),
        ('Manuel', 'Manuel'),
        ('Automatique', 'Automatique'),
        ('Mixte', 'Mixte')
    ], validators=[DataRequired(message='La nature est obligatoire')])
    
    frequence = SelectField('Fréquence', choices=[
        ('', '-- Sélectionner --'),
        ('Permanent', 'Permanent'),
        ('Quotidien', 'Quotidien'),
        ('Hebdomadaire', 'Hebdomadaire'),
        ('Mensuel', 'Mensuel'),
        ('Trimestriel', 'Trimestriel'),
        ('Semestriel', 'Semestriel'),
        ('Annuel', 'Annuel'),
        ('Exceptionnel', 'Exceptionnel')
    ], validators=[DataRequired(message='La fréquence est obligatoire')])
    
    responsable_id = SelectField('Responsable', coerce=int)
    
    direction_id = SelectField('Direction', coerce=int)
    
    service_id = SelectField('Service', coerce=int)
    
    efficacite_attendue = SelectField('Efficacité attendue', choices=[
        (0, '-- Sélectionner --'),
        (1, '1 - Très faible'),
        (2, '2 - Faible'),
        (3, '3 - Moyenne'),
        (4, '4 - Bonne'),
        (5, '5 - Excellente')
    ], coerce=int, validators=[Optional()])
    
    date_mise_en_place = DateField('Date de mise en place', 
                                  format='%Y-%m-%d',
                                  validators=[Optional()])


class EvaluationDispositifForm(FlaskForm):
    """Formulaire pour évaluer un dispositif de maîtrise"""
    efficacite_reelle = SelectField('Efficacité réelle', choices=[
        (0, '-- Sélectionner --'),
        (1, '1 - Très faible'),
        (2, '2 - Faible'),
        (3, '3 - Moyenne'),
        (4, '4 - Bonne'),
        (5, '5 - Excellente')
    ], coerce=int, validators=[DataRequired(message="L'efficacité réelle est obligatoire")])
    
    couverture = SelectField('Couverture', choices=[
        (0, '-- Sélectionner --'),
        (1, '1 - Très limitée'),
        (2, '2 - Limitée'),
        (3, '3 - Partielle'),
        (4, '4 - Bonne'),
        (5, '5 - Totale')
    ], coerce=int, validators=[DataRequired(message='La couverture est obligatoire')])
    
    prochaine_verification = DateField('Prochaine vérification', 
                                      format='%Y-%m-%d',
                                      validators=[Optional()])
    
    commentaire = TextAreaField('Commentaire', validators=[
        Optional(),
        Length(max=1000, message='Maximum 1000 caractères')
    ])


class VerificationDispositifForm(FlaskForm):
    """Formulaire pour ajouter une vérification d'un dispositif"""
    date_verification = DateField('Date de vérification', 
                                 format='%Y-%m-%d',
                                 validators=[DataRequired(message='La date est obligatoire')])
    
    type_verification = SelectField('Type de vérification', choices=[
        ('', '-- Sélectionner --'),
        ('Test', 'Test'),
        ('Observation', 'Observation'),
        ('Revue documentaire', 'Revue documentaire'),
        ('Entretien', 'Entretien'),
        ('Autre', 'Autre')
    ], validators=[DataRequired(message='Le type est obligatoire')])
    
    resultat = SelectField('Résultat', choices=[
        ('', '-- Sélectionner --'),
        ('Conforme', 'Conforme'),
        ('Non conforme', 'Non conforme'),
        ('À corriger', 'À corriger'),
        ('À améliorer', 'À améliorer')
    ], validators=[DataRequired(message='Le résultat est obligatoire')])
    
    commentaire = TextAreaField('Commentaire', validators=[
        Optional(),
        Length(max=2000, message='Maximum 2000 caractères')
    ])


class DocumentDispositifForm(FlaskForm):
    """Formulaire pour ajouter un document à un dispositif"""
    fichier = FileField('Fichier', validators=[
        DataRequired(message='Le fichier est obligatoire'),
        FileAllowed(['pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'txt', 'jpg', 'jpeg', 'png'],
                   'Formats autorisés: PDF, Word, Excel, PowerPoint, TXT, JPG, PNG')
    ])
    
    type_document = SelectField('Type de document', choices=[
        ('', '-- Sélectionner --'),
        ('Procédure', 'Procédure'),
        ('Mode opératoire', 'Mode opératoire'),
        ('Fiche de contrôle', 'Fiche de contrôle'),
        ('Rapport', 'Rapport'),
        ('Documentation', 'Documentation'),
        ('Autre', 'Autre')
    ], validators=[DataRequired(message='Le type de document est obligatoire')])
    
    description = TextAreaField('Description', validators=[
        Optional(),
        Length(max=500, message='Maximum 500 caractères')
    ])

class SimplePlanActionForm(FlaskForm):
    """Formulaire simplifié pour créer un plan d'action"""
    nom = StringField('Nom du plan d\'action', validators=[  # Changé de titre à nom
        DataRequired(message='Le nom est obligatoire'),
        Length(max=200, message='Maximum 200 caractères')
    ])
    
    description = TextAreaField('Description', validators=[
        DataRequired(message='La description est obligatoire'),
        Length(max=2000, message='Maximum 2000 caractères')
    ])
    
    responsable_id = SelectField('Responsable', coerce=int, validators=[DataRequired()])
    
    date_debut = DateField('Date de début', format='%Y-%m-%d',
                          validators=[DataRequired(message='La date de début est obligatoire')])
    
    date_echeance = DateField('Date d\'échéance', format='%Y-%m-%d',  # date_fin_prevue dans le modèle
                             validators=[DataRequired(message='La date d\'échéance est obligatoire')])
    
    priorite = SelectField('Priorité', choices=[
        ('', '-- Sélectionner --'),
        ('basse', 'Basse'),
        ('moyenne', 'Moyenne'),
        ('haute', 'Haute'),
        ('critique', 'Critique')
    ], validators=[DataRequired(message='La priorité est obligatoire')])
    
    dispositif_id = HiddenField('Dispositif ID')
    risque_id = HiddenField('Risque ID')

class SousActionForm(FlaskForm):
    """Formulaire pour créer/modifier une sous-action"""
    description = TextAreaField('Description', validators=[
        DataRequired(message='La description est obligatoire'),
        Length(max=1000, message='Maximum 1000 caractères')
    ])
    
    responsable_id = SelectField('Responsable', coerce=int)
    
    date_debut = DateField('Date de début', format='%Y-%m-%d',
                          validators=[Optional()])
    
    date_fin_prevue = DateField('Date d\'échéance', format='%Y-%m-%d',
                               validators=[Optional()])
    
    # AJOUTEZ CE CHAMP (il est déjà là mais vérifiez qu'il est correct)
    commentaire = TextAreaField('Commentaire', validators=[
        Optional(),
        Length(max=500, message='Maximum 500 caractères')
    ])
    
    # AJOUTEZ AUSSI UN CHAMP SUBMIT POUR LE TEMPLATE
    from wtforms import SubmitField
    submit = SubmitField('Enregistrer')


class CampagneForm(FlaskForm):
    """Formulaire pour créer/modifier une campagne"""
    nom = StringField('Nom de la campagne', validators=[
        DataRequired(message="Le nom est obligatoire"),
        Length(min=2, max=100, message="Le nom doit contenir entre 2 et 100 caractères")
    ])
    
    description = TextAreaField('Description', validators=[
        Length(max=500, message="La description ne doit pas dépasser 500 caractères")
    ])
    
    date_debut = DateField('Date de début', format='%Y-%m-%d', validators=[Optional()])
    date_fin = DateField('Date de fin', format='%Y-%m-%d', validators=[Optional()])
    
    statut = SelectField('Statut', choices=[
        ('planifiee', 'Planifiée'),
        ('en_cours', 'En cours'),
        ('terminee', 'Terminée'),
        ('suspendue', 'Suspendue')
    ], validators=[DataRequired()])
    
    submit = SubmitField('Enregistrer')
