# services/ia_qualite_service.py
import os
import json
import random
from openai import OpenAI
from flask import current_app
from models import PlanQualiteFonction, ActionAmeliorationQualite
from datetime import datetime, timedelta

# Initialisation du client OpenAI (si la clé est disponible)
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
client = None
if OPENAI_API_KEY and OPENAI_API_KEY != "mode-simulation" and not OPENAI_API_KEY.startswith("sk-proj-"):
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        print("✅ OpenAI client initialisé avec succès")
    except Exception as e:
        print(f"⚠️ Erreur initialisation OpenAI: {e}")
        client = None
else:
    print("⚠️ Clé API OpenAI non configurée ou invalide - Mode suggestions standard activé")

class IAQualiteService:
    """Service d'IA pour le module Qualité (suggestions standard + IA si disponible)"""

    @staticmethod
    def _is_ia_available():
        """Vérifie si l'IA est disponible"""
        return client is not None

    # ============================================
    # 1. DESCRIPTION
    # ============================================
    @staticmethod
    def generer_description_plan(plan_data):
        """Génère une description de plan qualité."""
        titre = plan_data.get('titre', '')
        objectifs = plan_data.get('objectifs', [])
        
        # Mode IA
        if IAQualiteService._is_ia_available():
            try:
                prompt = f"""
                Tu es un expert en management de la qualité. Rédige une description professionnelle (2-3 phrases) pour un plan d'assurance et d'amélioration qualité.

                Titre du plan : {titre}
                Objectifs principaux : {', '.join(objectifs) if objectifs else 'Non spécifiés'}

                La description doit être concise et expliquer la valeur ajoutée du plan.
                """
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                    max_tokens=150
                )
                return response.choices[0].message.content.strip()
            except Exception as e:
                current_app.logger.error(f"Erreur IA génération description: {e}")
        
        # Mode standard
        descriptions_standard = [
            f"Ce plan d'assurance et d'amélioration qualité vise à renforcer la maîtrise des processus clés et à garantir la conformité réglementaire. Il s'inscrit dans une démarche d'amélioration continue pour atteindre les objectifs stratégiques définis.",
            f"Le présent plan qualité établit le cadre de référence pour l'assurance qualité préventive et les actions correctives nécessaires. Il définit les indicateurs de performance et les objectifs SMART à atteindre.",
            f"Ce plan d'action qualité structure la démarche d'amélioration continue autour de plusieurs axes prioritaires, combinant mesures préventives et correctives pour garantir l'efficacité du système de management.",
            f"Ce document stratégique définit les orientations qualité pour la période à venir, identifie les risques et opportunités, fixe les objectifs d'amélioration et détaille les actions correctives à mettre en œuvre."
        ]
        
        if objectifs:
            return f"Ce plan qualité vise à atteindre les objectifs suivants : {', '.join(objectifs[:2])}. Il combine des actions préventives d'assurance qualité et des actions correctives d'amélioration continue pour garantir la conformité et la performance des processus."
        
        return random.choice(descriptions_standard)

    # ============================================
    # 2. OBJECTIFS SMART
    # ============================================
    @staticmethod
    def generer_objectifs_smart(titre):
        """Génère des objectifs SMART pour un plan qualité."""
        
        # Mode IA
        if IAQualiteService._is_ia_available():
            try:
                prompt = f"""
                Propose 3 objectifs SMART (Spécifiques, Mesurables, Atteignables, Réalistes, Temporellement définis) pour le plan qualité intitulé : "{titre}".

                Rends UNIQUEMENT une liste JSON valide de 3 chaînes de caractères. Exemple : ["Objectif 1", "Objectif 2", "Objectif 3"]
                """
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.6,
                    response_format={"type": "json_object"}
                )
                data = json.loads(response.choices[0].message.content)
                if isinstance(data, list):
                    return data
                return list(data.values())[0] if data else []
            except Exception as e:
                current_app.logger.error(f"Erreur IA génération objectifs: {e}")
        
        # Mode standard
        objectifs_standard = [
            "Atteindre un taux de conformité de 95% sur l'ensemble des processus critiques d'ici la fin de l'exercice.",
            "Réduire de 30% le nombre de non-conformités majeures dans les 6 prochains mois.",
            "Former 100% du personnel aux nouvelles procédures qualité dans les 3 mois suivant leur validation.",
            "Mettre en place un tableau de bord qualité avec 5 indicateurs clés suivis mensuellement d'ici 3 mois.",
            "Réaliser un audit interne complet du système qualité avant la fin du semestre.",
            "Atteindre un taux de satisfaction client de 85% sur les critères qualité d'ici la fin de l'année.",
            "Formaliser et documenter 100% des processus critiques dans les 4 prochains mois.",
            "Réduire le délai moyen de traitement des réclamations clients à moins de 48 heures d'ici 6 mois."
        ]
        random.shuffle(objectifs_standard)
        return objectifs_standard[:3]

    # ============================================
    # 3. INDICATEURS KPI
    # ============================================
    @staticmethod
    def generer_indicateurs(titre, objectifs):
        """Génère des indicateurs KPI pour un plan qualité."""
        
        # Mode IA
        if IAQualiteService._is_ia_available():
            try:
                prompt = f"""
                Propose 3 indicateurs clés de performance (KPI) pour le plan qualité "{titre}" ayant les objectifs : {', '.join(objectifs) if objectifs else 'Non spécifiés'}.

                Chaque indicateur doit avoir : un nom, une cible, une unité.
                Rends UNIQUEMENT une liste JSON valide au format : [{{"nom": "...", "cible": "...", "unite": "..."}}, ...]
                """
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.6,
                    response_format={"type": "json_object"}
                )
                data = json.loads(response.choices[0].message.content)
                if isinstance(data, list):
                    return data
                return list(data.values())[0] if data else []
            except Exception as e:
                current_app.logger.error(f"Erreur IA génération indicateurs: {e}")
        
        # Mode standard
        indicateurs_standard = [
            {"nom": "Taux de conformité des processus", "cible": "≥ 95%", "unite": "%"},
            {"nom": "Nombre de non-conformités", "cible": "≤ 5 par trimestre", "unite": "nb"},
            {"nom": "Taux de réalisation des actions correctives", "cible": "100% dans les délais", "unite": "%"},
            {"nom": "Délai moyen de traitement des écarts", "cible": "≤ 15 jours", "unite": "jours"},
            {"nom": "Taux de satisfaction client", "cible": "≥ 85%", "unite": "%"},
            {"nom": "Taux de documentation des processus", "cible": "100%", "unite": "%"},
            {"nom": "Taux de participation aux formations qualité", "cible": "100%", "unite": "%"},
            {"nom": "Score d'efficacité des contrôles", "cible": "≥ 4/5", "unite": "/5"}
        ]
        random.shuffle(indicateurs_standard)
        return indicateurs_standard[:3]

    # ============================================
    # 4. NIVEAU DE MATURITÉ
    # ============================================
    @staticmethod
    def suggerer_niveau_maturite(titre):
        """Suggère un niveau de maturité basé sur le titre du plan."""
        
        niveaux = {
            '1': '1 - Initial',
            '2': '2 - Répétable',
            '3': '3 - Défini',
            '4': '4 - Géré',
            '5': '5 - Optimisé'
        }
        
        titre_lower = titre.lower()
        
        # Analyse sémantique simple
        if any(word in titre_lower for word in ['initial', 'démarrage', 'création', 'mise en place']):
            return '1'
        elif any(word in titre_lower for word in ['répétable', 'standard', 'base']):
            return '2'
        elif any(word in titre_lower for word in ['défini', 'structuré', 'formalisé']):
            return '3'
        elif any(word in titre_lower for word in ['géré', 'mesuré', 'piloté', 'performance']):
            return '4'
        elif any(word in titre_lower for word in ['optimisé', 'excellence', 'amélioration continue']):
            return '5'
        
        # Par défaut : niveau 3
        return '3'

    # ============================================
    # 5. SECTION AMÉLIORATION COMPLÈTE
    # ============================================
    @staticmethod
    def generer_section_amelioration(titre):
        """Génère toute la section amélioration (objectifs + indicateurs)."""
        
        objectifs = IAQualiteService.generer_objectifs_smart(titre)
        indicateurs = IAQualiteService.generer_indicateurs(titre, objectifs)
        
        return {
            'objectifs': objectifs,
            'indicateurs': indicateurs
        }

    # ============================================
    # 6. PLAN COMPLET
    # ============================================
    @staticmethod
    def generer_plan_complet(titre):
        """Génère un plan qualité complet avec toutes les sections."""
        
        # Générer tous les éléments
        description = IAQualiteService.generer_description_plan({'titre': titre, 'objectifs': []})
        objectifs = IAQualiteService.generer_objectifs_smart(titre)
        indicateurs = IAQualiteService.generer_indicateurs(titre, objectifs)
        niveau_maturite = IAQualiteService.suggerer_niveau_maturite(titre)
        
        # Suggestions pour l'assurance qualité
        procedures_suggestions = [
            "PRO-001 - Gestion des non-conformités\nPRO-002 - Audit interne\nPRO-003 - Management des risques",
            "PRO-012 - Contrôle des documents\nPRO-045 - Évaluation fournisseurs\nPRO-078 - Traitement des réclamations",
            "Procédure de revue de direction\nProcédure de gestion des compétences\nProcédure de surveillance et mesure"
        ]
        
        documents_suggestions = [
            "Manuel qualité version 2.0\nRéférentiel ISO 9001:2025\nGuide des bonnes pratiques qualité",
            "Documentation du système de management\nMatrice de conformité réglementaire\nPlan d'audit annuel"
        ]
        
        controles_suggestions = [
            "Séparation des tâches\nValidation systématique des documents\nRevue hebdomadaire des indicateurs",
            "Contrôle croisé des dossiers\nAudit qualité mensuel\nRevue de processus trimestrielle"
        ]
        
        frequences = ['mensuel', 'trimestriel', 'semestriel']
        
        # Date de revue suggérée (dans 6 mois)
        date_prochaine_revue = (datetime.now() + timedelta(days=180)).strftime('%Y-%m-%d')
        
        return {
            'description': description,
            'objectifs': objectifs,
            'indicateurs': indicateurs,
            'niveau_maturite': niveau_maturite,
            'procedures': random.choice(procedures_suggestions),
            'documents': random.choice(documents_suggestions),
            'controles': random.choice(controles_suggestions),
            'frequence': random.choice(frequences),
            'date_prochaine_revue': date_prochaine_revue
        }

    # ============================================
    # 7. ANALYSE DE PLAN EXISTANT
    # ============================================
    @staticmethod
    def analyser_plan_qualite(plan_id):
        """Analyse un plan qualité existant et retourne des recommandations."""
        try:
            plan = PlanQualiteFonction.query.get(plan_id)
            if not plan:
                return None

            actions = ActionAmeliorationQualite.query.filter_by(plan_qualite_id=plan_id, is_archived=False).all()
            actions_terminees = sum(1 for a in actions if a.statut == 'terminee')
            progression = (actions_terminees / len(actions) * 100) if actions else 0
            
            a_des_objectifs = plan.objectifs_qualite and len(plan.objectifs_qualite) > 0
            a_des_indicateurs = plan.indicateurs_cles and len(plan.indicateurs_cles) > 0
            a_des_actions = len(actions) > 0
            a_des_actions_en_retard = any(a.est_en_retard() for a in actions)
            a_des_actions_bloquees = any(a.statut == 'bloquee' for a in actions)
            niveau_maturite = int(plan.niveau_maturite) if plan.niveau_maturite else 3
            
            recommendations = []
            
            # Recommandation 1 : objectifs
            if not a_des_objectifs:
                recommendations.append({
                    'titre': 'Définir des objectifs SMART',
                    'description': 'Le plan ne contient pas d\'objectifs qualité mesurables. Définissez des objectifs SMART pour piloter efficacement votre démarche qualité.',
                    'priorite': 'haute'
                })
            
            # Recommandation 2 : indicateurs
            if not a_des_indicateurs:
                recommendations.append({
                    'titre': 'Mettre en place des indicateurs de performance',
                    'description': 'Le plan manque d\'indicateurs clés (KPI). Définissez des indicateurs quantitatifs pour mesurer l\'atteinte de vos objectifs.',
                    'priorite': 'haute'
                })
            
            # Recommandation 3 : actions
            if not a_des_actions:
                recommendations.append({
                    'titre': 'Décliner les objectifs en actions concrètes',
                    'description': 'Aucune action d\'amélioration n\'est définie. Transformez vos objectifs en actions opérationnelles.',
                    'priorite': 'haute'
                })
            elif a_des_actions_en_retard:
                recommendations.append({
                    'titre': 'Traiter les actions en retard',
                    'description': f'{len([a for a in actions if a.est_en_retard()])} action(s) sont en retard. Priorisez leur traitement.',
                    'priorite': 'haute'
                })
            elif a_des_actions_bloquees:
                recommendations.append({
                    'titre': 'Débloquer les actions bloquées',
                    'description': 'Certaines actions sont bloquées. Identifiez les obstacles et mettez en place des mesures correctives.',
                    'priorite': 'haute'
                })
            
            # Recommandation 4 : maturité
            if niveau_maturite < 3:
                recommendations.append({
                    'titre': 'Améliorer le niveau de maturité',
                    'description': f'Niveau de maturité actuel : {niveau_maturite}/5. Formalisez les procédures et renforcez les contrôles.',
                    'priorite': 'moyenne'
                })
            
            # Recommandation 5 : revue
            if not plan.date_prochaine_revue:
                recommendations.append({
                    'titre': 'Planifier la revue périodique',
                    'description': 'Aucune date de revue n\'est planifiée. Programmez une revue du plan qualité.',
                    'priorite': 'basse'
                })
            
            # Recommandation 6 : progression lente
            if progression < 30 and a_des_actions:
                recommendations.append({
                    'titre': 'Accélérer la mise en œuvre',
                    'description': f'La progression actuelle est de {progression:.0f}%. Mobilisez les équipes pour accélérer l\'exécution.',
                    'priorite': 'moyenne'
                })
            
            return recommendations[:5]
            
        except Exception as e:
            current_app.logger.error(f"Erreur analyse plan {plan_id}: {e}")
            return None

