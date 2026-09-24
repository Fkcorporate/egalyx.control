# services/ia_veille_service.py
"""
Service d'analyse IA pour la veille réglementaire.
- Si OPENAI_API_KEY est défini → utilise OpenAI GPT-4o-mini
- Sinon → utilise un moteur de suggestion local (heuristiques)
"""

import os
import re
import json
from typing import Optional, Dict, List
from collections import Counter


# ============================================
# MOTEUR LOCAL DE SUGGESTION (fallback)
# ============================================

class MoteurSuggestionLocal:
    """
    Moteur heuristique qui suggère une analyse SANS appel API.
    Basé sur :
    - Dictionnaire de mots-clés par criticité
    - Extraction de patterns (dates, références)
    - Fréquence des termes juridiques
    """
    
    # Mots-clés qui indiquent une criticité élevée
    MOTS_CLES_CRITIQUE = [
        'sanction', 'pénal', 'interdiction', 'obligation', 'conformité',
        'amende', 'poursuite', 'censure', 'radiation', 'retrait d\'agrément',
        'urgence', 'immédiat', 'sous peine', 'nullité', 'annulation'
    ]
    
    MOTS_CLES_ELEVE = [
        'obligatoire', 'doit', 'requis', 'impératif', 'exigence',
        'contrôle', 'audit', 'déclaration', 'déclarer', 'notification',
        'renforcement', 'durcissement', 'nouvelle exigence'
    ]
    
    MOTS_CLES_MOYEN = [
        'recommandation', 'incitation', 'encouragement', 'bonne pratique',
        'guide', 'référentiel', 'charte', 'modification', 'mise à jour'
    ]
    
    MOTS_CLES_FAIBLE = [
        'information', 'communication', 'sensibilisation', 'formation',
        'précision', 'clarification', 'interprétation'
    ]
    
    # Organismes connus
    ORGANISMES_CONNUS = {
        'AMF': 'Autorité des Marchés Financiers',
        'ACPR': 'Autorité de Contrôle Prudentiel et de Résolution',
        'CNIL': 'Commission Nationale de l\'Informatique et des Libertés',
        'BCEAO': 'Banque Centrale des États de l\'Afrique de l\'Ouest',
        'BEAC': 'Banque des États de l\'Afrique Centrale',
        'COBAC': 'Commission Bancaire de l\'Afrique Centrale',
        'OHADA': 'Organisation pour l\'Harmonisation en Afrique du Droit des Affaires',
        'CCJA': 'Cour Commune de Justice et d\'Arbitrage',
        'UE': 'Union Européenne',
        'JORF': 'Journal Officiel de la République Française',
        'ANSSI': 'Agence Nationale de la Sécurité des Systèmes d\'Information',
        'CNC': 'Conseil National de la Comptabilité',
        'IFRS': 'International Financial Reporting Standards',
        'BCBS': 'Comité de Bâle sur le contrôle bancaire',
        'GAFI': 'Groupe d\'Action Financière',
        'TRACFIN': 'Traitement du renseignement et action contre les circuits financiers clandestins'
    }
    
    # Secteurs d'impact
    SECTEURS_MOTS_CLES = {
        'finance': ['banque', 'financier', 'crédit', 'paiement', 'monétaire', 'bancaire'],
        'assurance': ['assurance', 'assureur', 'police', 'sinistre', 'prime'],
        'données personnelles': ['données', 'personnelles', 'RGPD', 'vie privée', 'informatique', 'libertés'],
        'cybersécurité': ['cyber', 'sécurité', 'informatique', 'système', 'piratage'],
        'santé': ['santé', 'médical', 'hôpital', 'pharmacie', 'patient'],
        'environnement': ['environnement', 'écologie', 'climat', 'carbone', 'pollution'],
        'social': ['social', 'travail', 'salarié', 'employeur', 'contrat', 'syndicat'],
        'comptabilité': ['comptabilité', 'comptable', 'bilan', 'audit', 'IFRS'],
        'fiscal': ['fiscal', 'impôt', 'taxe', 'TVA', 'contribution'],
        'concurrence': ['concurrence', 'antitrust', 'abus de position', 'cartel']
    }
    
    @classmethod
    def analyser(cls, titre: str, texte: str) -> Dict:
        """Analyse locale du texte"""
        texte_lower = (titre + ' ' + texte).lower()
        mots = re.findall(r'\b[a-zàâçéèêëîïôûùüÿñæœ]{3,}\b', texte_lower)
        
        # 1. Criticité
        criticite, justification = cls._evaluer_criticite(texte_lower)
        
        # 2. Résumé
        resume = cls._generer_resume(titre, texte)
        
        # 3. Organismes
        organismes = cls._detecter_organismes(texte_lower)
        
        # 4. Mots-clés
        mots_cles = cls._extraire_mots_cles(mots)
        
        # 5. Secteurs
        secteurs = cls._detecter_secteurs(texte_lower)
        
        # 6. Actions recommandées
        actions = cls._suggerer_actions(criticite, secteurs)
        
        return {
            'resume': resume,
            'criticite': criticite,
            'justification_criticite': justification,
            'organismes': organismes,
            'mots_cles': mots_cles,
            'secteurs_impactes': secteurs,
            'actions_recommandees': actions,
            'mode': 'local'
        }
    
    @classmethod
    def _evaluer_criticite(cls, texte: str) -> tuple:
        """Évalue la criticité basée sur les mots-clés"""
        scores = {
            'critique': sum(1 for m in cls.MOTS_CLES_CRITIQUE if m in texte),
            'eleve': sum(1 for m in cls.MOTS_CLES_ELEVE if m in texte),
            'moyen': sum(1 for m in cls.MOTS_CLES_MOYEN if m in texte),
            'faible': sum(1 for m in cls.MOTS_CLES_FAIBLE if m in texte),
        }
        
        # Priorité au plus élevé
        if scores['critique'] >= 2:
            return 'critique', f'{scores["critique"]} indicateurs de criticité critique détectés'
        elif scores['critique'] >= 1 or scores['eleve'] >= 3:
            return 'eleve', f'{scores["critique"] + scores["eleve"]} indicateurs d\'importance détectés'
        elif scores['eleve'] >= 1 or scores['moyen'] >= 2:
            return 'moyen', 'Texte de portée modérée'
        elif scores['faible'] >= 1:
            return 'faible', 'Texte informatif ou de sensibilisation'
        else:
            return 'moyen', 'Analyse basée sur le contenu général'
    
    @classmethod
    def _generer_resume(cls, titre: str, texte: str) -> str:
        """Résumé heuristique"""
        if not texte or len(texte) < 50:
            return f"Réglementation : {titre}. Contenu non disponible pour résumé automatique."
        
        # Premier paragraphe significatif
        paragraphes = [p.strip() for p in texte.split('\n\n') if len(p.strip()) > 50]
        if paragraphes:
            premier = paragraphes[0][:500]
            # Nettoyer les espaces
            premier = re.sub(r'\s+', ' ', premier)
            # Couper à la dernière phrase complète
            dernier_point = premier.rfind('.')
            if dernier_point > 100:
                premier = premier[:dernier_point + 1]
            return premier
        
        return f"Réglementation : {titre}. {texte[:200]}..."
    
    @classmethod
    def _detecter_organismes(cls, texte: str) -> List[str]:
        """Détecte les organismes mentionnés"""
        trouves = []
        for code, nom in cls.ORGANISMES_CONNUS.items():
            if code.lower() in texte or nom.lower() in texte:
                trouves.append(code)
        return trouves[:5]
    
    @classmethod
    def _extraire_mots_cles(cls, mots: List[str]) -> List[str]:
        """Extrait les mots-clés les plus fréquents"""
        # Mots vides à ignorer
        stopwords = {'dans', 'pour', 'avec', 'cette', 'sont', 'être', 'plus',
                     'tout', 'tous', 'toute', 'elles', 'nous', 'vous', 'leur',
                     'cela', 'ainsi', 'donc', 'mais', 'aussi', 'comme', 'sans'}
        
        filtres = [m for m in mots if m not in stopwords and len(m) > 4]
        compteur = Counter(filtres)
        return [mot for mot, _ in compteur.most_common(8)]
    
    @classmethod
    def _detecter_secteurs(cls, texte: str) -> List[str]:
        """Détecte les secteurs impactés"""
        trouves = []
        for secteur, mots in cls.SECTEURS_MOTS_CLES.items():
            if any(m in texte for m in mots):
                trouves.append(secteur)
        return trouves[:5]
    
    @classmethod
    def _suggerer_actions(cls, criticite: str, secteurs: List[str]) -> List[str]:
        """Suggère des actions selon la criticité"""
        actions = []
        
        if criticite in ['critique', 'eleve']:
            actions.extend([
                "Analyser en détail le texte et identifier les impacts",
                "Planifier une réunion de conformité dans les 7 jours",
                "Créer un plan d'action avec échéances"
            ])
        elif criticite == 'moyen':
            actions.extend([
                "Vérifier la pertinence pour votre organisation",
                "Programmer une analyse approfondie sous 30 jours"
            ])
        else:
            actions.append("Documenter et archiver pour référence")
        
        if 'données personnelles' in secteurs:
            actions.append("Vérifier les registres RGPD et les consentements")
        if 'finance' in secteurs:
            actions.append("Contrôler la conformité des process financiers")
        if 'cybersécurité' in secteurs:
            actions.append("Évaluer les mesures de sécurité existantes")
        
        return actions


