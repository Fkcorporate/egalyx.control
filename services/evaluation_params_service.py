# services/evaluation_params_service.py

from datetime import datetime
from flask import current_app, session
from models import ParametreEvaluation, GuideEvaluation
import json

class EvaluationParamsService:
    """Service de gestion des paramètres d'évaluation avec cache et multi-tenant"""
    
    _cache = {}
    _cache_time = {}
    CACHE_DURATION = 60  # secondes
    
    @classmethod
    def get_parametres(cls, client_id, categorie=None, force_refresh=False):
        """Récupère les paramètres d'évaluation avec cache multi-tenant"""
        cache_key = f"{client_id}:{categorie or 'all'}"
        
        if force_refresh:
            cls._cache.pop(cache_key, None)
            cls._cache_time.pop(cache_key, None)
        
        if cache_key in cls._cache:
            cache_time = cls._cache_time.get(cache_key, 0)
            if (datetime.now() - cache_time).total_seconds() < cls.CACHE_DURATION:
                return cls._cache[cache_key]
        
        query = ParametreEvaluation.query.filter_by(client_id=client_id, est_actif=True)
        if categorie:
            query = query.filter_by(categorie=categorie)
        
        parametres = query.order_by(ParametreEvaluation.ordre, ParametreEvaluation.niveau).all()
        
        result = {}
        for param in parametres:
            if param.categorie not in result:
                result[param.categorie] = []
            result[param.categorie].append({
                'id': param.id,
                'niveau': param.niveau,
                'nom_court': param.nom_court,
                'description_longue': param.description_longue,
                'couleur_hex': param.couleur_hex,
                'ordre': param.ordre,
                'est_actif': param.est_actif
            })
        
        cls._cache[cache_key] = result
        cls._cache_time[cache_key] = datetime.now()
        return result
    
    @classmethod
    def get_niveau_couleur(cls, client_id, categorie, niveau):
        """Retourne la couleur pour un niveau donné"""
        parametres = cls.get_parametres(client_id, categorie)
        if categorie in parametres:
            for param in parametres[categorie]:
                if param['niveau'] == niveau:
                    return param['couleur_hex']
        
        default_colors = {
            'impact': {1: '#28a745', 2: '#8bc34a', 3: '#ffc107', 4: '#ff9800', 5: '#dc3545'},
            'probabilite': {1: '#28a745', 2: '#8bc34a', 3: '#ffc107', 4: '#ff9800', 5: '#dc3545'},
            'maitrise': {1: '#dc3545', 2: '#ff9800', 3: '#ffc107', 4: '#8bc34a', 5: '#28a745'}
        }
        return default_colors.get(categorie, {}).get(niveau, '#6c757d')
    
    @classmethod
    def get_niveau_nom_court(cls, client_id, categorie, niveau):
        """Retourne le nom court pour un niveau donné"""
        parametres = cls.get_parametres(client_id, categorie)
        if categorie in parametres:
            for param in parametres[categorie]:
                if param['niveau'] == niveau:
                    return param['nom_court']
        
        default_names = {
            'impact': {1: 'Négligeable', 2: 'Mineur', 3: 'Modéré', 4: 'Important', 5: 'Critique'},
            'probabilite': {1: 'Très rare', 2: 'Rare', 3: 'Possible', 4: 'Probable', 5: 'Très probable'},
            'maitrise': {1: 'Très faible', 2: 'Faible', 3: 'Moyenne', 4: 'Bonne', 5: 'Très bonne'}
        }
        return default_names.get(categorie, {}).get(niveau, f'Niveau {niveau}')
    
    @classmethod
    def get_niveau_description(cls, client_id, categorie, niveau):
        """Retourne la description pour un niveau donné"""
        parametres = cls.get_parametres(client_id, categorie)
        if categorie in parametres:
            for param in parametres[categorie]:
                if param['niveau'] == niveau:
                    return param['description_longue']
        
        default_descriptions = {
            'impact': {
                1: "🟢 Conséquences négligeables, sans impact significatif",
                2: "🟢 Conséquences mineures, impact limité",
                3: "🟡 Conséquences modérées, impact notable",
                4: "🟠 Conséquences importantes, impact significatif",
                5: "🔴 Conséquences critiques, menace grave"
            },
            'probabilite': {
                1: "🟢 Événement exceptionnel (< 1%)",
                2: "🟢 Événement peu fréquent (1-10%)",
                3: "🟡 Événement possible (10-30%)",
                4: "🟠 Événement probable (30-60%)",
                5: "🔴 Événement très probable (> 60%)"
            },
            'maitrise': {
                1: "🔴 Contrôle inexistant ou très insuffisant",
                2: "🟠 Contrôle faible, efficacité limitée",
                3: "🟡 Contrôle modéré, partiellement efficace",
                4: "🟢 Contrôle bon, efficace",
                5: "🟢 Contrôle excellent, très efficace"
            }
        }
        return default_descriptions.get(categorie, {}).get(niveau, 'Description non définie')
    
    @classmethod
    def get_parametres_evaluation(cls, client_id):
        """Retourne tous les paramètres d'évaluation formatés pour le template"""
        parametres = cls.get_parametres(client_id)
        
        result = {
            'impact': {},
            'probabilite': {},
            'maitrise': {}
        }
        
        for categorie, items in parametres.items():
            if categorie in result:
                for item in items:
                    result[categorie][item['niveau']] = {
                        'nom': item['nom_court'],
                        'description': item['description_longue'],
                        'couleur': item['couleur_hex']
                    }
        
        result['maitrise_inverse'] = True
        return result
    
    @classmethod
    def get_guide_sections(cls, client_id, force_refresh=False):
        """Récupère les sections du guide d'évaluation"""
        cache_key = f"guide:{client_id}"
        
        if force_refresh:
            cls._cache.pop(cache_key, None)
        
        if cache_key in cls._cache:
            return cls._cache[cache_key]
        
        sections = GuideEvaluation.query.filter_by(
            client_id=client_id,
            est_actif=True
        ).order_by(GuideEvaluation.ordre).all()
        
        result = [{
            'id': s.id,
            'section': s.section,
            'titre': s.titre,
            'contenu': s.contenu,
            'ordre': s.ordre
        } for s in sections]
        
        cls._cache[cache_key] = result
        return result
    
    @classmethod
    def invalidate_cache(cls, client_id=None):
        """Invalide le cache pour un client ou pour tous"""
        if client_id:
            keys_to_remove = [k for k in cls._cache.keys() if str(client_id) in k]
            for key in keys_to_remove:
                cls._cache.pop(key, None)
                cls._cache_time.pop(key, None)
        else:
            cls._cache.clear()
            cls._cache_time.clear()
