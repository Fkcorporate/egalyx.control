from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed
from wtforms import StringField, TextAreaField, SelectField, DateField, IntegerField, BooleanField, SubmitField, FieldList, FormField, FileField, TimeField, DateTimeField, HiddenFieldfrom datetime import datetime, timedelta

# Formulaire pour un objectif qualité individuel
class ObjectifQualiteForm(FlaskForm):
    objectif = StringField('Objectif', validators=[DataRequired(), Length(max=255)])
    
# Formulaire pour un indicateur clé (KPI) individuel
class IndicateurCleForm(FlaskForm):
    nom = StringField('Nom de l\'indicateur', validators=[DataRequired(), Length(max=100)])
    cible = StringField('Cible', validators=[DataRequired(), Length(max=100)])
    unite = StringField('Unité', validators=[Optional(), Length(max=50)])
    
class PlanQualiteFonctionForm(FlaskForm):
    # ============================================
    # INFORMATIONS GÉNÉRALES
    # ============================================
    reference = StringField('Référence', validators=[DataRequired(), Length(max=50)])
    titre = StringField('Titre du plan', validators=[DataRequired(), Length(max=200)])
    description = TextAreaField('Description', validators=[Optional()])
    
    # ============================================
    # FONCTION CIBLE
    # ============================================
    type_fonction = SelectField('Type de fonction', choices=[
        ('pole', 'Pôle'),
        ('direction', 'Direction'),
        ('service', 'Service')
    ], validators=[DataRequired()])
    pole_id = SelectField('Pôle', coerce=int, choices=[], validators=[Optional()])
    direction_id = SelectField('Direction', coerce=int, choices=[], validators=[Optional()])
    service_id = SelectField('Service', coerce=int, choices=[], validators=[Optional()])
    
    # ============================================
    # PÉRIODE
    # ============================================
    date_debut = DateField('Date de début', validators=[DataRequired()], default=datetime.now().date)
    date_fin = DateField('Date de fin', validators=[DataRequired()], default=(datetime.now() + timedelta(days=365)).date)
    annee_exercice = IntegerField('Année d\'exercice', validators=[DataRequired()], default=datetime.now().year)
    
    # ============================================
    # SECTION 1 : ASSURANCE QUALITÉ (PRÉVENTIF)
    # ============================================
    procedures_applicables = TextAreaField('Procédures applicables', validators=[Optional()])
    frequence_controles = SelectField('Fréquence des contrôles internes', choices=[
        ('quotidien', 'Quotidien'),
        ('hebdomadaire', 'Hebdomadaire'),
        ('mensuel', 'Mensuel'),
        ('trimestriel', 'Trimestriel'),
        ('semestriel', 'Semestriel'),
        ('annuel', 'Annuel')
    ], default='mensuel')
    responsable_conformite_id = SelectField('Responsable conformité', coerce=int, choices=[], validators=[Optional()])
    documents_reference = TextAreaField('Documents de référence', validators=[Optional()])
    controles_cles = TextAreaField('Contrôles clés existants', validators=[Optional()])
    niveau_maturite = SelectField('Niveau de maturité', choices=[
        ('1', '1 - Initial'),
        ('2', '2 - Répétable'),
        ('3', '3 - Défini'),
        ('4', '4 - Géré'),
        ('5', '5 - Optimisé')
    ], default='3')
    
    # ============================================
    # SECTION 2 : AMÉLIORATION QUALITÉ (CORRECTIF)
    # ============================================
    objectifs_qualite = FieldList(FormField(ObjectifQualiteForm), min_entries=1)
    indicateurs_cles = FieldList(FormField(IndicateurCleForm), min_entries=1)
    
    # ============================================
    # SECTION 3 : REVUE ET AUDIT DU PLAN
    # ============================================
    date_prochaine_revue = DateField('Date de la prochaine revue', validators=[Optional()])
    date_derniere_revue = DateField('Date de la dernière revue', validators=[Optional()])
    responsable_revue_id = SelectField('Responsable de la revue', coerce=int, choices=[], validators=[Optional()])
    
    # ============================================
    # STATUT ET VALIDATION
    # ============================================
    statut = SelectField('Statut', choices=[
        ('brouillon', 'Brouillon'),
        ('actif', 'Actif'),
        ('clos', 'Clos'),
        ('annule', 'Annulé')
    ], default='brouillon')
    est_valide = BooleanField('Plan validé', default=False)
    submit = SubmitField('Enregistrer le plan')


