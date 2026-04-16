# services/ia_pca_service.py
import os
import json
import random
from openai import OpenAI
from flask import current_app
from datetime import datetime, timedelta

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
client = None
if OPENAI_API_KEY and OPENAI_API_KEY != "mode-simulation" and not OPENAI_API_KEY.startswith("sk-proj-"):
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        print("✅ OpenAI client initialisé pour PCA")
    except Exception as e:
        print(f"⚠️ Erreur initialisation OpenAI PCA: {e}")
        client = None

class IAPcaService:
    """Service d'IA pour le module PCA"""

    @staticmethod
    def _is_ia_available():
        return client is not None

    @staticmethod
    def calculer_score_efficacite(plan_data):
        """
        Calcule un score d'efficacité IA basé sur les données du plan PCA
        Score de 0 à 100
        """
        score = 0
        details = []
        
        # 1. BIA réalisée (20 points)
        if plan_data.get('bia_realisee'):
            score += 20
            details.append({"categorie": "BIA", "points": 20, "max": 20, "statut": "ok"})
        else:
            details.append({"categorie": "BIA", "points": 0, "max": 20, "statut": "warning", "message": "BIA non réalisée"})
        
        # 2. Définition des RTO/RPO (15 points)
        if plan_data.get('delai_arret_max') and plan_data.get('perte_donnees_max'):
            score += 15
            details.append({"categorie": "RTO/RPO", "points": 15, "max": 15, "statut": "ok"})
        elif plan_data.get('delai_arret_max') or plan_data.get('perte_donnees_max'):
            score += 8
            details.append({"categorie": "RTO/RPO", "points": 8, "max": 15, "statut": "warning", "message": "RTO ou RPO manquant"})
        else:
            details.append({"categorie": "RTO/RPO", "points": 0, "max": 15, "statut": "danger", "message": "Aucun objectif défini"})
        
        # 3. Processus critiques (10 points)
        processus = plan_data.get('processus_critiques', [])
        if processus:
            nb_processus = len(processus)
            if nb_processus >= 5:
                score += 10
                details.append({"categorie": "Processus critiques", "points": 10, "max": 10, "statut": "ok"})
            elif nb_processus >= 3:
                score += 7
                details.append({"categorie": "Processus critiques", "points": 7, "max": 10, "statut": "warning", "message": f"{nb_processus} processus définis"})
            else:
                score += 4
                details.append({"categorie": "Processus critiques", "points": 4, "max": 10, "statut": "warning", "message": f"{nb_processus} processus définis (minimum recommandé: 5)"})
        else:
            details.append({"categorie": "Processus critiques", "points": 0, "max": 10, "statut": "danger", "message": "Aucun processus critique défini"})
        
        # 4. Stratégies de continuité (10 points)
        strategies = plan_data.get('strategies', [])
        if strategies:
            nb_strategies = len(strategies)
            if nb_strategies >= 3:
                score += 10
                details.append({"categorie": "Stratégies", "points": 10, "max": 10, "statut": "ok"})
            else:
                score += 5
                details.append({"categorie": "Stratégies", "points": 5, "max": 10, "statut": "warning", "message": f"{nb_strategies} stratégie(s) définie(s)"})
        else:
            details.append({"categorie": "Stratégies", "points": 0, "max": 10, "statut": "danger", "message": "Aucune stratégie définie"})
        
        # 5. Sites de secours (10 points)
        sites = plan_data.get('sites_secours', [])
        if sites:
            nb_sites = len(sites)
            if nb_sites >= 2:
                score += 10
                details.append({"categorie": "Sites de secours", "points": 10, "max": 10, "statut": "ok"})
            else:
                score += 5
                details.append({"categorie": "Sites de secours", "points": 5, "max": 10, "statut": "warning", "message": f"{nb_sites} site(s) défini(s)"})
        else:
            details.append({"categorie": "Sites de secours", "points": 0, "max": 10, "statut": "danger", "message": "Aucun site de secours défini"})
        
        # 6. Procédures (15 points)
        has_urgence = bool(plan_data.get('procedures_urgence'))
        has_reprise = bool(plan_data.get('procedures_reprise'))
        has_retour = bool(plan_data.get('procedures_retour_normal'))
        
        nb_procedures = sum([has_urgence, has_reprise, has_retour])
        if nb_procedures == 3:
            score += 15
            details.append({"categorie": "Procédures", "points": 15, "max": 15, "statut": "ok"})
        elif nb_procedures == 2:
            score += 10
            details.append({"categorie": "Procédures", "points": 10, "max": 15, "statut": "warning", "message": "Procédures incomplètes"})
        elif nb_procedures == 1:
            score += 5
            details.append({"categorie": "Procédures", "points": 5, "max": 15, "statut": "warning", "message": "Une seule procédure définie"})
        else:
            details.append({"categorie": "Procédures", "points": 0, "max": 15, "statut": "danger", "message": "Aucune procédure définie"})
        
        # 7. Ressources critiques (10 points)
        ressources = plan_data.get('ressources_critiques', [])
        if ressources:
            nb_ressources = len(ressources)
            if nb_ressources >= 5:
                score += 10
                details.append({"categorie": "Ressources", "points": 10, "max": 10, "statut": "ok"})
            else:
                score += 5
                details.append({"categorie": "Ressources", "points": 5, "max": 10, "statut": "warning", "message": f"{nb_ressources} ressource(s) définie(s)"})
        else:
            details.append({"categorie": "Ressources", "points": 0, "max": 10, "statut": "danger", "message": "Aucune ressource critique définie"})
        
        # 8. Tests et exercices (10 points)
        a_test = bool(plan_data.get('date_dernier_test'))
        a_prochain_test = bool(plan_data.get('date_prochain_test'))
        
        if a_test and a_prochain_test:
            score += 10
            details.append({"categorie": "Tests", "points": 10, "max": 10, "statut": "ok"})
        elif a_test or a_prochain_test:
            score += 5
            details.append({"categorie": "Tests", "points": 5, "max": 10, "statut": "warning", "message": "Tests partiellement planifiés"})
        else:
            details.append({"categorie": "Tests", "points": 0, "max": 10, "statut": "danger", "message": "Aucun test planifié"})
        
        # Niveau de maturité
        niveau_maturite = int(plan_data.get('niveau_maturite', 3))
        
        # Ajustement du score selon le niveau de maturité
        maturite_ajustement = {
            1: -5,
            2: 0,
            3: 5,
            4: 10,
            5: 15
        }.get(niveau_maturite, 0)
        
        score = min(100, max(0, score + maturite_ajustement))
        
        # Déterminer la classe CSS et le message
        if score >= 80:
            niveau = "excellent"
            couleur = "success"
            message = "Plan PCA très mature et complet"
        elif score >= 60:
            niveau = "bon"
            couleur = "primary"
            message = "Plan PCA satisfaisant, quelques points d'amélioration"
        elif score >= 40:
            niveau = "moyen"
            couleur = "warning"
            message = "Plan PCA perfectible, des actions correctives nécessaires"
        else:
            niveau = "faible"
            couleur = "danger"
            message = "Plan PCA insuffisant, une refonte est recommandée"
        
        return {
            'score': score,
            'niveau': niveau,
            'couleur': couleur,
            'message': message,
            'details': details
        }

    @staticmethod
    def suggerer_actions(plan_data):
        """Suggère des actions d'amélioration basées sur les faiblesses détectées"""
        suggestions = []
        
        # Analyse des faiblesses
        if not plan_data.get('bia_realisee'):
            suggestions.append({
                'titre': 'Réaliser une analyse d\'impact (BIA)',
                'description': 'Une BIA est essentielle pour identifier les processus critiques et définir les objectifs de reprise (RTO/RPO).',
                'priorite': 'haute',
                'delai_suggere': '30 jours',
                'categorie': 'bia'
            })
        
        if not plan_data.get('delai_arret_max') or not plan_data.get('perte_donnees_max'):
            suggestions.append({
                'titre': 'Définir les objectifs RTO et RPO',
                'description': 'Formalisez les délais d\'arrêt maximaux admissibles (RTO) et les pertes de données acceptables (RPO) pour chaque processus critique.',
                'priorite': 'haute',
                'delai_suggere': '15 jours',
                'categorie': 'rto_rpo'
            })
        
        processus = plan_data.get('processus_critiques', [])
        if len(processus) < 3:
            suggestions.append({
                'titre': 'Identifier davantage de processus critiques',
                'description': f'Actuellement {len(processus)} processus critiques identifiés. Une cartographie plus exhaustive est recommandée (minimum 5 processus).',
                'priorite': 'moyenne',
                'delai_suggere': '45 jours',
                'categorie': 'processus'
            })
        
        strategies = plan_data.get('strategies', [])
        if len(strategies) < 2:
            suggestions.append({
                'titre': 'Diversifier les stratégies de continuité',
                'description': 'Envisagez plusieurs options : site de secours, télétravail, mutualisation, cloud, etc.',
                'priorite': 'moyenne',
                'delai_suggere': '60 jours',
                'categorie': 'strategies'
            })
        
        if not plan_data.get('procedures_urgence') or not plan_data.get('procedures_reprise'):
            suggestions.append({
                'titre': 'Compléter les procédures opérationnelles',
                'description': 'Formalisez les procédures d\'urgence, de reprise et de retour à la normale pour chaque scénario identifié.',
                'priorite': 'haute',
                'delai_suggere': '30 jours',
                'categorie': 'procedures'
            })
        
        if not plan_data.get('date_prochain_test'):
            suggestions.append({
                'titre': 'Planifier un exercice de test',
                'description': 'Programmez un test de votre plan PCA pour valider son efficacité et former les équipes.',
                'priorite': 'haute',
                'delai_suggere': '90 jours',
                'categorie': 'tests'
            })
        
        ressources = plan_data.get('ressources_critiques', [])
        if len(ressources) < 3:
            suggestions.append({
                'titre': 'Identifier les ressources critiques manquantes',
                'description': 'Listez les équipements, logiciels, données et compétences indispensables à la reprise.',
                'priorite': 'moyenne',
                'delai_suggere': '30 jours',
                'categorie': 'ressources'
            })
        
        return suggestions[:5]

    @staticmethod
    def suggerer_exercices(plan_data):
        """Suggère des exercices de test adaptés au plan"""
        
        niveau_maturite = int(plan_data.get('niveau_maturite', 3))
        
        exercices = []
        
        # Exercice de base - Tabletop
        exercices.append({
            'titre': 'Exercice Tabletop - Validation des procédures',
            'type': 'table_top',
            'description': 'Exercice sur table pour valider la compréhension des procédures par les équipes et identifier les lacunes documentaires.',
            'duree_suggeree': '4 heures',
            'objectifs': [
                'Valider la compréhension des rôles et responsabilités',
                'Tester la cohérence des procédures',
                'Identifier les dépendances critiques'
            ]
        })
        
        # Exercice technique selon le niveau
        if niveau_maturite >= 2:
            exercices.append({
                'titre': 'Exercice technique - Reprise partielle',
                'type': 'technique',
                'description': 'Exercice technique ciblé sur la reprise d\'un processus critique spécifique.',
                'duree_suggeree': '8 heures',
                'objectifs': [
                    'Tester la restauration d\'un service critique',
                    'Valider les procédures de reprise technique',
                    'Mesurer le temps effectif de reprise'
                ]
            })
        
        # Exercice grandeur nature pour les plans matures
        if niveau_maturite >= 4:
            exercices.append({
                'titre': 'Exercice grandeur nature - Simulation crise majeure',
                'type': 'grandeur_nature',
                'description': 'Exercice complet impliquant toutes les équipes et simulant une crise majeure.',
                'duree_suggeree': '24 heures',
                'objectifs': [
                    'Tester l\'ensemble du plan PCA en conditions réelles',
                    'Évaluer la coordination inter-équipes',
                    'Valider les délais de reprise (RTO/RPO)',
                    'Former les équipes en situation de crise'
                ]
            })
        
        # Exercice complémentaire
        exercices.append({
            'titre': 'Exercice de reprise informatique',
            'type': 'technique',
            'description': 'Exercice ciblé sur la reprise des systèmes d\'information et des données critiques.',
            'duree_suggeree': '12 heures',
            'objectifs': [
                'Tester la restauration des serveurs et données',
                'Valider les RPO (perte de données acceptable)',
                'Vérifier la disponibilité des sauvegardes'
            ]
        })
        
        return exercices[:3]

    @staticmethod
    def analyser_plan_complet(plan_data):
        """Analyse complète du plan PCA"""
        
        score = IAPcaService.calculer_score_efficacite(plan_data)
        actions = IAPcaService.suggerer_actions(plan_data)
        exercices = IAPcaService.suggerer_exercices(plan_data)
        
        # Recommandation globale
        if score['score'] >= 80:
            recommandation = "Votre plan PCA est mature. Concentrez-vous sur les exercices périodiques et l'amélioration continue."
        elif score['score'] >= 60:
            recommandation = "Votre plan est satisfaisant mais présente des points d'amélioration. Priorisez les actions haute priorité."
        elif score['score'] >= 40:
            recommandation = "Votre plan nécessite des améliorations significatives. Commencez par combler les lacunes critiques."
        else:
            recommandation = "Votre plan est insuffisant. Une refonte complète est recommandée en suivant les suggestions ci-dessus."
        
        return {
            'score': score,
            'actions': actions,
            'exercices': exercices,
            'recommandation': recommandation
        }

    # services/ia_pca_service.py - Ajoutez ces méthodes

    @staticmethod
    def suggerer_actions_specifiques(plan_data, existing_actions=None):
        """Suggère des actions spécifiques pour le plan PCA"""
        
        existing_titles = [a.intitule.lower() for a in (existing_actions or [])]
        
        suggestions = []
        
        # Vérifier les lacunes
        if not plan_data.get('bia_realisee'):
            suggestions.append({
                'titre': 'Réaliser une analyse d\'impact (BIA)',
                'description': 'La BIA est essentielle pour identifier les processus critiques et définir les objectifs de reprise.',
                'phase': 'preparation',
                'priorite': 'haute',
                'delai_suggere': '30 jours'
            })
        
        if not plan_data.get('delai_arret_max') or not plan_data.get('perte_donnees_max'):
            suggestions.append({
                'titre': 'Définir les objectifs RTO et RPO',
                'description': 'Formalisez les délais d\'arrêt maximaux admissibles (RTO) et les pertes de données acceptables (RPO).',
                'phase': 'preparation',
                'priorite': 'haute',
                'delai_suggere': '15 jours'
            })
        
        processus_count = len(plan_data.get('processus_critiques', []))
        if processus_count < 3:
            suggestions.append({
                'titre': 'Identifier les processus critiques manquants',
                'description': f'Seulement {processus_count} processus critiques identifiés. Cartographiez au moins 5 processus essentiels.',
                'phase': 'preparation',
                'priorite': 'moyenne',
                'delai_suggere': '45 jours'
            })
        
        strategies_count = len(plan_data.get('strategies', []))
        if strategies_count < 2:
            suggestions.append({
                'titre': 'Diversifier les stratégies de continuité',
                'description': 'Envisagez plusieurs options : site de secours, télétravail, cloud, mutualisation.',
                'phase': 'crise',
                'priorite': 'moyenne',
                'delai_suggere': '60 jours'
            })
        
        if not plan_data.get('procedures_urgence') or not plan_data.get('procedures_reprise'):
            suggestions.append({
                'titre': 'Formaliser les procédures opérationnelles',
                'description': 'Rédigez les procédures d\'urgence, de reprise et de retour à la normale.',
                'phase': 'crise',
                'priorite': 'haute',
                'delai_suggere': '30 jours'
            })
        
        ressources_count = len(plan_data.get('ressources_critiques', []))
        if ressources_count < 3:
            suggestions.append({
                'titre': 'Identifier les ressources critiques',
                'description': f'Seulement {ressources_count} ressources identifiées. Listez équipements, logiciels et données indispensables.',
                'phase': 'preparation',
                'priorite': 'moyenne',
                'delai_suggere': '30 jours'
            })
        
        if not plan_data.get('date_prochain_test'):
            suggestions.append({
                'titre': 'Planifier un test du plan PCA',
                'description': 'Programmez un exercice de test pour valider l\'efficacité du plan et former les équipes.',
                'phase': 'test',
                'priorite': 'haute',
                'delai_suggere': '90 jours'
            })
        
        # Filtrer les suggestions déjà existantes
        return [s for s in suggestions if s['titre'].lower() not in existing_titles]

    @staticmethod
    def suggerer_exercices_specifiques(plan_data, existing_exercices=None):
        """Suggère des exercices spécifiques pour le plan PCA"""
        
        existing_names = [e.nom.lower() for e in (existing_exercices or [])]
        niveau_maturite = int(plan_data.get('niveau_maturite', 3))
        
        suggestions = []
        
        # Exercice Tabletop (toujours pertinent)
        suggestions.append({
            'titre': 'Exercice Tabletop - Validation des procédures',
            'description': 'Exercice sur table pour valider la compréhension des procédures par les équipes.',
            'type': 'table_top',
            'duree_suggeree': '4 heures',
            'objectifs': 'Valider la compréhension des rôles\nTester la cohérence des procédures\nIdentifier les dépendances critiques'
        })
        
        # Exercice technique selon le niveau
        if niveau_maturite >= 2:
            suggestions.append({
                'titre': 'Exercice technique - Reprise d\'un service critique',
                'description': 'Exercice technique ciblé sur la reprise d\'un processus critique spécifique.',
                'type': 'technique',
                'duree_suggeree': '8 heures',
                'objectifs': 'Tester la restauration d\'un service critique\nValider les procédures de reprise technique\nMesurer le temps effectif de reprise (RTO)'
            })
        
        # Exercice grandeur nature pour les plans matures
        if niveau_maturite >= 4:
            suggestions.append({
                'titre': 'Exercice grandeur nature - Simulation de crise majeure',
                'description': 'Exercice complet impliquant toutes les équipes et simulant une crise majeure.',
                'type': 'grandeur_nature',
                'duree_suggeree': '24 heures',
                'objectifs': 'Tester l\'ensemble du plan PCA\nÉvaluer la coordination inter-équipes\nValider les délais de reprise (RTO/RPO)\nFormer les équipes en situation de crise'
            })
        
        # Exercice de reprise informatique
        suggestions.append({
            'titre': 'Exercice de reprise des systèmes d\'information',
            'description': 'Exercice ciblé sur la reprise des données et serveurs critiques.',
            'type': 'technique',
            'duree_suggeree': '12 heures',
            'objectifs': 'Tester la restauration des serveurs\nValider les RPO (perte de données)\nVérifier la disponibilité des sauvegardes'
        })
        
        # Filtrer les suggestions déjà existantes
        return [s for s in suggestions if s['titre'].lower() not in existing_names][:3]
