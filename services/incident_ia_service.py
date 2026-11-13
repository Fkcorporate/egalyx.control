# services/incident_ia_service.py
import json
from datetime import datetime, timedelta
from flask import current_app

# IMPORTANT: Ajouter cet import pour accéder au modèle Incident
from models import Incident

try:
    from egalyx import ia_moteur as moteur
except ImportError:                                    # installation sans le module commun
    moteur = None

CONSIGNES_INCIDENT = """Tu es un expert en gestion des incidents et du risque opérationnel. On te donne UN incident déclaré.
Analyse-le à partir de ses seules informations : n'invente ni fait, ni chiffre, ni nom. Si une information manque, dis-le.
Français professionnel, concret.
Réponds {"classification": {"type": "...", "gravite": "faible|moyenne|elevee|critique"},
 "causes_probables": ["au plus 3, formulées comme des hypothèses à vérifier"],
 "recommandations": ["au plus 4 actions concrètes, de la plus urgente à la moins urgente"],
 "delai_estime": "estimation prudente du délai de résolution, ou 'Non estimable' si les informations manquent",
 "informations_manquantes": ["au plus 3 éléments qu'il faudrait connaître"]}"""

class IncidentIAService:
    """Service d'analyse IA pour les incidents"""
    
    @staticmethod
    def analyser_incident(incident):
        """Analyse d'un incident : vraie IA si disponible, sinon analyse automatique sans IA (signalée comme telle).
        Aucun « score de confiance » n'est inventé : ia_score_confiance reste à 0."""
        try:
            response = IncidentIAService._appel_api_ia(incident)
        except Exception as e:
            current_app.logger.info(f"Analyse IA indisponible pour l'incident {incident.id} : {e}")
            response = IncidentIAService._get_analyse_fallback(incident)
        incident.analyse_ia = json.dumps(response, ensure_ascii=False)
        incident.ia_score_confiance = 0
        incident.ia_recommandations = json.dumps(response.get('recommandations', []), ensure_ascii=False)
        return response

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
    def _appel_api_ia(incident):
        """Vrai appel à l'IA (egalyx.ia_moteur). Lève une exception si l'IA n'est pas disponible."""
        if moteur is None:
            raise RuntimeError("module IA absent")
        donnees = {'titre': incident.titre, 'description': moteur.texte(incident.description, 3000),
                   'type_declare': incident.type_incident, 'gravite_declaree': incident.gravite,
                   'statut': incident.statut, 'cause_racine_connue': moteur.texte(incident.cause_racine, 800) or None,
                   'actions_deja_menees': moteur.texte(incident.actions_correctives, 800) or None,
                   'service': incident.service_associe, 'direction': incident.direction_associee,
                   'cout_estime': incident.cout_estime, 'temps_arret_heures': incident.temps_arret,
                   'date_occurrence': incident.date_occurrence}
        r = moteur.demander_json(CONSIGNES_INCIDENT, donnees, max_tokens=900)
        cl = r.get('classification') if isinstance(r.get('classification'), dict) else {}
        return {
            'classification': {'type': moteur.texte(cl.get('type'), 60) or incident.type_incident,
                               'gravite': moteur.texte(cl.get('gravite'), 20) or incident.gravite},
            'causes_probables': moteur.liste_textes(r.get('causes_probables'), 3, 300),
            'recommandations': moteur.liste_textes(r.get('recommandations'), 4, 300),
            'delai_estime': moteur.texte(r.get('delai_estime'), 80) or 'Non estimable',
            'informations_manquantes': moteur.liste_textes(r.get('informations_manquantes'), 3, 200),
            'origine': 'ia', 'modele': moteur.modele(),
            'date': datetime.utcnow().isoformat(timespec='seconds'),
        }

    @staticmethod
    def _get_analyse_fallback(incident):
        """Analyse automatique SANS IA : règles simples, clairement signalée à l'écran."""
        if moteur is not None:
            moteur.marquer(moteur.AUTO)
        recos = []
        if not incident.cause_racine:
            recos.append("Identifier et documenter la cause racine de l'incident")
        if not incident.actions_correctives:
            recos.append("Définir des actions correctives avec un responsable et une échéance")
        if incident.gravite in ('critique', 'elevee'):
            recos.append("Informer la hiérarchie et vérifier si une escalade est nécessaire")
        if not incident.risque_id:
            recos.append("Rattacher l'incident au risque de la cartographie concerné")
        return {
            'classification': {'type': incident.type_incident, 'gravite': incident.gravite},
            'causes_probables': [],
            'recommandations': recos or ["Suivre la résolution et clôturer l'incident une fois les actions vérifiées"],
            'delai_estime': 'Non estimé',
            'origine': 'automatique', 'mode': 'fallback',
            'date': datetime.utcnow().isoformat(timespec='seconds'),
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
            types = ", ".join(str(t[0]) for t in types_frequents[:2] if t and t[0]) or "non renseignés"
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
        suggestions['origine'] = analyse.get('origine') or ('ia' if analyse.get('modele') else 'automatique')
        suggestions['commentaire_cloture'] = ("Pistes proposées par l'IA, à valider par un responsable." if analyse.get('origine') == 'ia'
                                              else "Pistes proposées par l'analyse automatique (sans IA), à valider par un responsable.")
        
        return suggestions
