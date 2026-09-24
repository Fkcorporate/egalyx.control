# services/legifrance_service.py
"""
Service de connexion à l'API Légifrance via PISTE.
Documentation : https://piste.gouv.fr
"""

import os
import requests
from datetime import datetime, timedelta
from typing import Optional, Dict, List


class LegifranceService:
    """Client pour l'API Légifrance"""
    
    # URLs PISTE
    SANDBOX_OAUTH_URL = "https://sandbox-oauth.piste.gouv.fr/api/oauth/token"
    PROD_OAUTH_URL = "https://oauth.piste.gouv.fr/api/oauth/token"
    
    SANDBOX_API_URL = "https://sandbox-api.piste.gouv.fr/dila/legifrance/lf-engine-app"
    PROD_API_URL = "https://api.piste.gouv.fr/dila/legifrance/lf-engine-app"
    
    def __init__(self, client_id: str, client_secret: str, sandbox: bool = True):
        self.client_id = client_id
        self.client_secret = client_secret
        self.sandbox = sandbox
        self.oauth_url = self.SANDBOX_OAUTH_URL if sandbox else self.PROD_OAUTH_URL
        self.api_url = self.SANDBOX_API_URL if sandbox else self.PROD_API_URL
        self._access_token = None
        self._token_expires_at = None
    
    # ============================================
    # AUTHENTIFICATION
    # ============================================
    
    def _get_access_token(self) -> str:
        """Récupère un token OAuth 2.0 (cache 1h)"""
        if self._access_token and self._token_expires_at:
            if datetime.utcnow() < self._token_expires_at - timedelta(minutes=5):
                return self._access_token
        
        response = requests.post(
            self.oauth_url,
            data={
                'grant_type': 'client_credentials',
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'scope': 'openid'
            },
            timeout=30
        )
        response.raise_for_status()
        data = response.json()
        
        self._access_token = data['access_token']
        self._token_expires_at = datetime.utcnow() + timedelta(seconds=data.get('expires_in', 3600))
        return self._access_token
    
    def _request(self, method: str, endpoint: str, **kwargs) -> Dict:
        """Effectue une requête authentifiée"""
        token = self._get_access_token()
        headers = {
            'Authorization': f'Bearer {token}',
            'Accept': 'application/json'
        }
        if method.upper() == 'POST':
            headers['Content-Type'] = 'application/json'
        
        url = f"{self.api_url}{endpoint}"
        response = requests.request(method, url, headers=headers, timeout=30, **kwargs)
        response.raise_for_status()
        return response.json()
    
    # ============================================
    # MÉTHODES MÉTIER
    # ============================================
    
    def ping(self) -> Dict:
        """Test de connexion"""
        return self._request('GET', '/list/ping')
    
    def get_derniers_jo(self, nb: int = 10) -> List[Dict]:
        """
        Récupère les derniers Journaux Officiels.
        Endpoint : /consult/lastNJo [citation:18]
        """
        return self._request('POST', '/consult/lastNJo', json={'nbJo': nb})
    
    def get_textes_jo(self, jorfcont_id: str) -> List[Dict]:
        """
        Récupère les textes d'un JO.
        Endpoint : /consult/jorfCont [citation:18]
        """
        return self._request('POST', '/consult/jorfCont', json={
            'id': jorfcont_id,
            'pageNumber': 1,
            'pageSize': 100
        })
    
    def get_texte_complet(self, jorftext_id: str) -> Dict:
        """
        Récupère le contenu complet d'un texte.
        Endpoint : /consult/jorf [citation:18]
        """
        return self._request('POST', '/consult/jorf', json={
            'textId': jorftext_id
        })
    
    def rechercher(self, query: str, fond: str = 'LODA_DATE', 
                   page: int = 1, taille: int = 10) -> Dict:
        """
        Recherche dans Légifrance.
        Endpoint : /search [citation:16]
        """
        return self._request('POST', '/search', json={
            'recherche': {
                'champs': [{
                    'typeChamp': 'ALL',
                    'criteres': [{
                        'typeRecherche': 'UN_DES_MOTS',
                        'valeur': query,
                        'operateur': 'ET'
                    }],
                    'operateur': 'ET'
                }],
                'filtres': [{'facette': 'DATE_VERSION', 'valeurs': []}],
                'pageNumber': page,
                'pageSize': taille,
                'sort': 'PERTINENCE',
                'typePagination': 'DEFAUT',
            },
            'fond': fond
        })