# services/ia_cartographie_service.py
import os
import json
import random
from datetime import datetime
from openai import OpenAI
from flask import current_app, session

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
client = None

if OPENAI_API_KEY and OPENAI_API_KEY != "mode-simulation" and OPENAI_API_KEY.startswith("sk-") and len(OPENAI_API_KEY) >= 30:  # toutes les clés OpenAI actuelles (sk-proj-…, sk-svcacct-…)
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        print("✅ OpenAI client initialisé pour Cartographie IA")
    except Exception as e:
        print(f"⚠️ Erreur initialisation OpenAI: {e}")
        client = None


class IACartographieService:
    """Service d'IA pour l'analyse intelligente des cartographies"""

    @staticmethod
    def _is_ia_available():
        return client is not None

    @staticmethod
    def analyser_cartographie(cartographie_data):
        """
        Analyse complète d'une cartographie avec IA
        
        Args:
            cartographie_data: dict contenant les données de la cartographie
        
        Returns:
            dict: Analyse complète avec suggestions et recommandations
        """
        
        # Si l'IA est disponible, utiliser OpenAI
        if IACartographieService._is_ia_available():
            return IACartographieService._analyser_avec_openai(cartographie_data)
        else:
            # Sinon, utiliser l'analyse locale
            return IACartographieService._analyser_localement(cartographie_data)

    @staticmethod
    def _analyser_avec_openai(cartographie_data):
        """Analyse avec OpenAI - Version avancée"""
        try:
            # Construire le prompt
            prompt = IACartographieService._construire_prompt(cartographie_data)
            
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": """Tu es un expert en gestion des risques et analyse de cartographie des risques.
                    Tu analyses les données d'une cartographie et tu fournis des recommandations stratégiques.
                    Tu dois être précis, pragmatique et orienté action.
                    Réponds au format JSON valide avec les clés suivantes:
                    - score_global: nombre (0-100)
                    - niveau: string (excellent/bon/moyen/faible)
                    - message: string (résumé de l'analyse)
                    - suggestions: liste d'objets avec titre, description, priorite (critical/high/medium/low), actions_conseillees
                    - statistiques: objet avec les statistiques clés
                    - risques_proposes: liste de risques suggérés si la cartographie est vide"""},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=2000,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            return result
            
        except Exception as e:
            print(f"❌ Erreur OpenAI: {e}")
            # Fallback vers l'analyse locale
            return IACartographieService._analyser_localement(cartographie_data)

    @staticmethod
    def _construire_prompt(cartographie_data):
        """Construit le prompt pour OpenAI"""
        return f"""
        Analyse la cartographie suivante et fournis des recommandations stratégiques :
        
        NOM: {cartographie_data.get('nom', 'Non défini')}
        DESCRIPTION: {cartographie_data.get('description', 'Non définie')}
        
        STATISTIQUES:
        - Nombre total de risques: {cartographie_data.get('total_risques', 0)}
        - Risques évalués: {cartographie_data.get('risques_evalues', 0)}
        - Taux d'évaluation: {cartographie_data.get('taux_evaluation', 0)}%
        - Dispositifs de maîtrise: {cartographie_data.get('total_dispositifs', 0)}
        - Taux de couverture: {cartographie_data.get('taux_couverture', 0)}%
        - Incidents récents: {cartographie_data.get('incidents_recents', 0)}
        
        DISTRIBUTION DES NIVEAUX:
        {json.dumps(cartographie_data.get('distribution_niveaux', {}), indent=2)}
        
        CATÉGORIES:
        {json.dumps(cartographie_data.get('categories', {}), indent=2)}
        
        TYPES DE RISQUES:
        {json.dumps(cartographie_data.get('types', {}), indent=2)}
        
        RISQUES CRITIQUES:
        {json.dumps(cartographie_data.get('risques_critiques', []), indent=2)}
        
        Questions à analyser:
        1. Quels sont les points forts et les points faibles de cette cartographie ?
        2. Quelles sont les principales lacunes à combler ?
        3. Quelles actions prioritaires recommanderais-tu ?
        4. Si la cartographie est vide (0 risque), propose des risques pertinents.
        
        IMPORTANT: 
        - Sois pragmatique et orienté action
        - Propose des suggestions concrètes avec des priorités
        - Si la cartographie est vide, propose 5-8 risques pertinents
        """

    @staticmethod
    def _analyser_localement(cartographie_data):
        """Analyse locale - Version sans OpenAI"""
        
        total_risques = cartographie_data.get('total_risques', 0)
        
        # Si la cartographie est vide, proposer des risques
        if total_risques == 0:
            return IACartographieService._generer_risques_par_defaut(cartographie_data)
        
        # Sinon, analyse standard
        suggestions = []
        
        # 1. Risques critiques sans dispositif
        risques_critiques = cartographie_data.get('risques_critiques', [])
        if risques_critiques:
            nb_risques = len(risques_critiques)
            suggestions.append({
                'id': 'suggestion_1',
                'titre': f"🛡️ {nb_risques} risque(s) critique(s) sans dispositif",
                'description': 'Ces risques ont un niveau critique mais ne disposent d\'aucun dispositif de maîtrise.',
                'priorite': 'critical',
                'icone': 'fa-shield-alt',
                'actions_conseillees': ['Créer des dispositifs de maîtrise', 'Planifier des audits spécifiques']
            })
        
        # 2. Taux d'évaluation faible
        taux_evaluation = cartographie_data.get('taux_evaluation', 0)
        if taux_evaluation < 50:
            suggestions.append({
                'id': 'suggestion_2',
                'titre': f"📊 Taux d'évaluation faible ({taux_evaluation}%)",
                'description': 'Seulement une partie des risques a été évaluée. Une évaluation complète est nécessaire.',
                'priorite': 'high',
                'icone': 'fa-chart-bar',
                'actions_conseillees': ['Évaluer tous les risques', 'Prioriser les risques critiques']
            })
        
        # 3. Incidents récents
        incidents_recents = cartographie_data.get('incidents_recents', 0)
        if incidents_recents > 0:
            suggestions.append({
                'id': 'suggestion_3',
                'titre': f"⚠️ {incidents_recents} incident(s) récent(s)",
                'description': 'Des incidents ont été enregistrés récemment. Une analyse approfondie est recommandée.',
                'priorite': 'high',
                'icone': 'fa-exclamation-triangle',
                'actions_conseillees': ['Analyser les incidents', 'Renforcer les contrôles']
            })
        
        # 4. Couverture des catégories
        categories = cartographie_data.get('categories', {})
        if len(categories) < 3:
            categories_manquantes = ['Financier', 'Opérationnel', 'Réglementaire', 'Stratégique', 'Réputationnel']
            suggestions.append({
                'id': 'suggestion_4',
                'titre': '🔍 Catégories insuffisantes',
                'description': f'Seulement {len(categories)} catégorie(s) couverte(s). Diversifiez votre cartographie.',
                'priorite': 'medium',
                'icone': 'fa-search',
                'actions_conseillees': ['Ajouter des risques dans de nouvelles catégories']
            })
        
        # 5. Score global
        score_global = IACartographieService._calculer_score_global(cartographie_data)
        
        return {
            'score_global': score_global,
            'niveau': score_global['niveau'],
            'message': score_global['message'],
            'suggestions': suggestions,
            'statistiques': {
                'total_risques': total_risques,
                'risques_evalues': cartographie_data.get('risques_evalues', 0),
                'taux_evaluation': cartographie_data.get('taux_evaluation', 0),
                'total_dispositifs': cartographie_data.get('total_dispositifs', 0),
                'taux_couverture': cartographie_data.get('taux_couverture', 0)
            },
            'risques_proposes': []
        }

    @staticmethod
    def _generer_risques_par_defaut(cartographie_data):
        """Génère des risques par défaut pour une cartographie vide"""
        
        risques_proposes = [
            {
                'reference': 'RISK-001',
                'intitule': 'Rupture d\'approvisionnement critique',
                'description': 'Dépendance excessive à un fournisseur unique pour des matières premières essentielles.',
                'categorie': 'Operationnel',
                'type_risque': 'Externe',
                'impact_propose': 4,
                'probabilite_propose': 3
            },
            {
                'reference': 'RISK-002',
                'intitule': 'Cyberattaque sur les systèmes d\'information',
                'description': 'Les systèmes d\'information sont vulnérables aux attaques de type ransomware ou phishing.',
                'categorie': 'Informatique',
                'type_risque': 'Externe',
                'impact_propose': 5,
                'probabilite_propose': 4
            },
            {
                'reference': 'RISK-003',
                'intitule': 'Non-conformité réglementaire',
                'description': 'Risque de non-respect des nouvelles réglementations sectorielles.',
                'categorie': 'Reglementaire',
                'type_risque': 'Reglementaire',
                'impact_propose': 4,
                'probabilite_propose': 4
            },
            {
                'reference': 'RISK-004',
                'intitule': 'Départ de talents clés',
                'description': 'Risque de perte de compétences critiques suite au départ de collaborateurs clés.',
                'categorie': 'RH',
                'type_risque': 'Interne',
                'impact_propose': 3,
                'probabilite_propose': 4
            },
            {
                'reference': 'RISK-005',
                'intitule': 'Défaillance technique majeure',
                'description': 'Risque de panne ou défaillance des équipements critiques de production.',
                'categorie': 'Operationnel',
                'type_risque': 'Technique',
                'impact_propose': 4,
                'probabilite_propose': 3
            },
            {
                'reference': 'RISK-006',
                'intitule': 'Image de marque et réputation',
                'description': 'Risque de dégradation de l\'image de marque suite à un scandale ou une mauvaise communication.',
                'categorie': 'Reputationnel',
                'type_risque': 'Externe',
                'impact_propose': 5,
                'probabilite_propose': 2
            },
            {
                'reference': 'RISK-007',
                'intitule': 'Fluctuation des taux de change',
                'description': 'Impact des variations des devises sur les marges et la compétitivité.',
                'categorie': 'Financier',
                'type_risque': 'Externe',
                'impact_propose': 3,
                'probabilite_propose': 4
            }
        ]
        
        return {
            'score_global': {
                'score': 10,
                'niveau': 'faible',
                'niveau_label': 'Faible',
                'message': 'Cartographie vide. Nous vous proposons des risques pour démarrer.'
            },
            'niveau': 'faible',
            'message': 'Cartographie vide. Commencez par ajouter des risques.',
            'suggestions': [
                {
                    'id': 'suggestion_start',
                    'titre': '🚀 Démarrer votre cartographie des risques',
                    'description': 'Votre cartographie est vide. Voici des risques suggérés pour vous lancer.',
                    'priorite': 'critical',
                    'icone': 'fa-rocket',
                    'actions_conseillees': ['Ajouter les risques proposés', 'Commencer les évaluations']
                }
            ],
            'statistiques': {
                'total_risques': 0,
                'risques_evalues': 0,
                'taux_evaluation': 0,
                'total_dispositifs': 0,
                'taux_couverture': 0
            },
            'risques_proposes': risques_proposes
        }

    @staticmethod
    def _calculer_score_global(cartographie_data):
        """Calcule le score global de la cartographie"""
        
        total_risques = cartographie_data.get('total_risques', 0)
        if total_risques == 0:
            return {
                'score': 0,
                'niveau': 'faible',
                'niveau_label': 'Faible',
                'message': 'Cartographie vide'
            }
        
        score = 0
        
        # Taux d'évaluation (30%)
        taux_evaluation = cartographie_data.get('taux_evaluation', 0)
        score += taux_evaluation * 0.3
        
        # Taux de couverture dispositifs (25%)
        taux_couverture = cartographie_data.get('taux_couverture', 0)
        score += min(taux_couverture * 0.25, 25)
        
        # Incidents (20%)
        incidents = cartographie_data.get('incidents_recents', 0)
        if incidents == 0:
            score += 20
        else:
            score += max(0, 20 - (incidents * 2))
        
        # Diversité des catégories (15%)
        categories = cartographie_data.get('categories', {})
        if len(categories) >= 5:
            score += 15
        elif len(categories) >= 3:
            score += 10
        elif len(categories) >= 1:
            score += 5
        
        # Niveaux (10%)
        niveaux = cartographie_data.get('distribution_niveaux', {})
        critiques = niveaux.get('Critique', 0)
        if critiques == 0:
            score += 10
        elif critiques <= 2:
            score += 5
        else:
            score += 2
        
        score_final = int(score)
        
        if score_final >= 80:
            return {'score': score_final, 'niveau': 'excellent', 'niveau_label': 'Excellent', 'message': 'Cartographie très mature'}
        elif score_final >= 60:
            return {'score': score_final, 'niveau': 'bon', 'niveau_label': 'Bon', 'message': 'Cartographie satisfaisante'}
        elif score_final >= 40:
            return {'score': score_final, 'niveau': 'moyen', 'niveau_label': 'Moyen', 'message': 'Cartographie perfectible'}
        else:
            return {'score': score_final, 'niveau': 'faible', 'niveau_label': 'Faible', 'message': 'Cartographie à améliorer'}