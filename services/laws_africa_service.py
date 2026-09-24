# services/laws_africa_service.py
"""
Service de connexion à l'API Laws.Africa (couvre l'OHADA).
Documentation : https://laws.africa/platform
"""

import requests
from typing import Optional, Dict, List


class LawsAfricaService:
    """Client pour l'API Laws.Africa"""
    
    BASE_URL = "https://api.laws.africa/v3"
    
    def __init__(self, api_token: str):
        self.api_token = api_token
        self.headers = {
            'Authorization': f'Token {api_token}',
            'Accept': 'application/json'
        }
    
    def _request(self, endpoint: str, **kwargs) -> Dict:
        """Effectue une requête authentifiée"""
        url = f"{self.BASE_URL}{endpoint}"
        response = requests.get(url, headers=self.headers, timeout=30, **kwargs)
        response.raise_for_status()
        return response.json()
    
    # ============================================
    # MÉTHODES MÉTIER
    # ============================================
    
    def get_zones(self) -> List[Dict]:
        """Liste les zones disponibles (pays)"""
        return self._request('/akn/')
    
    def get_works(self, area: str = 'ohada') -> List[Dict]:
        """
        Récupère les travaux législatifs pour une zone.
        'ohada' pour les textes OHADA.
        """
        return self._request(f'/akn/{area}/')
    
    def rechercher(self, query: str, area: str = 'ohada') -> List[Dict]:
        """Recherche dans les textes"""
        return self._request(f'/akn/{area}/search/', params={'q': query})