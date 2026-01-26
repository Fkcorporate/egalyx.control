# services/kri_ia_service.py
import os
import json
from datetime import datetime
from typing import Dict, List, Optional
import openai

class KRIIAService:
    """Service IA pour générer des KRI pertinents"""
    
    def __init__(self):
        self.api_key = os.environ.get("OPENAI_API_KEY")
        self.mode_simulation = False
        
        if not self.api_key or self.api_key.startswith("mode-simulation"):
            self.mode_simulation = True
            print("🔧 Mode simulation pour KRI IA")
        else:
            try:
                self.client = openai.OpenAI(api_key=self.api_key)
                print("✅ Service KRI IA initialisé")
            except Exception as e:
                print(f"⚠️ Erreur initialisation OpenAI: {e}")
                self.mode_simulation = True
    
    def generer_kris_pour_risque(self, risque_data: Dict) -> List[Dict]:
        """
        Génère des suggestions de KRI pour un risque
        
        Args:
            risque_data: Données du risque
        
        Returns:
            Liste de suggestions de KRI
        """
        if self.mode_simulation:
            return self._simuler_generation_kri(risque_data)
        
        try:
            return self._generer_kri_reel(risque_data)
        except Exception as e:
            print(f"❌ Erreur génération KRI IA: {e}")
            return self._simuler_generation_kri(risque_data)
    
    def _generer_kri_reel(self, risque_data: Dict) -> List[Dict]:
        """Génération réelle avec OpenAI"""
        prompt = self._construire_prompt_kri(risque_data)
        
        response = self.client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": """Tu es un expert en gestion des risques et indicateurs (KRI/KPI). 
                    Tu dois générer des indicateurs KRI pertinents pour surveiller des risques.
                    Réponds uniquement au format JSON suivant :
                    {
                        "kris": [
                            {
                                "nom": "Nom du KRI",
                                "description": "Description détaillée",
                                "formule_calcul": "Formule de calcul",
                                "unite_mesure": "Unité de mesure",
                                "categorie": "catégorie",
                                "seuil_alerte": 0.0,
                                "seuil_critique": 0.0,
                                "sens_evaluation_seuil": "superieur",
                                "frequence_mesure": "mensuel",
                                "justification": "Pourquoi cet indicateur est pertinent"
                            }
                        ]
                    }"""
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=1500
        )
        
        resultat = response.choices[0].message.content
        
        try:
            # Essayer d'extraire le JSON
            import re
            json_match = re.search(r'\{.*\}', resultat, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return data.get("kris", [])
        except json.JSONDecodeError:
            print(f"⚠️ Réponse non JSON: {resultat[:100]}...")
        
        return []
    
    def _construire_prompt_kri(self, risque_data: Dict) -> str:
        """Construire un prompt intelligent pour générer des KRI"""
        
        # Récupérer les informations du risque de manière sécurisée
        reference = risque_data.get('reference', 'N/A')
        intitule = risque_data.get('intitule', 'N/A')
        description = risque_data.get('description', 'Non spécifiée')
        categorie = risque_data.get('categorie', 'Non spécifiée')
        probabilite = risque_data.get('probabilite', 'Non évaluée')
        impact = risque_data.get('impact', 'Non évalué')
        score_risque = risque_data.get('score_risque', 'Non calculé')
        
        # Récupérer le processus de manière sécurisée
        processus_nom = 'Non spécifié'
        if 'processus' in risque_data and risque_data['processus']:
            if isinstance(risque_data['processus'], dict):
                processus_nom = risque_data['processus'].get('nom', 'Non spécifié')
            elif hasattr(risque_data['processus'], 'nom'):
                processus_nom = risque_data['processus'].nom
            else:
                processus_nom = str(risque_data['processus'])
        
        # Récupérer le responsable de manière sécurisée
        responsable_nom = 'Non assigné'
        if 'responsable' in risque_data and risque_data['responsable']:
            if isinstance(risque_data['responsable'], dict):
                responsable_nom = risque_data['responsable'].get('username', 'Non assigné')
            elif hasattr(risque_data['responsable'], 'username'):
                responsable_nom = risque_data['responsable'].username
            else:
                responsable_nom = str(risque_data['responsable'])
        
        return f"""
        Génère 3 à 5 indicateurs KRI (Key Risk Indicators) pertinents pour surveiller ce risque :
        
        RISQUE :
        Référence: {reference}
        Intitulé: {intitule}
        Description: {description}
        Catégorie: {categorie}
        
        ÉVALUATION DU RISQUE (si disponible) :
        - Probabilité: {probabilite}
        - Impact: {impact}
        - Score: {score_risque}
        
        CONTEXTE SUPPLÉMENTAIRE :
        - Processus concerné: {processus_nom}
        - Responsable: {responsable_nom}
        
        Pour chaque KRI, fournis :
        1. Un nom clair et explicite
        2. Une description de l'indicateur
        3. La formule de calcul ou méthode de mesure
        4. L'unité de mesure appropriée
        5. Une catégorie (financier, opérationnel, qualité, sécurité, etc.)
        6. Des seuils d'alerte et critique réalistes
        7. La fréquence de mesure recommandée
        8. Une justification expliquant pourquoi cet indicateur est pertinent
        
        Les KRI doivent être :
        - Mesurables et quantifiables
        - Pertinents pour le risque
        - Actionnables (permettre de prendre des décisions)
        - Réalistes à mettre en place
        """
    
    def _simuler_generation_kri(self, risque_data: Dict) -> List[Dict]:
        """Simuler la génération de KRI"""
        
        # Récupérer les informations de base
        reference = risque_data.get('reference', 'RISQUE')
        intitule = risque_data.get('intitule', 'Risque')
        categorie = risque_data.get('categorie', '').lower()
        
        kris_generiques = [
            {
                "nom": f"Taux d'occurrence - {reference}",
                "description": f"Mesure la fréquence d'apparition du risque : {intitule}",
                "formule_calcul": "(Nombre d'occurrences / Période) × 100",
                "unite_mesure": "%",
                "categorie": "operationnel",
                "seuil_alerte": 5.0,
                "seuil_critique": 10.0,
                "sens_evaluation_seuil": "superieur",
                "frequence_mesure": "mensuel",
                "justification": "Permet de surveiller la fréquence d'apparition du risque"
            },
            {
                "nom": f"Impact moyen - {reference}",
                "description": f"Impact moyen constaté lorsque le risque '{intitule}' se matérialise",
                "formule_calcul": "Somme des impacts / Nombre d'occurrences",
                "unite_mesure": "€",
                "categorie": "financier",
                "seuil_alerte": 5000.0,
                "seuil_critique": 10000.0,
                "sens_evaluation_seuil": "superieur",
                "frequence_mesure": "trimestriel",
                "justification": "Mesure l'impact financier moyen du risque"
            }
        ]
        
        # KRI spécifiques par catégorie
        kris_specifiques = []
        
        if 'financier' in categorie:
            kris_specifiques.append({
                "nom": f"Écart budgétaire - {reference}",
                "description": "Écart entre le budget prévu et les dépenses réelles liées au risque",
                "formule_calcul": "(Dépenses réelles - Budget prévu) / Budget prévu × 100",
                "unite_mesure": "%",
                "categorie": "financier",
                "seuil_alerte": 10.0,
                "seuil_critique": 20.0,
                "sens_evaluation_seuil": "superieur",
                "frequence_mesure": "mensuel",
                "justification": "Surveille les dépassements budgétaires liés au risque"
            })
        
        if 'operationnel' in categorie or 'processus' in categorie:
            kris_specifiques.append({
                "nom": f"Délai de traitement - {reference}",
                "description": "Délai moyen pour traiter les incidents liés au risque",
                "formule_calcul": "Somme des délais / Nombre d'incidents",
                "unite_mesure": "jours",
                "categorie": "operationnel",
                "seuil_alerte": 7.0,
                "seuil_critique": 14.0,
                "sens_evaluation_seuil": "superieur",
                "frequence_mesure": "hebdomadaire",
                "justification": "Mesure l'efficacité du traitement des incidents"
            })
        
        if 'securite' in categorie or 'conformite' in categorie:
            kris_specifiques.append({
                "nom": f"Taux de conformité - {reference}",
                "description": "Pourcentage de conformité aux exigences de sécurité/conformité",
                "formule_calcul": "(Nombre de contrôles conformes / Nombre total de contrôles) × 100",
                "unite_mesure": "%",
                "categorie": "conformite",
                "seuil_alerte": 90.0,
                "seuil_critique": 80.0,
                "sens_evaluation_seuil": "inferieur",
                "frequence_mesure": "trimestriel",
                "justification": "Surveille le niveau de conformité aux exigences"
            })
        
        if 'rh' in categorie or 'humain' in categorie:
            kris_specifiques.append({
                "nom": f"Taux de rotation - {reference}",
                "description": "Taux de rotation du personnel lié au risque",
                "formule_calcul": "(Nombre de départs / Effectif moyen) × 100",
                "unite_mesure": "%",
                "categorie": "rh",
                "seuil_alerte": 15.0,
                "seuil_critique": 25.0,
                "sens_evaluation_seuil": "superieur",
                "frequence_mesure": "trimestriel",
                "justification": "Surveille la stabilité du personnel concerné"
            })
        
        # Combiner les KRI
        kris_simules = kris_generiques + kris_specifiques[:2]  # Limiter à 2 spécifiques
        
        # Ajouter des métadonnées
        for kri in kris_simules:
            kri['_metadata'] = {
                'generated_at': datetime.utcnow().isoformat(),
                'mode': 'simulation',
                'risque_reference': reference,
                'score_confiance': 70.0
            }
        
        return kris_simules
    
    def ajuster_kri(self, kri_suggestion: Dict, ajustements: Dict) -> Dict:
        """
        Ajuste une suggestion de KRI selon les préférences utilisateur
        """
        kri_ajuste = kri_suggestion.copy()
        
        # Appliquer les ajustements
        for champ, valeur in ajustements.items():
            if champ in kri_ajuste:
                if champ in ['seuil_alerte', 'seuil_critique']:
                    try:
                        kri_ajuste[champ] = float(valeur)
                    except (ValueError, TypeError):
                        kri_ajuste[champ] = valeur
                else:
                    kri_ajuste[champ] = valeur
        
        # Marquer comme ajusté
        if '_metadata' not in kri_ajuste:
            kri_ajuste['_metadata'] = {}
        
        kri_ajuste['_metadata']['ajuste'] = True
        kri_ajuste['_metadata']['ajustements'] = ajustements
        kri_ajuste['_metadata']['ajusted_at'] = datetime.utcnow().isoformat()
        
        return kri_ajuste

# Singleton
kri_ia_service = KRIIAService()
