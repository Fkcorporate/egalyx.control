# forms_incident.py
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, DateTimeField, IntegerField, BooleanField, SubmitField, FileField
from wtforms.validators import DataRequired, Optional, Length, ValidationError, Email
from datetime import datetime

class IncidentForm(FlaskForm):
    """Formulaire de création d'incident"""
    
    titre = StringField('Titre', validators=[DataRequired(), Length(max=200)])
    description = TextAreaField('Description', validators=[DataRequired()])
    
    gravite = SelectField('Gravité', choices=[
        ('critique', 'Critique - Impact majeur'),
        ('elevee', 'Élevée - Impact significatif'),
        ('moyenne', 'Moyenne - Impact modéré'),
        ('mineure', 'Mineure - Impact limité')
    ], default='moyenne')
    
    type_incident = SelectField('Type', choices=[
        ('', 'Sélectionnez...'),
        ('securite', 'Sécurité'),
        ('conformite', 'Conformité'),
        ('operationnel', 'Opérationnel'),
        ('technique', 'Technique'),
        ('juridique', 'Juridique')
    ], validators=[DataRequired()])
    
    date_occurrence = DateTimeField('Date d\'occurrence', format='%Y-%m-%dT%H:%M', 
                                    default=datetime.now, validators=[DataRequired()])
    
    risque_id = SelectField('Risque associé', coerce=int, choices=[], validators=[Optional()])
    dispositif_id = SelectField('Dispositif concerné', coerce=int, choices=[], validators=[Optional()])
    responsable_resolution_id = SelectField('Responsable résolution', coerce=int, choices=[], validators=[Optional()])
    
    sla_heures = IntegerField('SLA (heures)', default=48, validators=[Optional()])
    approbation_requise = BooleanField('Approbation requise avant clôture', default=False)
    
    submit = SubmitField('Créer l\'incident')


class IncidentResolutionForm(FlaskForm):
    """Formulaire de résolution d'incident"""
    
    statut = SelectField('Statut', choices=[
        ('en_cours', 'En cours de résolution'),
        ('resolu', 'Résolu - Solution trouvée'),
        ('ferme', 'Fermé - Incident clos'),
        ('rejete', 'Rejeté - Incident non valide')
    ], validators=[DataRequired()])
    
    cause_racine = TextAreaField('Cause racine', validators=[Optional()])
    actions_correctives = TextAreaField('Actions correctives', validators=[Optional()])
    lecons_apprises = TextAreaField('Leçons apprises', validators=[Optional()])
    commentaire_cloture = TextAreaField('Commentaire de clôture', validators=[Optional()])
    
    creer_plan_action = BooleanField('Créer un plan d\'action associé', default=False)
    
    submit = SubmitField('Enregistrer la résolution')


class IncidentApprobationForm(FlaskForm):
    """Formulaire d'approbation d'incident"""
    
    approbation = SelectField('Décision', choices=[
        ('approuve', 'Approuver - Incident valide et clos'),
        ('rejete', 'Rejeter - Retour en cours pour corrections')
    ], validators=[DataRequired()])
    
    commentaire = TextAreaField('Commentaire', validators=[DataRequired()])
    
    submit = SubmitField('Valider la décision')


class TicketSupportForm(FlaskForm):
    """Formulaire de ticket support (interface client)"""
    
    nom = StringField('Nom complet', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    telephone = StringField('Téléphone', validators=[Optional()])
    societe = StringField('Société', validators=[DataRequired()])
    
    sujet = StringField('Sujet', validators=[DataRequired(), Length(max=200)])
    description = TextAreaField('Description du problème', validators=[DataRequired()])
    priorite = SelectField('Priorité', choices=[
        ('basse', 'Basse - Peu urgent'),
        ('normale', 'Normale - À traiter sous 48h'),
        ('haute', 'Haute - À traiter sous 24h'),
        ('critique', 'Critique - Urgent')
    ], default='normale')
    
    pieces_jointes = FileField('Pièces jointes', validators=[Optional()])
    
    submit = SubmitField('Envoyer le ticket')


class IncidentSearchForm(FlaskForm):
    """Formulaire de recherche avancée"""
    
    gravite = SelectField('Gravité', choices=[('', 'Toutes'), ('critique', 'Critique'), 
                        ('elevee', 'Élevée'), ('moyenne', 'Moyenne'), ('mineure', 'Mineure')])
    type_incident = SelectField('Type', choices=[('', 'Tous'), ('securite', 'Sécurité'),
                              ('conformite', 'Conformité'), ('operationnel', 'Opérationnel'),
                              ('technique', 'Technique'), ('juridique', 'Juridique')])
    statut = SelectField('Statut', choices=[('', 'Tous'), ('ouvert', 'Ouvert'),
                        ('en_cours', 'En cours'), ('resolu', 'Résolu'),
                        ('ferme', 'Fermé'), ('rejete', 'Rejeté')])
    escalation = SelectField('Niveau escalade', choices=[('', 'Tous'), ('1', 'Niveau 1'),
                           ('2', 'Niveau 2'), ('3', 'Niveau 3')])
    sla_viole = SelectField('SLA', choices=[('', 'Tous'), ('oui', 'Violé'), ('non', 'Respecté')])
    date_debut = DateTimeField('Date début', format='%Y-%m-%d', validators=[Optional()])
    date_fin = DateTimeField('Date fin', format='%Y-%m-%d', validators=[Optional()])
    submit = SubmitField('Rechercher')