# ============================================
# SERVICE IA PRINCIPAL (API + fallback)
# ============================================

class IAVeilleService:
    """
    Service d'analyse IA.
    - Utilise OpenAI si OPENAI_API_KEY est défini
    - Sinon, bascule sur le moteur local
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get('OPENAI_API_KEY')
        self.use_api = bool(self.api_key and self.api_key.strip())
        self.client = None
        
        if self.use_api:
            try:
                from openai import OpenAI
                self.client = OpenAI(api_key=self.api_key)
                print("✅ IAVeilleService : mode API OpenAI activé")
            except ImportError:
                print("⚠️ Module openai non installé → mode local activé")
                self.use_api = False
            except Exception as e:
                print(f"⚠️ Erreur OpenAI : {e} → mode local activé")
                self.use_api = False
        else:
            print("ℹ️ IAVeilleService : mode local (pas de OPENAI_API_KEY)")
    
    # ============================================
    # MÉTHODES PUBLIQUES
    # ============================================
    
    def analyser_texte_reglementaire(self, titre: str, texte: str,
                                      source: str = 'legifrance') -> Dict:
        """Analyse un texte réglementaire (API ou local)"""
        
        if self.use_api and self.client:
            try:
                return self._analyser_avec_api(titre, texte, source)
            except Exception as e:
                print(f"⚠️ Erreur API IA : {e} → fallback local")
                # Bascule sur le mode local
                result = MoteurSuggestionLocal.analyser(titre, texte)
                result['fallback_raison'] = str(e)
                return result
        else:
            return MoteurSuggestionLocal.analyser(titre, texte)
    
    def resumer_texte(self, texte: str, max_mots: int = 100) -> str:
        """Résume un texte (API ou local)"""
        if self.use_api and self.client:
            try:
                return self._resumer_avec_api(texte, max_mots)
            except Exception as e:
                print(f"⚠️ Erreur résumé IA : {e} → fallback local")
        
        # Fallback local
        result = MoteurSuggestionLocal.analyser("", texte)
        return result.get('resume', texte[:max_mots * 5])
    
    def suggerer_criticite(self, titre: str, texte: str) -> Dict:
        """Suggère une criticité (API ou local)"""
        if self.use_api and self.client:
            try:
                return self._criticite_avec_api(titre, texte)
            except Exception as e:
                print(f"⚠️ Erreur criticité IA : {e} → fallback local")
        
        # Fallback local
        result = MoteurSuggestionLocal.analyser(titre, texte)
        return {
            'criticite': result['criticite'],
            'justification': result['justification_criticite']
        }
    
    # ============================================
    # MÉTHODES PRIVÉES (API OpenAI)
    # ============================================
    
    def _analyser_avec_api(self, titre: str, texte: str, source: str) -> Dict:
        """Analyse via API OpenAI"""
        
        prompt = f"""Tu es un expert en conformité réglementaire.

