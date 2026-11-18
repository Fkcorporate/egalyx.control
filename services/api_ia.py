"""
Intégration avec les APIs IA externes
"""

# --- Journal (remplace les anciens print()) : erreurs -> WARNING (journaux du serveur) ; le reste -> DEBUG,
#     visible seulement avec EGALYX_TRACES=1. Ajouté le 18/11/2026 (ménage).
import logging as _logging_journal
import os as _os_journal
_JOURNAL = _logging_journal.getLogger('egalyx.services.api_ia')
_MOTS_ALERTE = ('\u274c', '\u26a0', 'ERREUR', 'Erreur', 'erreur', 'ERROR', 'Error', 'error', 'Exception', 'chec', 'Traceback', 'CRITIQUE')
if _os_journal.environ.get('EGALYX_TRACES') == '1' and not _JOURNAL.handlers:
    _JOURNAL.setLevel(_logging_journal.DEBUG)
    _h = _logging_journal.StreamHandler()
    _h.setFormatter(_logging_journal.Formatter('%(asctime)s %(name)s %(levelname)s %(message)s'))
    _JOURNAL.addHandler(_h)
    _JOURNAL.propagate = False


def _journal(*args, sep=' ', **_ignore):
    """Ancien print() : écrit dans le journal au lieu de la sortie standard."""
    try:
        texte = sep.join(str(a) for a in args)
    except Exception:  # noqa: BLE001
        return
    if any(m in texte for m in _MOTS_ALERTE) and not texte.lstrip().startswith(('\u2705', '\u2713')):
        _JOURNAL.warning(texte)
    elif _JOURNAL.isEnabledFor(_logging_journal.DEBUG):
        _JOURNAL.debug(texte)
# --- fin du journal
import os
import json
from typing import Optional, Dict, Any

try:
    import openai
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    _journal("⚠️ OpenAI non disponible")

class APIIntegration:
    """Intégration avec les APIs IA externes"""
    
    @staticmethod
    def analyser_avec_openai(audit_data: Dict[str, Any], api_key: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Analyser un audit avec OpenAI
        
        Args:
            audit_data: Données de l'audit
            api_key: Clé API OpenAI (optionnelle, utilise la variable d'environnement par défaut)
        
        Returns:
            Dict avec les résultats de l'analyse ou None en cas d'erreur
        """
        if not OPENAI_AVAILABLE:
            _journal("❌ OpenAI non disponible")
            return None
        
        try:
            # Utiliser la clé fournie ou celle de l'environnement
            api_key = api_key or os.getenv('OPENAI_API_KEY')
            
            if not api_key:
                _journal("❌ Clé API OpenAI manquante")
                return None
            
            client = OpenAI(api_key=api_key)
            
            # Construire le prompt
            prompt = f"""
            Analyse cet audit et fournis des recommandations:
            
            Titre: {audit_data.get('titre', 'Non spécifié')}
            Description: {audit_data.get('description', 'Non spécifiée')}
            Nombre de constatations: {audit_data.get('nb_constatations', 0)}
            Nombre de recommandations: {audit_data.get('nb_recommandations', 0)}
            
            Constatations principales:
            {json.dumps(audit_data.get('constatations', []), ensure_ascii=False, indent=2)}
            
            Fournis une analyse structurée avec:
            1. 3-5 recommandations concrètes et actionnables
            2. Les causes racines identifiées
            3. Une évaluation de la gravité globale
            4. Des suggestions d'actions prioritaires
            
            Format de réponse JSON avec ces champs:
            - recommandations_ia (liste)
            - causes_racines (liste)
            - evaluation_gravite (texte)
            - actions_prioritaires (liste)
            - score_confiance (nombre)
            """
            
            response = client.chat.completions.create(
                model="gpt-4-turbo-preview",  # ou "gpt-3.5-turbo" pour un coût réduit
                messages=[
                    {
                        "role": "system", 
                        "content": "Tu es un expert en audit et contrôle interne. Tu fournis des analyses précises et des recommandations pratiques."
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                temperature=0.7,
                max_tokens=1500,
                response_format={"type": "json_object"}
            )
            
            result_text = response.choices[0].message.content
            
            try:
                result = json.loads(result_text)
                return result
            except json.JSONDecodeError as e:
                _journal(f"❌ Erreur décodage JSON: {e}")
                _journal(f"Texte reçu: {result_text[:500]}...")
                return None
            
        except openai.OpenAIError as e:
            _journal(f"❌ Erreur OpenAI API: {e}")
            return None
        except Exception as e:
            _journal(f"❌ Erreur inattendue: {e}")
            return None
    
    @staticmethod
    def analyser_avec_gemini(audit_data: Dict[str, Any], api_key: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Analyser avec Google Gemini
        """
        try:
            import google.generativeai as genai
            
            api_key = api_key or os.getenv('GEMINI_API_KEY')
            
            if not api_key:
                _journal("❌ Clé API Gemini manquante")
                return None
            
            genai.configure(api_key=api_key)
            
            # Sélectionner un modèle
            model = genai.GenerativeModel('gemini-pro')
            
            prompt = f"""
            Analyse cet audit et fournis des recommandations:
            
            {json.dumps(audit_data, indent=2)}
            
            Fournis une réponse en JSON.
            """
            
            response = model.generate_content(prompt)
            
            # Essayer d'extraire du JSON de la réponse
            import re
            
            # Chercher du JSON dans la réponse
            json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
            
            if json_match:
                try:
                    result = json.loads(json_match.group())
                    return result
                except json.JSONDecodeError:
                    # Si échec, retourner la réponse textuelle
                    return {'reponse_textuelle': response.text}
            else:
                return {'reponse_textuelle': response.text}
                
        except ImportError:
            _journal("❌ Google Generative AI non installé")
            return None
        except Exception as e:
            _journal(f"❌ Erreur Gemini: {e}")
            return None
    
    @staticmethod
    def analyser_avec_anthropic(audit_data: Dict[str, Any], api_key: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Analyser avec Anthropic Claude
        """
        try:
            import anthropic
            
            api_key = api_key or os.getenv('ANTHROPIC_API_KEY')
            
            if not api_key:
                _journal("❌ Clé API Anthropic manquante")
                return None
            
            client = anthropic.Anthropic(api_key=api_key)
            
            prompt = f"""
            Analyse cet audit et fournis des recommandations:
            
            {json.dumps(audit_data, indent=2)}
            
            Fournis une réponse en JSON.
            """
            
            response = client.messages.create(
                model="claude-3-opus-20240229",  # ou "claude-3-sonnet-20240229" pour un coût réduit
                max_tokens=1000,
                temperature=0.7,
                system="Tu es un expert en audit et contrôle interne.",
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )
            
            # Traiter la réponse
            result_text = response.content[0].text
            
            try:
                # Essayer d'extraire du JSON
                import re
                json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
                
                if json_match:
                    result = json.loads(json_match.group())
                    return result
                else:
                    return {'reponse_textuelle': result_text}
                    
            except json.JSONDecodeError:
                return {'reponse_textuelle': result_text}
                
        except ImportError:
            _journal("❌ Anthropic non installé")
            return None
        except Exception as e:
            _journal(f"❌ Erreur Anthropic: {e}")
            return None
