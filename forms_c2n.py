# forms_c2n.py - Nouveau fichier

from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, IntegerField, DateField, FloatField, HiddenField
from wtforms.validators import DataRequired, Optional, NumberRange, Length
from wtforms.fields import FieldList, FormField

# Formulaire pour le référentiel
class ReferentielControleForm(FlaskForm):
    code_controle = StringField('Code contrôle', validators=[DataRequired(), Length(max=50)])
    nom = StringField('Nom du contrôle', validators=[DataRequired(), Length(max=200)])
    processus = StringField('Processus', validators=[Optional(), Length(max=100)])
    metier = StringField('Métier', validators=[Optional(), Length(max=100)])
    objectif = TextAreaField('Objectif du contrôle')
    risques_couverts = TextAreaField('Risques couverts (un par ligne)')
    frequence = SelectField('Fréquence', choices=[
        ('mensuel', 'Mensuel'),
        ('trimestriel', 'Trimestriel'),
        ('annuel', 'Annuel')
    ], validators=[DataRequired()])
    responsable_id = SelectField('Responsable', coerce=int, validators=[Optional()])


# Formulaire pour la planification
class PlanificationControleForm(FlaskForm):
    annee = SelectField('Année', coerce=int, validators=[DataRequired()])
    mois = SelectField('Mois', coerce=int, choices=[
        (0, 'Annuel (pas de mois spécifique)'),
        (1, 'Janvier'), (2, 'Février'), (3, 'Mars'),
        (4, 'Avril'), (5, 'Mai'), (6, 'Juin'),
        (7, 'Juillet'), (8, 'Août'), (9, 'Septembre'),
        (10, 'Octobre'), (11, 'Novembre'), (12, 'Décembre')
    ], validators=[Optional()])
    perimetre = StringField('Périmètre', validators=[Optional(), Length(max=200)])
    date_prevue = DateField('Date prévue', validators=[DataRequired()], format='%Y-%m-%d')
    controleur_id = SelectField('Contrôleur assigné', coerce=int, validators=[DataRequired()])
    referentiel_id = SelectField('Référentiel', coerce=int, validators=[DataRequired()])


# Formulaire pour l'exécution (réutilise vos champs)
class ExecutionControleForm(FlaskForm):
    volume_previsionnel = IntegerField('Volume prévisionnel', validators=[Optional(), NumberRange(min=0)])
    volume_controle = IntegerField('Volume contrôlé', validators=[Optional(), NumberRange(min=0)])
    resultats = TextAreaField('Résultats du contrôle')
    commentaires = TextAreaField('Commentaires')
    conclusion = TextAreaField('Conclusion')
    taux_conformite = FloatField('Taux de conformité (%)', validators=[Optional(), NumberRange(min=0, max=100)])


# Formulaire pour la non-conformité
class NonConformiteC2NForm(FlaskForm):
    description = TextAreaField('Description', validators=[DataRequired()])
    nombre_ecarts = IntegerField('Nombre d\'écarts', validators=[Optional(), NumberRange(min=0)])
    niveau_criticite = SelectField('Niveau de criticité', choices=[
        ('mineur', '🟡 Mineur'),
        ('majeur', '🟠 Majeur'),
        ('critique', '🔴 Critique')
    ], validators=[DataRequired()])
    impact = TextAreaField('Impact')
    cause_racine = TextAreaField('Cause racine')


# Formulaire pour le plan d'action
class PlanActionC2NForm(FlaskForm):
    action_corrective = TextAreaField('Action corrective', validators=[DataRequired()])
    responsable_id = SelectField('Responsable', coerce=int, validators=[Optional()])
    date_echeance = DateField('Date d\'échéance', validators=[Optional()], format='%Y-%m-%d')
    statut = SelectField('Statut', choices=[
        ('a_faire', '📋 À faire'),
        ('en_cours', '▶️ En cours'),
        ('terminee', '✅ Terminée')
    ], validators=[Optional()])
    taux_avancement = IntegerField('Taux d\'avancement (%)', validators=[Optional(), NumberRange(min=0, max=100)])


# Formulaire de validation
class ValidationControleForm(FlaskForm):
    action = SelectField('Action', choices=[
        ('approuve', '✅ Approuver'),
        ('rejete', '❌ Rejeter')
    ], validators=[DataRequired()])
    commentaire = TextAreaField('Commentaire', validators=[DataRequired()])