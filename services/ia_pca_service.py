# services/ia_pca_service.py
import os
import json
from flask import current_app
from datetime import datetime, timedelta

try:
    from egalyx import ia_moteur as moteur
except ImportError:                                    # installation sans le module commun
    moteur = None

class IAPcaService:
    """Service d'IA pour le module PCA"""

    @staticmethod
    def _is_ia_available():
        return bool(moteur and moteur.disponible())

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


# ============================================================================================
# Suggestions : vraie IA d'abord ; sinon les règles ci-dessus, signalées comme « automatiques ».
# ============================================================================================
CONSIGNES_PCA = """Tu es un expert en continuité d'activité (ISO 22301). On te donne l'état d'un plan de continuité d'activité (PCA).
Propose des suggestions concrètes et propres À CE PLAN, fondées uniquement sur les données (lacunes, maturité, tests).
Ne répète pas les éléments déjà existants. Français professionnel."""
PHASES = ('preparation', 'crise', 'reprise', 'retour', 'test')
TYPES_EXERCICE = ('table_top', 'technique', 'grandeur_nature')


def _donnees(plan_data, existants):
    d = {k: v for k, v in (plan_data or {}).items()}
    d['deja_existants'] = existants
    return d


def _ia_actions(plan_data, existants):
    if moteur is None:
        return None
    try:
        r = moteur.demander_json(CONSIGNES_PCA + """
Réponds {"actions": [{"titre": "...", "description": "1 à 2 phrases", "phase": "preparation|crise|reprise|retour|test",
"priorite": "haute|moyenne|basse", "delai_suggere": "ex. 30 jours"}]} avec 3 à 5 actions, la plus urgente d'abord.""",
                                 _donnees(plan_data, existants), max_tokens=1100)
    except moteur.IndisponibleIA:
        return None
    res, vus = [], {e.lower() for e in existants}
    for a in (r.get('actions') or [])[:5]:
        if isinstance(a, dict) and moteur.texte(a.get('titre')) and moteur.texte(a.get('titre')).lower() not in vus:
            phase = moteur.texte(a.get('phase'), 20).lower()
            res.append({'titre': moteur.texte(a.get('titre'), 180), 'description': moteur.texte(a.get('description'), 500),
                        'phase': phase if phase in PHASES else 'preparation', 'priorite': moteur.priorite(a.get('priorite')),
                        'delai_suggere': moteur.texte(a.get('delai_suggere'), 40) or '30 jours'})
    return res or None


def _ia_exercices(plan_data, existants):
    if moteur is None:
        return None
    try:
        r = moteur.demander_json(CONSIGNES_PCA + """
Propose 2 ou 3 exercices de test adaptés au niveau de maturité et aux dates de test.
Réponds {"exercices": [{"titre": "...", "description": "1 à 2 phrases", "type": "table_top|technique|grandeur_nature",
"duree_suggeree": "ex. 4 heures", "objectifs": ["...", "..."]}]}""", _donnees(plan_data, existants), max_tokens=1100)
    except moteur.IndisponibleIA:
        return None
    res, vus = [], {e.lower() for e in existants}
    for e in (r.get('exercices') or [])[:3]:
        if isinstance(e, dict) and moteur.texte(e.get('titre')) and moteur.texte(e.get('titre')).lower() not in vus:
            t = moteur.texte(e.get('type'), 20).lower()
            res.append({'titre': moteur.texte(e.get('titre'), 180), 'description': moteur.texte(e.get('description'), 500),
                        'type': t if t in TYPES_EXERCICE else 'table_top',
                        'duree_suggeree': moteur.texte(e.get('duree_suggeree'), 40) or '4 heures',
                        'objectifs': moteur.liste_textes(e.get('objectifs'), 5, 200)})
    return res or None


def _auto():
    if moteur is not None:
        moteur.marquer(moteur.AUTO)


_regles_actions = IAPcaService.suggerer_actions
_regles_exercices = IAPcaService.suggerer_exercices
_regles_actions_spec = IAPcaService.suggerer_actions_specifiques
_regles_exercices_spec = IAPcaService.suggerer_exercices_specifiques


def suggerer_actions(plan_data):
    res = _ia_actions(plan_data, [])
    if res:
        return [{**a, 'categorie': a['phase']} for a in res]
    _auto()
    return _regles_actions(plan_data)


def suggerer_exercices(plan_data):
    res = _ia_exercices(plan_data, [])
    if res:
        return res
    _auto()
    return _regles_exercices(plan_data)


def suggerer_actions_specifiques(plan_data, existing_actions=None):
    res = _ia_actions(plan_data, [a.intitule for a in (existing_actions or []) if getattr(a, 'intitule', None)])
    if res:
        return res
    _auto()
    return _regles_actions_spec(plan_data, existing_actions)


def suggerer_exercices_specifiques(plan_data, existing_exercices=None):
    res = _ia_exercices(plan_data, [e.nom for e in (existing_exercices or []) if getattr(e, 'nom', None)])
    if res:
        return [{**e, 'objectifs': "\n".join(e['objectifs'])} for e in res]
    _auto()
    return _regles_exercices_spec(plan_data, existing_exercices)


IAPcaService.suggerer_actions = staticmethod(suggerer_actions)
IAPcaService.suggerer_exercices = staticmethod(suggerer_exercices)
IAPcaService.suggerer_actions_specifiques = staticmethod(suggerer_actions_specifiques)
IAPcaService.suggerer_exercices_specifiques = staticmethod(suggerer_exercices_specifiques)
