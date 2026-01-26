import json
import os
from werkzeug.utils import secure_filename
from models import db, ConfigurationChampRisque, ConfigurationListeDeroulante, ChampPersonnaliseRisque, FichierRisque

class GestionnaireParametrage:
    """Classe pour gérer le paramétrage dynamique des fiches de risque"""
    
    @staticmethod
    def generer_formulaire_risque(risque_id=None):
        """Génère dynamiquement le formulaire de risque basé sur la configuration"""
        from forms import RisqueForm
        
        class RisqueFormDynamique(RisqueForm):
            pass
        
        # Récupérer les champs configurés
        champs_config = ConfigurationChampRisque.query.filter_by(
            est_actif=True
        ).order_by('section', 'ordre_affichage').all()
        
        # Valeurs existantes si modification
        valeurs_existantes = {}
        if risque_id:
            champs_perso = ChampPersonnaliseRisque.query.filter_by(risque_id=risque_id).all()
            for champ in champs_perso:
                valeurs_existantes[champ.nom_technique] = champ.get_valeur()
        
        # Ajouter les champs dynamiques
        for config in champs_config:
            field_name = config.nom_technique
            
            # Créer le champ selon le type
            if config.type_champ == 'texte':
                field = StringField(
                    config.nom_affichage,
                    validators=[DataRequired() if config.est_obligatoire else Optional()],
                    description=config.aide_texte,
                    default=valeurs_existantes.get(field_name, '')
                )
                
            elif config.type_champ == 'textarea':
                field = TextAreaField(
                    config.nom_affichage,
                    validators=[DataRequired() if config.est_obligatoire else Optional()],
                    description=config.aide_texte,
                    default=valeurs_existantes.get(field_name, '')
                )
                
            elif config.type_champ in ['select', 'multiselect', 'radio']:
                # Récupérer les options depuis la liste déroulante ou valeurs possibles
                options = []
                if config.valeurs_possibles:
                    # Valeurs directes
                    for val in config.valeurs_possibles:
                        options.append((val, val))
                else:
                    # Chercher une liste déroulante associée
                    liste = ConfigurationListeDeroulante.query.filter_by(
                        nom_technique=field_name
                    ).first()
                    if liste and liste.valeurs:
                        for item in liste.valeurs:
                            options.append((item.get('valeur'), item.get('label', item.get('valeur'))))
                
                if config.type_champ == 'select':
                    field = SelectField(
                        config.nom_affichage,
                        choices=[('', 'Sélectionnez...')] + options,
                        validators=[DataRequired() if config.est_obligatoire else Optional()],
                        description=config.aide_texte,
                        default=valeurs_existantes.get(field_name, '')
                    )
                elif config.type_champ == 'multiselect':
                    field = SelectMultipleField(
                        config.nom_affichage,
                        choices=options,
                        validators=[DataRequired() if config.est_obligatoire else Optional()],
                        description=config.aide_texte,
                        default=valeurs_existantes.get(field_name, [])
                    )
                elif config.type_champ == 'radio':
                    field = RadioField(
                        config.nom_affichage,
                        choices=options,
                        validators=[DataRequired() if config.est_obligatoire else Optional()],
                        description=config.aide_texte,
                        default=valeurs_existantes.get(field_name, '')
                    )
                    
            elif config.type_champ == 'checkbox':
                field = BooleanField(
                    config.nom_affichage,
                    description=config.aide_texte,
                    default=valeurs_existantes.get(field_name, False)
                )
                
            elif config.type_champ == 'date':
                from wtforms.fields import DateField
                field = DateField(
                    config.nom_affichage,
                    format='%Y-%m-%d',
                    validators=[DataRequired() if config.est_obligatoire else Optional()],
                    description=config.aide_texte,
                    default=valeurs_existantes.get(field_name, None)
                )
                
            elif config.type_champ == 'fichier':
                from wtforms.fields import FileField
                field = FileField(
                    config.nom_affichage,
                    description=config.aide_texte
                )
                
            elif config.type_champ == 'nombre':
                field = IntegerField(
                    config.nom_affichage,
                    validators=[DataRequired() if config.est_obligatoire else Optional()],
                    description=config.aide_texte,
                    default=valeurs_existantes.get(field_name, 0)
                )
            
            # Ajouter le champ au formulaire
            setattr(RisqueFormDynamique, field_name, field)
        
        return RisqueFormDynamique
    
    @staticmethod
    def sauvegarder_champs_personnalises(risque_id, form_data):
        """Sauvegarde les champs personnalisés d'un risque"""
        # Supprimer les champs existants
        ChampPersonnaliseRisque.query.filter_by(risque_id=risque_id).delete()
        
        # Récupérer la configuration des champs
        champs_config = ConfigurationChampRisque.query.filter_by(est_actif=True).all()
        
        for config in champs_config:
            field_name = config.nom_technique
            if field_name in form_data:
                valeur = form_data[field_name]
                
                # Ne pas sauvegarder les champs vides non obligatoires
                if not config.est_obligatoire and not valeur:
                    continue
                
                champ = ChampPersonnaliseRisque(
                    risque_id=risque_id,
                    nom_technique=field_name
                )
                champ.set_valeur(valeur)
                db.session.add(champ)
        
        db.session.commit()
    
    @staticmethod
    def generer_liste_deroulante_options(nom_liste):
        """Génère les options pour une liste déroulante"""
        liste = ConfigurationListeDeroulante.query.filter_by(
            nom_technique=nom_liste,
            est_actif=True
        ).first()
        
        if liste and liste.valeurs:
            return [(item.get('valeur'), item.get('label', item.get('valeur'))) 
                   for item in liste.valeurs]
        
        return []
    
    @staticmethod
    def televerser_fichier(risque_id, fichier, categorie='document', description=''):
        """Téléverse un fichier pour un risque"""
        if fichier:
            # Sécuriser le nom du fichier
            nom_fichier = secure_filename(fichier.filename)
            timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            nom_unique = f"{timestamp}_{nom_fichier}"
            
            # Chemin de sauvegarde
            dossier = os.path.join(current_app.config['UPLOAD_FOLDER'], 'risques', str(risque_id))
            os.makedirs(dossier, exist_ok=True)
            chemin = os.path.join(dossier, nom_unique)
            
            # Sauvegarder le fichier
            fichier.save(chemin)
            
            # Enregistrer en base
            fichier_db = FichierRisque(
                risque_id=risque_id,
                nom_fichier=nom_fichier,
                chemin_fichier=chemin,
                type_fichier=fichier.content_type,
                taille=os.path.getsize(chemin),
                categorie=categorie,
                description=description,
                uploaded_by=current_user.id
            )
            
            db.session.add(fichier_db)
            db.session.commit()
            
            return fichier_db
        
        return None
    
    @staticmethod
    def synchroniser_configuration_globale():
        """Synchronise la configuration avec toutes les fiches existantes"""
        # Cette méthode peut être appelée après modification de la configuration
        # pour appliquer les changements à tous les risques existants
        pass