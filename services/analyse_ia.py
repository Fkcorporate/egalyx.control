# services/analyse_ia.py - Version corrigée
import os
import json
import time
from datetime import datetime
from typing import Optional, Dict, Any

class ServiceAnalyseIA:
    def __init__(self):
        """Initialiser le service IA avec la nouvelle API OpenAI"""
        
        # Récupérer la clé depuis l'environnement
        self.api_key = os.environ.get("OPENAI_API_KEY")
        
        # Déterminer le mode de fonctionnement
        self.mode_simulation = True  # Par défaut en simulation
        self.client = None
        self.quota_error = False
        
        print(f"\n🔍 INITIALISATION SERVICE IA")
        print(f"   Clé API: {'✅ Présente' if self.api_key else '❌ Absente'}")
        
        if not self.api_key or self.api_key.startswith("mode-simulation"):
            print("   🔧 Mode simulation activé (pas de clé API valide)")
            return
        
        # Vérifier le format de la clé
        if not self.api_key.startswith("sk-"):
            print(f"   ⚠️ Format clé invalide (doit commencer par 'sk-')")
            return
        
        # Initialiser OpenAI
        try:
            from openai import OpenAI
            self.client = OpenAI(api_key=self.api_key)
            print("   ✅ Client OpenAI initialisé")
            
            # Tester la connexion
            if self._tester_connexion():
                self.mode_simulation = False
                print("   ✅ Mode réel activé")
            else:
                print("   🔧 Mode simulation activé (test échoué)")
                
        except ImportError:
            print("   ⚠️ Package OpenAI non installé")
            print("      pip install openai")
        except Exception as e:
            print(f"   ⚠️ Erreur: {e}")
    
    def _tester_connexion(self):
        """Tester la connexion à l'API - retourne True si succès"""
        if not self.client:
            return False
        
        try:
            # Test très basique pour vérifier l'authentification
            response = self.client.models.list(timeout=10.0)
            print(f"   ✅ Connexion API OK - {len(response.data)} modèles disponibles")
            return True
            
        except Exception as e:
            error_msg = str(e)
            print(f"   ❌ Erreur connexion API")
            
            # Messages d'erreur spécifiques
            if "insufficient_quota" in error_msg or "429" in error_msg:
                print("   💸 ERREUR QUOTA: Plus de crédit sur votre compte")
                print("      https://platform.openai.com/billing")
                self.quota_error = True
            elif "Invalid API key" in error_msg:
                print("   🔑 Clé API invalide")
            elif "rate limit" in error_msg.lower():
                print("   ⏳ Limite de taux, réessayez plus tard")
            else:
                print(f"   Détails: {error_msg[:100]}...")
            
            return False
    
    def analyser_audit(self, audit_id, type_analyse='complet', user_id=None):
        """Analyser un audit avec l'IA"""
        
        print(f"\n🎯 ANALYSE IA DÉMARRÉE")
        print(f"   Audit ID: {audit_id}")
        print(f"   Mode: {'Simulation' if self.mode_simulation else 'Réel'}")
        
        if self.mode_simulation:
            return self._simuler_analyse_detaille(audit_id, type_analyse)
        
        try:
            # Mode réel avec OpenAI
            return self._analyser_reel(audit_id, type_analyse)
            
        except Exception as e:
            print(f"❌ Erreur analyse réelle: {e}")
            print("   Fallback vers la simulation")
            return self._simuler_analyse_detaille(audit_id, type_analyse)
    
    def _analyser_reel(self, audit_id, type_analyse):
        """Analyse réelle avec OpenAI"""
        try:
            # Créer un contexte d'application
            app_context = self.get_app_context()  # CORRECTION : utiliser self.
            
            if not app_context:
                raise Exception("Contexte d'application non disponible")
            
            with app_context:
                from models import Audit, Constatation
                from app import db
                
                # Récupérer les données de l'audit
                audit = db.session.get(Audit, audit_id)
                if not audit:
                    raise ValueError(f"Audit {audit_id} non trouvé")
                
                # Construire un prompt intelligent
                prompt = self._construire_prompt_intelligent(audit, type_analyse)
                
                # Appel à l'API
                response = self.client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {
                            "role": "system", 
                            "content": "Tu es un expert en audit interne, gestion des risques et conformité. Réponds en français avec des analyses structurées."
                        },
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7,
                    max_tokens=1500
                )
                
                # Traiter la réponse
                resultat = self._traiter_reponse_ia(response, audit_id)
                
                # Ajouter les métadonnées
                resultat['metadata'] = {
                    'audit_id': audit_id,
                    'mode': 'reel',
                    'model': response.model,
                    'tokens': response.usage.total_tokens,
                    'score_confiance': 85.0,
                    'timestamp': datetime.now().isoformat()
                }
                
                print(f"   ✅ Analyse réelle terminée")
                print(f"   Tokens utilisés: {response.usage.total_tokens}")
                
                return resultat
                
        except Exception as e:
            raise Exception(f"Erreur analyse réelle: {e}")
    
    def get_app_context(self):
        """Obtenir ou créer un contexte d'application Flask"""
        try:
            from app import app
            return app.app_context()
        except ImportError:
            # Si l'application n'est pas disponible, retourner None
            return None
        except Exception:
            return None
    
    def _simuler_analyse_detaille(self, audit_id, type_analyse):
        """Simuler une analyse IA détaillée"""
        try:
            # Récupérer les données de l'audit depuis la base
            from app import app
            from models import Audit, Constatation, Recommandation
            import sys
            
            # Créer un contexte d'application
            app_context = app.app_context()
            
            if not app_context:
                # Si pas de contexte, simulation par défaut
                return self._simulation_par_defaut(audit_id)
            
            with app_context:
                from app import db
                
                # Récupérer l'audit
                audit = db.session.get(Audit, audit_id)
                if not audit:
                    return self._simulation_par_defaut(audit_id)
                
                # Récupérer les constatations et recommandations
                # CORRECTION : utiliser statut au lieu de is_archived
                constatations = db.session.query(Constatation).filter_by(
                    audit_id=audit_id
                ).filter(Constatation.statut != 'archive' if hasattr(Constatation, 'statut') else True).all()
                
                recommandations = db.session.query(Recommandation).filter_by(
                    audit_id=audit_id
                ).filter(Recommandation.statut != 'archive' if hasattr(Recommandation, 'statut') else True).all()
                
                # Générer une analyse réaliste basée sur les données réelles
                return self._generer_analyse_realiste(audit, constatations, recommandations, type_analyse)
                
        except Exception as e:
            print(f"⚠️ Erreur simulation détaillée: {e}")
            import traceback
            traceback.print_exc()
            # Retourner une simulation par défaut
            return self._simulation_par_defaut(audit_id)
    
    def _generer_analyse_realiste(self, audit, constatations, recommandations, type_analyse):
        """Générer une analyse réaliste basée sur les données réelles"""
        
        # Analyser les thèmes des constatations
        themes = []
        for constatation in constatations[:5]:  # Prendre max 5
            titre = getattr(constatation, 'titre', '')
            if 'procédure' in titre.lower():
                themes.append('procédures')
            elif 'contrôle' in titre.lower():
                themes.append('contrôles')
            elif 'document' in titre.lower():
                themes.append('documentation')
            elif 'formation' in titre.lower():
                themes.append('formation')
            else:
                themes.append('général')
        
        # Compter les occurrences
        from collections import Counter
        theme_counts = Counter(themes)
        
        # Générer des recommandations basées sur les thèmes
        recommandations_ia = []
        priorites = ['haute', 'moyenne', 'basse']
        
        for i, (theme, count) in enumerate(theme_counts.most_common(3)):
            recommandations_ia.append({
                'id': i + 1,
                'titre': self._generer_titre_recommandation(theme, count),
                'description': self._generer_description_recommandation(theme, audit),
                'priorite': priorites[min(i, 2)],
                'score_confiance': 85 - (i * 10),
                'delai_suggere': f'{(i+1)*30} jours',
                'theme': theme
            })
        
        # Générer des causes racines
        causes_racines = []
        if theme_counts:
            causes_racines.append({
                'cause': 'Manque de formalisation des procédures',
                'frequence': theme_counts.get('procédures', 0) + theme_counts.get('documentation', 0),
                'impact': 'élevé' if theme_counts.get('procédures', 0) > 0 else 'moyen',
                'solutions': ['Documenter les procédures', 'Former le personnel']
            })
        
        if constatations:
            causes_racines.append({
                'cause': 'Contrôles internes insuffisants',
                'frequence': theme_counts.get('contrôles', 0),
                'impact': 'élevé',
                'solutions': ['Renforcer les contrôles', 'Automatiser les vérifications']
            })
        
        # Statistiques
        nb_recommandations = len(recommandations_ia)
        nb_causes = len(causes_racines)
        score_global = min(85 + (len(constatations) * 2), 95)  # Score basé sur le nombre de constatations
        
        return {
            'analyse': f"Analyse IA de l'audit {audit.reference} : {audit.titre}\n\nL'analyse a identifié {len(constatations)} constatations principales regroupées en {len(theme_counts)} thèmes clés.",
            'points_forts': self._generer_points_forts(audit, recommandations),
            'risques': self._generer_risques(constatations),
            'recommandations_ia': recommandations_ia,
            'causes_racines': causes_racines,
            'statistiques': {
                'nb_recommandations_suggerees': nb_recommandations,
                'nb_causes_identifiees': nb_causes,
                'score_global': score_global,
                'temps_analyse': f'{1.5 + len(constatations) * 0.2:.1f} secondes',
                'constatations_analysees': len(constatations),
                'themes_identifies': len(theme_counts)
            },
            'metadata': {
                'audit_id': audit.id,
                'audit_reference': audit.reference,
                'mode': 'simulation_ameliorée',
                'score_confiance': float(score_global),
                'timestamp': datetime.now().isoformat(),
                'user_notice': 'Analyse en mode simulation - Pour une analyse réelle, rechargez votre compte OpenAI'
            }
        }
    
    def _generer_titre_recommandation(self, theme, count):
        """Générer un titre de recommandation réaliste"""
        titres = {
            'procédures': [
                f'Formaliser les procédures ({count} constatations)',
                'Documenter les processus clés',
                'Mettre à jour le manuel de procédures'
            ],
            'contrôles': [
                f'Renforcer les contrôles internes ({count} faiblesses)',
                'Implémenter des contrôles automatiques',
                'Supervision renforcée des activités'
            ],
            'documentation': [
                'Améliorer la documentation des processus',
                'Centraliser la documentation',
                'Système de gestion documentaire'
            ],
            'formation': [
                'Plan de formation du personnel',
                'Sessions de formation régulières',
                'Évaluation des compétences'
            ]
        }
        
        return titres.get(theme, [f'Amélioration des processus ({count} constatations)'])[0]
    
    def _generer_description_recommandation(self, theme, audit):
        """Générer une description réaliste"""
        descriptions = {
            'procédures': f"Suite à l'audit {audit.reference}, il est recommandé de formaliser et documenter les procédures opérationnelles pour assurer une exécution cohérente et traçable des activités.",
            'contrôles': f"L'audit {audit.reference} a identifié des faiblesses dans les contrôles internes. Il est nécessaire de renforcer les mécanismes de contrôle pour prévenir les risques opérationnels.",
            'documentation': f"La documentation des processus de l'audit {audit.reference} présente des lacunes. Une documentation complète et à jour est essentielle pour la conformité et la formation du personnel.",
            'formation': f"L'audit {audit.reference} révèle un besoin en formation. Un plan de formation structuré améliorera les compétences et réduira les erreurs opérationnelles."
        }
        
        return descriptions.get(theme, f"Recommandation générale pour améliorer les processus suite à l'audit {audit.reference}.")
    
    def _generer_points_forts(self, audit, recommandations):
        """Générer des points forts réalistes"""
        points = []
        
        if hasattr(audit, 'statut') and audit.statut == 'termine':
            points.append('Audit mené à son terme avec succès')
        
        if recommandations:
            points.append(f'{len(recommandations)} recommandations déjà identifiées')
        
        points.extend([
            'Engagement de la direction',
            'Coopération des équipes auditées',
            'Méthodologie d\'audit structurée'
        ])
        
        return points
    
    def _generer_risques(self, constatations):
        """Générer des risques réalistes"""
        risques = []
        
        if constatations:
            risques.append({
                'nom': 'Risque de non-conformité réglementaire',
                'niveau': 'élevé' if len(constatations) > 3 else 'moyen',
                'probabilite': 0.4,
                'description': f"{len(constatations)} constatations identifiées pouvant entraîner des sanctions réglementaires"
            })
        
        risques.extend([
            {
                'nom': 'Risque opérationnel',
                'niveau': 'moyen',
                'probabilite': 0.3,
                'description': 'Faiblesses dans les processus pouvant affecter l\'efficacité opérationnelle'
            },
            {
                'nom': 'Risque réputationnel',
                'niveau': 'moyen' if len(constatations) > 2 else 'faible',
                'probabilite': 0.2,
                'description': 'Impact potentiel sur l\'image de l\'organisation'
            }
        ])
        
        return risques
    
    def _simulation_par_defaut(self, audit_id):
        """Simulation par défaut si audit non trouvé"""
        return {
            'analyse': f"Analyse IA de l'audit {audit_id} - Mode simulation",
            'points_forts': ['Procédures existantes', 'Équipe disponible'],
            'risques': [
                {
                    'nom': 'Risque générique',
                    'niveau': 'moyen',
                    'probabilite': 0.3
                }
            ],
            'recommandations_ia': [
                {
                    'id': 1,
                    'titre': 'Améliorer la documentation',
                    'description': 'Documenter les processus clés pour assurer la traçabilité',
                    'priorite': 'haute',
                    'score_confiance': 80,
                    'delai_suggere': '30 jours'
                },
                {
                    'id': 2,
                    'titre': 'Renforcer les contrôles',
                    'description': 'Mettre en place des contrôles supplémentaires sur les activités critiques',
                    'priorite': 'moyenne',
                    'score_confiance': 75,
                    'delai_suggere': '45 jours'
                }
            ],
            'causes_racines': [
                {
                    'cause': 'Manque de ressources dédiées',
                    'frequence': 2,
                    'impact': 'moyen',
                    'solutions': ['Allouer des ressources spécifiques', 'Former le personnel existant']
                }
            ],
            'statistiques': {
                'nb_recommandations_suggerees': 2,
                'nb_causes_identifiees': 1,
                'score_global': 78,
                'temps_analyse': '2.5 secondes',
                'constatations_analysees': 0,
                'themes_identifies': 2
            },
            'metadata': {
                'audit_id': audit_id,
                'mode': 'simulation_defaut',
                'score_confiance': 78.0,
                'timestamp': datetime.now().isoformat(),
                'notice': 'Mode simulation - Rechargez votre compte OpenAI pour une analyse réelle'
            }
        }
    
    def _construire_prompt_intelligent(self, audit, type_analyse):
        """Construire un prompt intelligent pour l'analyse"""
        # Cette méthode est utilisée en mode réel
        return f"""
        Analyse l'audit suivant :
        
        Référence: {audit.reference}
        Titre: {audit.titre}
        Objectif: {getattr(audit, 'objectif', 'Non spécifié')}
        
        Fournis une analyse structurée avec:
        1. Points forts
        2. Risques identifiés
        3. Recommandations prioritaires
        4. Causes racines
        
        Format de réponse: JSON structuré.
        """
    
    def _traiter_reponse_ia(self, response, audit_id):
        """Traiter la réponse de l'IA (mode réel)"""
        try:
            content = response.choices[0].message.content
            
            # Essayer de parser comme JSON
            if content.strip().startswith('{'):
                return json.loads(content)
            else:
                # Retourner comme texte structuré
                return {
                    'analyse': content,
                    'recommandations_ia': [],
                    'causes_racines': []
                }
                
        except json.JSONDecodeError:
            return {
                'analyse': content,
                'metadata': {'format': 'texte', 'audit_id': audit_id}
            }
    
    def get_statut(self):
        """Obtenir le statut du service"""
        return {
            'mode': 'simulation' if self.mode_simulation else 'reel',
            'quota_error': self.quota_error,
            'client_initialise': self.client is not None,
            'api_key_presente': self.api_key is not None
        }

    def generer_lettre_mission(self, audit_id, feuille_id=None):
        """Générer une lettre de mission pour un audit"""
        
        print(f"\n📝 GÉNÉRATION LETTRE DE MISSION")
        print(f"   Audit ID: {audit_id}")
        print(f"   Mode: {'Simulation' if self.mode_simulation else 'Réel'}")
        
        # Récupérer le contexte d'application
        app_context = self.get_app_context()
        if not app_context:
            return self._simuler_lettre_mission(audit_id)
        
        with app_context:
            from models import Audit, User, Client
            from app import db
            
            audit = db.session.get(Audit, audit_id)
            if not audit:
                return self._simuler_lettre_mission(audit_id)
            
            if self.mode_simulation:
                return self._simuler_lettre_mission(audit_id, audit)
            
            try:
                return self._generer_lettre_mission_reelle(audit)
            except Exception as e:
                print(f"❌ Erreur génération lettre: {e}")
                return self._simuler_lettre_mission(audit_id, audit)
    
    def _generer_lettre_mission_reelle(self, audit):
        """Générer une lettre de mission réelle avec OpenAI"""
        
        # Récupérer les informations
        responsable_nom = "Responsable concerné"
        if audit.responsable:
            responsable_nom = audit.responsable.username
            if hasattr(audit.responsable, 'nom_complet') and audit.responsable.nom_complet:
                responsable_nom = audit.responsable.nom_complet
        
        client_nom = "Votre société"
        if audit.client_id:
            from models import Client
            client = Client.query.get(audit.client_id)
            if client:
                client_nom = client.nom if hasattr(client, 'nom') else (client.name if hasattr(client, 'name') else client_nom)
        
        date_debut = audit.date_debut_prevue.strftime('%d/%m/%Y') if audit.date_debut_prevue else "à définir"
        date_fin = audit.date_fin_prevue.strftime('%d/%m/%Y') if audit.date_fin_prevue else "à définir"
        
        # Construire le prompt
        prompt = f"""
        Génère une lettre de mission d'audit professionnelle en français.
        
        Informations de l'audit:
        - Référence: {audit.reference}
        - Titre: {audit.titre}
        - Type: {audit.type_audit or 'interne'}
        - Responsable: {responsable_nom}
        - Client: {client_nom}
        - Date début: {date_debut}
        - Date fin: {date_fin}
        - Portée: {audit.portee or 'Non spécifiée'}
        
        Génère un objet JSON avec les champs suivants:
        - destinataire (nom et fonction)
        - societe
        - objet
        - introduction (2-3 paragraphes)
        - objectifs (liste détaillée)
        - perimetre
        - modalites (modalités pratiques)
        - equipe (composition)
        - livrables
        """
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Tu es un expert en audit interne. Génère des lettres de mission professionnelles au format JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=1200
            )
            
            content = response.choices[0].message.content
            
            # Extraire le JSON
            import re
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                import json
                lettre = json.loads(json_match.group())
                lettre['_mode'] = 'openai'
                lettre['_tokens'] = response.usage.total_tokens if hasattr(response, 'usage') else 0
                return lettre
            else:
                raise ValueError("Pas de JSON trouvé")
                
        except Exception as e:
            print(f"❌ Erreur OpenAI: {e}")
            return self._simuler_lettre_mission(audit.id, audit)
    
    def _simuler_lettre_mission(self, audit_id, audit=None):
        """Simuler une lettre de mission réaliste"""
        
        from datetime import datetime
        from models import Audit, User
        
        # Si audit non fourni, essayer de le récupérer
        if audit is None:
            app_context = self.get_app_context()
            if app_context:
                with app_context:
                    from app import db
                    audit = db.session.get(Audit, audit_id)
        
        # Valeurs par défaut
        responsable_nom = "Responsable concerné"
        client_nom = "Votre société"
        audit_ref = f"AUD-{audit_id:04d}"
        audit_titre = "Audit"
        audit_type = "interne"
        portee = "L'ensemble des processus de l'entité"
        
        if audit:
            audit_ref = audit.reference or audit_ref
            audit_titre = audit.titre or audit_titre
            audit_type = audit.type_audit or audit_type
            portee = audit.portee or portee
            
            if audit.responsable:
                responsable_nom = audit.responsable.username
                if hasattr(audit.responsable, 'nom_complet') and audit.responsable.nom_complet:
                    responsable_nom = audit.responsable.nom_complet
            
            if audit.client_id:
                from models import Client
                client = Client.query.get(audit.client_id)
                if client:
                    client_nom = client.nom if hasattr(client, 'nom') else (client.name if hasattr(client, 'name') else client_nom)
        
        date_debut = audit.date_debut_prevue.strftime('%d/%m/%Y') if audit and audit.date_debut_prevue else "à définir"
        date_fin = audit.date_fin_prevue.strftime('%d/%m/%Y') if audit and audit.date_fin_prevue else "à définir"
        
        # Calcul durée
        duree = "5 jours"
        if audit and audit.date_debut_prevue and audit.date_fin_prevue:
            jours = (audit.date_fin_prevue - audit.date_debut_prevue).days
            duree = f"{jours} jours" if jours > 0 else "À définir"
        
        return {
            "destinataire": responsable_nom,
            "societe": client_nom,
            "objet": f"Lettre de mission - Audit {audit_type.upper()} {audit_ref}",
            "introduction": f"""Dans le cadre de notre plan d'audit annuel, nous vous informons de la réalisation d'une mission d'audit au sein de votre service.
    
    Cette mission s'inscrit dans notre démarche d'amélioration continue et vise à évaluer la conformité des processus avec les référentiels applicables.
    
    Nous vous remercions par avance pour votre collaboration et pour la mise à disposition des informations nécessaires à la bonne réalisation de cette mission.""",
            "objectifs": f"""Les principaux objectifs de cette mission sont :
    - Évaluer l'efficacité du contrôle interne
    - Identifier les risques potentiels
    - Formuler des recommandations d'amélioration
    - Assurer la conformité réglementaire
    - Proposer des axes de progrès""",
            "perimetre": f"""Le périmètre de la mission couvre : {portee}
    
    Période concernée : du {date_debut} au {date_fin}
    Durée estimée : {duree}""",
            "modalites": """Les travaux seront réalisés selon les modalités suivantes :
    - Entretiens avec les responsables et les opérationnels
    - Analyse documentaire (procédures, instructions, registres)
    - Tests de conformité sur échantillon
    - Observations sur site
    - Réunions de synthèse et de clôture
    
    L'équipe d'audit aura accès aux informations nécessaires à la bonne réalisation de la mission, dans le respect des règles de confidentialité.""",
            "equipe": f"L'équipe d'audit est composée de professionnels qualifiés, sous la supervision de l'auditeur principal.",
            "livrables": """Les livrables attendus à l'issue de la mission sont :
    - Rapport d'audit détaillé
    - Fiche de synthèse des constats
    - Plan d'action correctif
    - Présentation des résultats à la direction
    - Suivi des actions mises en place""",
            "date_debut": date_debut,
            "date_fin": date_fin,
            "duree": duree,
            "date": datetime.now().strftime('%Y-%m-%d'),
            "reference": f"LM-{audit_ref}-{datetime.now().year}",
            "emetteur": "L'équipe d'audit - Auditeur principal",
            "confidentialite": True,
            "confidentialite_texte": """Les informations recueillies dans le cadre de cette mission sont strictement confidentielles et ne pourront être divulguées à des tiers sans autorisation préalable.
    
    Conformément aux dispositions légales et réglementaires, les données personnelles sont traitées dans le respect du RGPD. Chaque membre de l'équipe d'audit est tenu au secret professionnel.""",
            "_mode": "simulation"
        }