# ============================================
# 8. SUGGESTIONS ASSURANCE QUALITÉ
# ============================================
@staticmethod
def suggerer_assurance_qualite(titre):
    """Suggère des éléments pour la section assurance qualité."""
    
    # Procédures applicables
    procedures_options = [
        "PRO-001 - Gestion des non-conformités\nPRO-002 - Audit interne\nPRO-003 - Management des risques\nPRO-004 - Contrôle des documents",
        "PRO-012 - Évaluation des fournisseurs\nPRO-045 - Traitement des réclamations\nPRO-078 - Revue de direction\nPRO-099 - Gestion des compétences",
        "PRO-100 - Surveillance et mesure\nPRO-101 - Action corrective\nPRO-102 - Action préventive\nPRO-103 - Communication interne"
    ]
    
    # Documents de référence
    documents_options = [
        "Manuel qualité version 2.0\nRéférentiel ISO 9001:2025\nGuide des bonnes pratiques qualité\nPolitique qualité",
        "Documentation du système de management\nMatrice de conformité réglementaire\nPlan d'audit annuel\nRéférentiel des processus",
        "Normes ISO applicables\nRèglements sectoriels\nCode de conduite\nCharte qualité"
    ]
    
    # Contrôles clés
    controles_options = [
        "Séparation des tâches\nValidation systématique des documents\nRevue hebdomadaire des indicateurs\nContrôle croisé des dossiers",
        "Audit qualité mensuel\nRevue de processus trimestrielle\nContrôle interne des comptes\nSupervision hiérarchique",
        "Auto-évaluation des processus\nRevue par les pairs\nTableau de bord qualité\nIndicateurs de performance"
    ]
    
    # Fréquences possibles
    frequences = ['mensuel', 'trimestriel', 'semestriel', 'annuel']
    
    return {
        'procedures': random.choice(procedures_options),
        'documents': random.choice(documents_options),
        'controles': random.choice(controles_options),
        'frequence': random.choice(frequences)
    }
# ============================================
# 6. PLAN COMPLET (version optimisée)
# ============================================
@staticmethod
def generer_plan_complet(titre):
    """Génère un plan qualité complet avec toutes les sections."""
    
    # Générer tous les éléments (sans appel API externe si possible)
    description = IAQualiteService.generer_description_plan({'titre': titre, 'objectifs': []})
    objectifs = IAQualiteService.generer_objectifs_smart(titre)
    indicateurs = IAQualiteService.generer_indicateurs(titre, objectifs)
    niveau_maturite = IAQualiteService.suggerer_niveau_maturite(titre)
    assurance = IAQualiteService.suggerer_assurance_qualite(titre)
    
    # Date de revue suggérée (dans 6 mois)
    date_prochaine_revue = (datetime.now() + timedelta(days=180)).strftime('%Y-%m-%d')
    
    return {
        'description': description,
        'objectifs': objectifs,
        'indicateurs': indicateurs,
        'niveau_maturite': niveau_maturite,
        'procedures': assurance['procedures'],
        'documents': assurance['documents'],
        'controles': assurance['controles'],
        'frequence': assurance['frequence'],
        'date_prochaine_revue': date_prochaine_revue
    }