Analyse ce texte réglementaire provenant de {source} :

TITRE : {titre}

TEXTE :
{texte[:3000]}

Réponds UNIQUEMENT en JSON avec ce format :
{{
    "resume": "Résumé en 3 phrases maximum",
    "criticite": "faible|moyen|eleve|critique",
    "justification_criticite": "Pourquoi cette criticité",
    "organismes": ["Organisme 1", "Organisme 2"],
    "mots_cles": ["mot1", "mot2", "mot3"],
    "secteurs_impactes": ["secteur1", "secteur2"],
    "actions_recommandees": ["Action 1", "Action 2"]
}}"""
        
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Tu es un expert en conformité réglementaire. Tu réponds uniquement en JSON valide."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=800,
            response_format={"type": "json_object"}
        )
        
        result = json.loads(response.choices[0].message.content)
        result['mode'] = 'api'
        return result
    
    def _resumer_avec_api(self, texte: str, max_mots: int) -> str:
        """Résumé via API OpenAI"""
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "user",
                "content": f"Résume ce texte réglementaire en {max_mots} mots maximum :\n\n{texte[:4000]}"
            }],
            temperature=0.3,
            max_tokens=300
        )
        return response.choices[0].message.content.strip()
    
    def _criticite_avec_api(self, titre: str, texte: str) -> Dict:
        """Criticité via API OpenAI"""
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "user",
                "content": f"""Analyse ce texte et suggère sa criticité (faible/moyen/eleve/critique).

