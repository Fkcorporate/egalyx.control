# services/incident_ia_service.py
import json
import openai
from datetime import datetime, timedelta
from flask import current_app

# IMPORTANT: Ajouter cet import pour accéder au modèle Incident
from models import Incident

class IncidentIAService:
    """Service d'analyse IA pour les incidents"""
    
    @staticmethod
    def analyser_incident(incident):
        """Analyse complète d'un incident avec IA"""
        
        # Préparer le prompt
        prompt = f"""
        Analyse l'incident suivant et fournis:
        1. Classification automatique (type, gravité)
        2. Causes probables
        3. Recommandations de résolution
        4. Estimation du délai de résolution
        
        Incident:
        - Titre: {incident.titre}
        - Description: {incident.description}
        - Type actuel: {incident.type_incident}
        - Gravité actuelle: {incident.gravite}
        """
        
        try:
            # Appel API OpenAI (ou simulation)
            response = IncidentIAService._appel_api_ia(prompt)
            
            # Stocker l'analyse
            incident.analyse_ia = json.dumps(response)
            incident.ia_score_confiance = response.get('score_confiance', 75)
            incident.ia_recommandations = json.dumps(response.get('recommandations', []))
            
            return response
            
        except Exception as e:
            current_app.logger.error(f"Erreur analyse IA incident {incident.id}: {e}")
            return IncidentIAService._get_analyse_fallback(incident)
    
    @staticmethod
    def predire_recurrence(incident):
        """Prédit la probabilité de récurrence"""
        
        # Analyse des incidents similaires dans l'historique
        incidents_similaires = Incident.query.filter(
            Incident.type_incident == incident.type_incident,
            Incident.client_id == incident.client_id,
            Incident.id != incident.id,
            Incident.created_at >= datetime.utcnow() - timedelta(days=365)
        ).count()
        
        # Facteurs de risque
        facteurs = {
            'cause_connue': bool(incident.cause_racine),
            'actions_correctives': bool(incident.actions_correctives),
            'historique_similaire': incidents_similaires > 3,
            'gravite_elevee': incident.gravite in ['critique', 'elevee']
        }
        
        # Calcul de probabilité (modèle simple)
        probabilite = 50  # Base
        if not facteurs['cause_connue']:
            probabilite += 20
        if not facteurs['actions_correctives']:
            probabilite += 15
        if facteurs['historique_similaire']:
            probabilite += 10
        if facteurs['gravite_elevee']:
            probabilite += 5
        
        probabilite = min(probabilite, 95)
        
        return {
            'probabilite_recurrence': probabilite,
            'niveau_risque': 'eleve' if probabilite > 70 else 'moyen' if probabilite > 40 else 'faible',
            'facteurs': facteurs,
            'recommandation': IncidentIAService._generer_recommandation_recurrence(probabilite, facteurs)
        }
    
    @staticmethod
    def detecter_tendance_incidents(client_id, jours=30):
        """Détecte les tendances d'incidents sur une période"""
        
        date_limite = datetime.utcnow() - timedelta(days=jours)
        
        incidents = Incident.query.filter(
            Incident.client_id == client_id,
            Incident.created_at >= date_limite
        ).all()
        
        if not incidents:
            return {'tendance': 'stable', 'message': 'Pas assez de données'}
        
        # Analyse des tendances
        tendance_par_type = {}
        for inc in incidents:
            if inc.type_incident not in tendance_par_type:
                tendance_par_type[inc.type_incident] = 0
            tendance_par_type[inc.type_incident] += 1
        
        # Détection des pics
        moyenne = len(incidents) / jours
        pic_detecte = len(incidents) > moyenne * 1.5
        
        # Prédiction
        if pic_detecte:
            prediction = "hausse significative"
        elif len(incidents) < moyenne * 0.5:
            prediction = "baisse significative"
        else:
            prediction = "stable"
        
        # Types les plus fréquents - CORRECTION ICI
        types_frequents = sorted(tendance_par_type.items(), key=lambda x: x[1], reverse=True)[:3]
        
        return {
            'tendance': prediction,
            'total_incidents': len(incidents),
            'moyenne_journaliere': round(len(incidents) / jours, 2),
            'pic_detecte': pic_detecte,
            'types_frequents': [{'type': t, 'count': c} for t, c in types_frequents],
            'recommandation': IncidentIAService._generer_recommandation_tendance(prediction, types_frequents)
        }
    
    @staticmethod
    def suggerer_ameliorations(client_id):
        """Suggère des améliorations basées sur l'historique des incidents"""
        
        incidents = Incident.query.filter(
            Incident.client_id == client_id,
            Incident.created_at >= datetime.utcnow() - timedelta(days=90)
        ).all()
        
        if len(incidents) < 5:
            return {'suggestions': [], 'message': 'Pas assez d\'incidents pour des suggestions'}
        
        # Analyse des causes racines
        causes_par_type = {}
        for inc in incidents:
            if inc.cause_racine:
                type_inc = inc.type_incident
                if type_inc not in causes_par_type:
                    causes_par_type[type_inc] = []
                causes_par_type[type_inc].append(inc.cause_racine[:100])
        
        # Génération de suggestions
        suggestions = []
        
        for type_inc, causes in causes_par_type.items():
            if len(causes) >= 3:
                suggestions.append({
                    'type': type_inc,
                    'causes_principales': list(set(causes[:3])),
                    'suggestion': f"Renforcer les contrôles sur les incidents de type {type_inc}",
                    'priorite': 'haute' if len(causes) >= 5 else 'moyenne'
                })
        
        return {'suggestions': suggestions, 'total_analyses': len(incidents)}
    
    @staticmethod
    def _appel_api_ia(prompt):
        """Appel à l'API OpenAI (simulé pour l'exemple)"""
        # Simulation - à remplacer par un vrai appel API
        return {
            'classification': {'type': 'technique', 'gravite': 'moyenne'},
            'causes_probables': ['Défaut de configuration', 'Erreur humaine'],
            'recommandations': ['Vérifier les logs', 'Mettre à jour la documentation'],
            'delai_estime': '2-4 heures',
            'score_confiance': 85
        }
    
    @staticmethod
    def _get_analyse_fallback(incident):
        """Analyse de secours quand l'IA n'est pas disponible"""
        return {
            'classification': {'type': incident.type_incident, 'gravite': incident.gravite},
            'causes_probables': ['À analyser manuellement'],
            'recommandations': ['Examiner l\'incident en détail'],
            'delai_estime': 'Non estimé',
            'score_confiance': 50,
            'mode': 'fallback'
        }
    
    @staticmethod
    def _generer_recommandation_recurrence(probabilite, facteurs):
        """Génère une recommandation basée sur la probabilité de récurrence"""
        if probabilite > 70:
            return "Risque élevé de récurrence. Mettre en place des actions correctives immédiates."
        elif probabilite > 40:
            return "Risque modéré. Surveiller et documenter tout événement similaire."
        else:
            return "Risque faible. Continuer la surveillance standard."
    
    @staticmethod
    def _generer_recommandation_tendance(prediction, types_frequents):
        """Génère une recommandation basée sur la tendance - CORRIGÉ"""
        if prediction == "hausse significative":
            # CORRECTION: types_frequents est une liste de tuples (type, count)
            types = ", ".join([t[0] for t in types_frequents[:2]])  # t[0] pour le type, t[1] pour le count
            return f"Augmentation des incidents. Prioriser l'analyse des types: {types}"
        elif prediction == "baisse significative":
            return "Tendance positive. Maintenir les actions en place."
        else:
            return "Situation stable. Continuer la surveillance."
    # À ajouter dans la classe IncidentIAService

    @staticmethod
    def suggerer_resolution(incident):
        """
        Génère des suggestions de résolution basées sur l'analyse IA
        Retourne un dict avec cause_racine, actions_correctives, lecons_apprises
        """
        # Utiliser l'analyse existante ou en lancer une nouvelle
        if not incident.analyse_ia:
            analyse = IncidentIAService.analyser_incident(incident)
        else:
            analyse = json.loads(incident.analyse_ia)
        
        # Générer des suggestions structurées
        suggestions = {
            'cause_racine': "",
            'actions_correctives': "",
            'lecons_apprises': "",
            'commentaire_cloture': ""
        }
        
        causes = analyse.get('causes_probables', [])
        if causes:
            suggestions['cause_racine'] = " ; ".join(causes)
        
        recommandations = analyse.get('recommandations', [])
        if recommandations:
            suggestions['actions_correctives'] = "\n".join(f"- {r}" for r in recommandations)
        
        suggestions['lecons_apprises'] = f"Suite à l'incident de type {incident.get_type_label()}, il est recommandé de renforcer les contrôles sur les causes identifiées."
        suggestions['commentaire_cloture'] = f"Incident analysé par IA (score {incident.ia_score_confiance}%). À valider par un responsable."
        
        return suggestions