class ActionAmeliorationQualiteForm(FlaskForm):
    reference = StringField('Référence', validators=[DataRequired(), Length(max=50)])
    intitule = StringField('Intitulé de l\'action', validators=[DataRequired(), Length(max=200)])
    description = TextAreaField('Description', validators=[Optional()])
    
    date_echeance = DateField('Date d\'échéance', validators=[DataRequired()], default=(datetime.now() + timedelta(days=30)).date)
    priorite = SelectField('Priorité', choices=[
        ('basse', 'Basse'),
        ('moyenne', 'Moyenne'),
        ('haute', 'Haute')
    ], default='moyenne')
    
    statut = SelectField('Statut', choices=[
        ('a_faire', 'À faire'),
        ('en_cours', 'En cours'),
        ('terminee', 'Terminée'),
        ('bloquee', 'Bloquée')
    ], default='a_faire')
    
    pourcentage_realisation = IntegerField('Avancement (%)', validators=[NumberRange(min=0, max=100)], default=0)
    commentaire_realisation = TextAreaField('Commentaire de réalisation', validators=[Optional()])
    
    responsable_id = SelectField('Responsable', coerce=int, choices=[], validators=[Optional()])
    submit = SubmitField('Enregistrer l\'action')


class UploadFichierPlanQualiteForm(FlaskForm):
    """Formulaire pour uploader un fichier"""
    fichier = FileField('Fichier', validators=[
        FileRequired(message='Veuillez sélectionner un fichier'),
        FileAllowed(['pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'jpg', 'jpeg', 'png', 'txt'], 
                   'Formats autorisés: PDF, Word, Excel, PowerPoint, Images, TXT')
    ])
    categorie = SelectField('Catégorie', choices=[
        ('document', 'Document général'),
        ('procedure', 'Procédure'),
        ('rapport', 'Rapport'),
        ('certificat', 'Certificat'),
        ('autre', 'Autre')
    ], default='document')
    description = TextAreaField('Description', validators=[Optional(), Length(max=500)])
    submit = SubmitField('Uploader')

class CartographieRisqueFonctionForm(FlaskForm):
    """Formulaire pour la cartographie des risques par fonction"""
    
    # Identification
    pole = StringField('Pôle', validators=[DataRequired(), Length(max=100)])
    direction = StringField('Direction', validators=[DataRequired(), Length(max=100)])
    direction_partie_prenante = StringField('Direction partie prenante', validators=[Optional(), Length(max=200)])
    zone_risque_majeur = StringField('Zone de Risque majeur', validators=[DataRequired(), Length(max=200)])
    
    # Évaluation
    impact = SelectField('Impact', choices=[
        ('Très fort à éviter', 'Très fort à éviter'),
        ('Fort à éviter', 'Fort à éviter'),
        ('Modéré', 'Modéré'),
        ('Faible', 'Faible'),
        ('Très faible', 'Très faible')
    ], validators=[DataRequired()])
    
    probabilite = SelectField('Probabilité', choices=[
        ('Certain', 'Certain'),
        ('Très probable', 'Très probable'),
        ('Probable', 'Probable'),
        ('Possible', 'Possible'),
        ('Peu probable', 'Peu probable'),
        ('Très rare', 'Très rare')
    ], validators=[DataRequired()])
    
    niveau_maitrise = SelectField('Niveau de maîtrise', choices=[
        ('Excellent', 'Excellent'),
        ('Bonne', 'Bonne'),
        ('Suffisante', 'Suffisante'),
        ('Faible', 'Faible'),
        ('Insuffisante', 'Insuffisante')
    ], validators=[DataRequired()])
    
    typologie_risque = StringField('Typologie Risque', validators=[Optional(), Length(max=100)])
    
    # Niveaux de contrôle
    niveau_1 = TextAreaField('Niveau 1 - Contrôle opérationnel', validators=[Optional()])
    niveau_2 = TextAreaField('Niveau 2 - Supervision', validators=[Optional()])
    niveau_3 = TextAreaField('Niveau 3 - Contrôle indépendant', validators=[Optional()])
    controle_externe = TextAreaField('Contrôle externe', validators=[Optional()])
    controles_prestataires = TextAreaField('Contrôles réalisés par prestataires externes', validators=[Optional()])
    
    # Historique
    anciens_audits = TextAreaField('Anciens audits en lien avec le risque', validators=[Optional()])
    plan_audit_annuel = TextAreaField("Plan d'audit annuel", validators=[Optional()])
    observations = TextAreaField('Observations', validators=[Optional()])
    
    # Fonctions d'assurance
    fonctions_assurance = StringField('Fonctions d\'assurance', validators=[Optional(), Length(max=200)])
    pole_audit = StringField('Pôle Audit', validators=[Optional(), Length(max=100)])
    pilote = StringField('Pilote', validators=[Optional(), Length(max=100)])
    
    annee = IntegerField('Année', validators=[DataRequired()], default=datetime.now().year)
    submit = SubmitField('Enregistrer')


# ============================================
# FORMULAIRES POUR LE MODULE QUALITÉ ULTRA-PREMIUM
# ============================================

# Formulaire pour les non-conformités
class NonConformiteForm(FlaskForm):
    titre = StringField('Titre', validators=[DataRequired(), Length(max=200)])
    description = TextAreaField('Description', validators=[DataRequired()])
    cause_racine = TextAreaField('Cause racine (5 pourquoi)', validators=[Optional()])
    gravite = SelectField('Gravité', choices=[
        ('mineure', 'Mineure'),
        ('majeure', 'Majeure'),
        ('critique', 'Critique')
    ], default='majeure')
    action_immediate = TextAreaField('Action immédiate', validators=[Optional()])
    action_corrective = TextAreaField('Action corrective', validators=[Optional()])
    action_preventive = TextAreaField('Action préventive', validators=[Optional()])
    responsable_id = SelectField('Responsable', coerce=int, choices=[], validators=[Optional()])
    submit = SubmitField('Enregistrer')


# Formulaire pour les audits qualité
class AuditQualiteForm(FlaskForm):
    titre = StringField('Titre de l\'audit', validators=[DataRequired(), Length(max=200)])
    perimetre = TextAreaField('Périmètre', validators=[Optional()])
    criteres = TextAreaField('Critères d\'audit', validators=[Optional()])
    auditeur_principal_id = SelectField('Auditeur principal', coerce=int, choices=[], validators=[Optional()])
    date_prevue = DateField('Date prévue', validators=[Optional()])
    conclusion = TextAreaField('Conclusion', validators=[Optional()])
    
    # Champs JSON pour l'équipe et les recommandations
    equipe_audit_json = HiddenField('Équipe audit JSON')
    recommandations_json = HiddenField('Recommandations JSON')
    
    submit = SubmitField('Enregistrer')


# Formulaire pour les formations
class FormationQualiteForm(FlaskForm):
    intitule = StringField('Intitulé de la formation', validators=[DataRequired(), Length(max=200)])
    description = TextAreaField('Description', validators=[Optional()])
    formateur = StringField('Formateur', validators=[Optional(), Length(max=200)])
    duree_heures = IntegerField('Durée (heures)', validators=[Optional()])
    date_formation = DateField('Date de la formation', validators=[Optional()])
    date_evaluation = DateField("Date d'évaluation", validators=[Optional()])
    
    # Champs JSON
    participants_json = HiddenField('Participants JSON')
    objectifs_json = HiddenField('Objectifs JSON')
    
    # Champs de certification et évaluation
    certification_obtenue = HiddenField('Certification obtenue')
    certification_nom = StringField('Nom de la certification', validators=[Optional(), Length(max=200)])
    satisfaction_moyenne = HiddenField('Satisfaction moyenne')
    efficacite = IntegerField('Efficacité (%)', validators=[Optional()])
    commentaires = TextAreaField('Commentaires', validators=[Optional()])
    
    submit = SubmitField('Enregistrer')


# Formulaire pour les réunions (CORRIGÉ - remplacement de DateTimeField par StringField)
class ReunionQualiteForm(FlaskForm):
    titre = StringField('Titre de la réunion', validators=[DataRequired(), Length(max=200)])
    type_reunion = SelectField('Type de réunion', choices=[
        ('revue_direction', 'Revue de direction'),
        ('comite_qualite', 'Comité qualité'),
        ('copil', 'COPIL'),
        ('audit', 'Audit')
    ], default='revue_direction')
    
    date_reunion = DateField('Date', validators=[DataRequired()], default=datetime.now().date)
    heure_reunion = TimeField('Heure', validators=[Optional()], default=datetime.now().time())
    duree_minutes = IntegerField('Durée (minutes)', validators=[Optional()])
    lieu = StringField('Lieu', validators=[Optional(), Length(max=200)])
    animateur_id = SelectField('Animateur', coerce=int, choices=[], validators=[Optional()])
    statut = SelectField('Statut', choices=[
        ('planifiee', '📅 Planifiée'),
        ('realisee', '✅ Réalisée'),
        ('reportee', '⏰ Reportée'),
        ('annulee', '❌ Annulée')
    ], default='planifiee')
    
    # 🔥 Champs JSON avec HiddenField
    participants_json = HiddenField('Participants JSON')
    ordre_jour_json = HiddenField('Ordre du jour JSON')
    decisions_json = HiddenField('Décisions JSON')
    actions_json = HiddenField('Actions JSON')
    
    compte_rendu = TextAreaField('Compte rendu', validators=[Optional()])
    submit = SubmitField('Enregistrer')


# Formulaire de filtrage pour la cartographie
class FiltreCartographieRisqueForm(FlaskForm):
    pole = SelectField('Pôle', choices=[], validators=[Optional()])
    direction = SelectField('Direction', choices=[], validators=[Optional()])
    niveau = SelectField('Niveau de risque', choices=[
        ('', 'Tous'),
        ('Faible', 'Faible'),
        ('Moyen', 'Moyen'),
        ('Élevé', 'Élevé'),
        ('Critique', 'Critique')
    ], validators=[Optional()])
    annee = SelectField('Année', choices=[], validators=[Optional()])
    submit = SubmitField('Filtrer')