TITRE : {titre}
TEXTE : {texte[:3000]}

Réponds en JSON : {{"criticite": "...", "justification": "..."}}"""
            }],
            temperature=0.2,
            max_tokens=200,
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    def suggerer_actions_concretes(self, titre, texte, criticite):
        """Suggère des actions concrètes basées sur la criticité"""
        actions_par_criticite = {
            'critique': [
                '🚨 Créer un plan d\'action immédiat',
                '📞 Convoquer une réunion de crise',
                '📊 Évaluer l\'impact financier',
                '👥 Informer le COMEX',
            ],
            'eleve': [
                '📝 Créer une veille dédiée',
                '⚠️ Analyser la conformité actuelle',
                '📅 Planifier une revue dans 15 jours',
            ],
            'moyen': [
                '📌 Documenter dans le registre',
                '👀 Surveiller les évolutions',
            ],
            'faible': [
                '📚 Archiver pour référence',
            ],
        }
        return actions_par_criticite.get(criticite, [])


    def detecter_risques_lies(self, titre, texte):
        """Détecte les risques métier à partir du texte"""
        risques_detectes = []
        
        mots_risques = {
            'cybersécurité': ['cyber', 'piratage', 'données', 'sécurité'],
            'conformité': ['conformité', 'sanction', 'amende'],
            'opérationnel': ['opération', 'processus', 'production'],
            'financier': ['financier', 'budget', 'trésorerie'],
            'réputation': ['réputation', 'image', 'marque'],
            'juridique': ['juridique', 'contentieux', 'procès'],
        }
        
        texte_lower = (titre + ' ' + texte).lower()
        
        for risque, mots in mots_risques.items():
            if any(m in texte_lower for m in mots):
                risques_detectes.append(risque)
        
        return risques_detectes
