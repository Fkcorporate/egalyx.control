# collecte_engine.py

import json
import requests
import pandas as pd
from datetime import datetime, timedelta
from sqlalchemy import create_engine
import logging
from typing import Any, Dict, List, Optional
import jsonpath_ng

logger = logging.getLogger(__name__)

class CollecteEngine:
    """Moteur intelligent de collecte de données multi-sources"""
    
    def __init__(self, app=None, db=None):
        self.app = app
        self.db = db
        self.transformateurs_cache = {}
        
    def collecter_source(self, source_id: int, force: bool = False) -> Dict[str, Any]:
        """Collecte les données d'une source spécifique"""
        from models import SourceDonnee, SourceKRILink, CollecteDonnee, db
        
        source = SourceDonnee.query.get(source_id)
        if not source:
            return {'success': False, 'error': 'Source inexistante'}
        
        if source.statut != 'actif' and not force:
            return {'success': False, 'error': 'Source inactive'}
        
        # Vérifier si c'est le moment de collecter
        if not force and source.prochaine_execution and source.prochaine_execution > datetime.utcnow():
            return {'success': False, 'error': 'Pas encore l\'heure de la collecte'}
        
        resultats = {
            'source': source.nom,
            'timestamp': datetime.utcnow().isoformat(),
            'kri_collectes': [],
            'erreurs': []
        }
        
        try:
            # Récupérer les données brutes selon le type de source
            donnees_brutes = self._recuperer_donnees_brutes(source)
            
            # Pour chaque KRI lié à cette source
            for link in source.kri_associes:
                if not link.est_actif:
                    continue
                
                try:
                    # Extraire la valeur spécifique pour ce KRI
                    valeur = self._extraire_valeur(link, donnees_brutes)
                    
                    # Valider la valeur
                    validation = link.valider_valeur(valeur)
                    
                    # Créer l'enregistrement de collecte
                    collecte = CollecteDonnee(
                        source_link_id=link.id,
                        valeur=valeur,
                        donnees_brutes=donnees_brutes if link == source.kri_associes[0] else None,
                        metadonnees={
                            'timestamp': datetime.utcnow().isoformat(),
                            'validation': validation
                        },
                        statut='succes' if validation['valide'] else 'avertissement',
                        message=validation.get('message', ''),
                        date_valeur=datetime.utcnow()
                    )
                    
                    db.session.add(collecte)
                    db.session.flush()
                    
                    # Créer automatiquement la mesure KRI
                    if validation['valide']:
                        mesure = collecte.creer_mesure_kri()
                        resultats['kri_collectes'].append({
                            'kri_id': link.kri_id,
                            'valeur': valeur,
                            'mesure_id': mesure.id,
                            'collecte_id': collecte.id
                        })
                    else:
                        resultats['erreurs'].append({
                            'kri_id': link.kri_id,
                            'error': validation['message']
                        })
                    
                except Exception as e:
                    logger.error(f"Erreur pour KRI {link.kri_id}: {e}")
                    resultats['erreurs'].append({
                        'kri_id': link.kri_id,
                        'error': str(e)
                    })
            
            # Mettre à jour la source
            source.derniere_execution = datetime.utcnow()
            source.prochaine_execution = self._calculer_prochaine_execution(source)
            source.statut = 'actif' if not resultats['erreurs'] else 'erreur'
            
            db.session.commit()
            
        except Exception as e:
            logger.error(f"Erreur globale pour source {source_id}: {e}")
            db.session.rollback()
            source.statut = 'erreur'
            source.derniere_execution = datetime.utcnow()
            db.session.commit()
            resultats['erreurs'].append({'global': str(e)})
        
        return resultats
    
    def _recuperer_donnees_brutes(self, source):
        """Récupère les données brutes selon le type de source"""
        config = source.config_connexion
        auth = source.get_decrypted_auth() if source.auth_config else None
        
        if source.type_source == 'api':
            return self._recuperer_depuis_api(config, auth)
        elif source.type_source == 'base_donnees':
            return self._recuperer_depuis_bdd(config, auth)
        elif source.type_source == 'fichier':
            return self._recuperer_depuis_fichier(config)
        else:
            raise ValueError(f"Type source non supporté: {source.type_source}")
    
    def _recuperer_depuis_api(self, config, auth):
        """Récupère depuis une API"""
        url = config.get('url')
        method = config.get('method', 'GET')
        headers = config.get('headers', {})
        params = config.get('params', {})
        
        # Ajout de l'authentification
        if auth:
            auth_type = auth.get('type')
            if auth_type == 'bearer':
                headers['Authorization'] = f"Bearer {auth.get('token')}"
            elif auth_type == 'basic':
                auth_tuple = (auth.get('username'), auth.get('password'))
                response = requests.request(method, url, headers=headers, params=params, auth=auth_tuple)
                response.raise_for_status()
                return self._parse_reponse_api(response)
            elif auth_type == 'api_key':
                if auth.get('in_header'):
                    headers[auth.get('key_name')] = auth.get('key_value')
                else:
                    params[auth.get('key_name')] = auth.get('key_value')
        
        response = requests.request(method, url, headers=headers, params=params)
        response.raise_for_status()
        return self._parse_reponse_api(response)
    
    def _parse_reponse_api(self, response):
        """Parse la réponse API"""
        content_type = response.headers.get('content-type', '')
        if 'application/json' in content_type:
            return response.json()
        elif 'text/csv' in content_type:
            return response.text
        else:
            return response.text
    
    def _recuperer_depuis_bdd(self, config, auth):
        """Récupère depuis une base de données"""
        db_type = config.get('type', 'postgresql')
        host = config.get('host')
        port = config.get('port')
        database = config.get('database')
        username = auth.get('username') if auth else None
        password = auth.get('password') if auth else None
        requete = config.get('requete')
        
        if not requete:
            raise ValueError("Pas de requête SQL configurée")
        
        # Construction chaîne de connexion
        if db_type == 'postgresql':
            conn_str = f"postgresql://{username}:{password}@{host}:{port}/{database}"
        elif db_type == 'mysql':
            conn_str = f"mysql+pymysql://{username}:{password}@{host}:{port}/{database}"
        else:
            conn_str = f"sqlite:///{database}"
        
        engine = create_engine(conn_str)
        with engine.connect() as conn:
            df = pd.read_sql(requete, conn)
        
        return df.to_dict(orient='records')
    
    def _recuperer_depuis_fichier(self, config):
        """Récupère depuis un fichier"""
        chemin = config.get('chemin')
        format_fichier = config.get('format', 'csv')
        
        if format_fichier == 'csv':
            df = pd.read_csv(chemin)
            return df.to_dict(orient='records')
        elif format_fichier == 'excel':
            df = pd.read_excel(chemin)
            return df.to_dict(orient='records')
        elif format_fichier == 'json':
            with open(chemin, 'r') as f:
                return json.load(f)
        else:
            raise ValueError(f"Format non supporté: {format_fichier}")
    
    def _extraire_valeur(self, link, donnees):
        """Extrait la valeur pour un KRI"""
        from models import TransformateurDonnee
        
        # Si transformateur configuré
        if link.transformateur:
            transformateur = TransformateurDonnee.query.filter_by(nom=link.transformateur).first()
            if transformateur:
                return transformateur.appliquer(donnees, **link.mapping_config)
        
        # Extraction par chemin JSON
        if link.chemin_donnee:
            return self._extraire_par_chemin(donnees, link.chemin_donnee)
        
        # Extraction par mapping
        if link.mapping_config:
            return self._extraire_par_mapping(donnees, link.mapping_config)
        
        # Si les données sont directement un nombre
        if isinstance(donnees, (int, float)):
            return float(donnees)
        
        raise ValueError("Aucune méthode d'extraction configurée")
    
    def _extraire_par_chemin(self, donnees, chemin):
        """Extrait avec JSONPath"""
        expr = jsonpath_ng.parse(chemin)
        matches = [match.value for match in expr.find(donnees)]
        
        if not matches:
            raise ValueError(f"Aucune donnée trouvée pour: {chemin}")
        
        # Si plusieurs résultats, prendre le premier
        try:
            return float(matches[0])
        except (TypeError, ValueError):
            raise ValueError(f"Impossible de convertir en nombre: {matches[0]}")
    
    def _extraire_par_mapping(self, donnees, mapping):
        """Extrait avec mapping"""
        if isinstance(donnees, list):
            operation = mapping.get('operation', 'sum')
            champ = mapping.get('champ')
            
            if champ:
                valeurs = [float(d.get(champ, 0)) for d in donnees if champ in d]
            else:
                valeurs = [float(d) for d in donnees if isinstance(d, (int, float))]
            
            if operation == 'sum':
                return sum(valeurs)
            elif operation == 'avg':
                return sum(valeurs) / len(valeurs) if valeurs else 0
            elif operation == 'min':
                return min(valeurs) if valeurs else 0
            elif operation == 'max':
                return max(valeurs) if valeurs else 0
            elif operation == 'count':
                return len(valeurs)
        
        elif isinstance(donnees, dict):
            champ = mapping.get('champ')
            if champ and champ in donnees:
                return float(donnees[champ])
        
        raise ValueError(f"Impossible d'extraire avec mapping: {mapping}")
    
    def _calculer_prochaine_execution(self, source):
        """Calcule la prochaine exécution"""
        from dateutil.relativedelta import relativedelta
        return datetime.utcnow() + relativedelta(seconds=source.frequence_rafraichissement)