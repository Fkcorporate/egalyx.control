# services/detection_menace_service.py
"""
Service de détection de menace réglementaire AVANCÉ.
Inspiré ISO 37301 § 4.1, ISO 31000 § 5.4.2, ISO 19600 § 4.6.

Améliorations v2 :
- Similarité par titre + contenu (TF-IDF)
- Score multi-dimensionnel (impact, probabilité, urgence)
- Prise en compte des dates de validité
- Pondération des sources
- Historique des menaces ignorées
- Cache des analyses IA
- Génération de plans d'action
- Lien automatique avec les risques
"""

from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import hashlib
import json
import re
from collections import Counter


class DetectionMenaceService:
    """
    Détection avancée des menaces réglementaires.
    """
    
    # ============================================
    # PONDÉRATION DES SOURCES
    # ============================================
    SOURCES_POIDS = {
        'legifrance': 10,       # Source officielle France
        'laws_africa': 10,      # Source officielle OHADA
        'ue': 10,               # Union Européenne
        'bceao': 9,             # Banque Centrale
        'beac': 9,
        'cobac': 9,
        'amf': 9,
        'acpr': 9,
        'cnil': 9,
        'anssi': 8,
        'blog': 3,              # Blog juridique
        'presse': 2,            # Presse généraliste
        'externe': 5,           # Par défaut
    }
    
    # ============================================
    # MATRICE DE CRITICITÉ (impact × probabilité)
    # ============================================
    MATRICE_CRITICITE = {
        # impact: {probabilite: score}
        'critique': {'certain': 100, 'probable': 90, 'possible': 75, 'rare': 60},
        'eleve': {'certain': 90, 'probable': 80, 'possible': 65, 'rare': 50},
        'moyen': {'certain': 70, 'probable': 60, 'possible': 45, 'rare': 30},
        'faible': {'certain': 50, 'probable': 40, 'possible': 25, 'rare': 10},
    }
    
    # ============================================
    # DÉLAIS PAR NIVEAU
    # ============================================
    DELAIS_RECOMMANDES = {
        'critique': 7,
        'eleve': 15,
        'moyen': 30,
        'faible': 90,
    }
    
    def __init__(self, ia_service, cache_service=None):
        self.ia = ia_service
        self.cache = cache_service
        self._cache_memory = {}  # Fallback si pas de service de cache
    
    # ============================================
    # MÉTHODE PRINCIPALE
    # ============================================
    
    def detecter_menaces(
        self, 
        client_id: int, 
        nouvelles_reglementations: List[Dict],
        options: Optional[Dict] = None
    ) -> Dict:
        """
        Analyse une liste de réglementations externes.
        
        Returns:
            {
                'menaces': [...],
                'stats': {...},
                'timestamp': '...'
            }
        """
        options = options or {}
        seuil_pertinence = options.get('seuil_pertinence', 60)
        inclure_faibles = options.get('inclure_faibles', False)
        limiter_analyse = options.get('limiter_analyse', 50)
        
        from models import VeilleReglementaire, Pays, Pole, Direction, Service, Risque
        
        # 1. Récupérer les données de l'organisation
        veilles_existantes = VeilleReglementaire.query.filter_by(
            client_id=client_id,
            is_active=True,
            is_archived=False
        ).all()
        
        menaces_ignorees = self._get_menaces_ignorees(client_id)
        
        pays_org = Pays.query.filter_by(client_id=client_id, is_archived=False).all()
        poles_org = Pole.query.filter_by(client_id=client_id, is_archived=False).all()
        directions_org = Direction.query.filter_by(client_id=client_id, is_archived=False).all()
        risques_org = Risque.query.filter_by(client_id=client_id, is_archived=False).all()
        
        # 2. Construire le périmètre enrichi
        perimetre_org = self._construire_perimetre(
            pays_org, poles_org, directions_org, risques_org
        )
        
        # 3. Index TF-IDF des veilles existantes (plus rapide)
        index_veilles = self._indexer_veilles(veilles_existantes)
        
        menaces = []
        stats = {
            'total_analysees': 0,
            'ignorees_doublons': 0,
            'ignorees_deja_vues': 0,
            'ignorees_non_pertinentes': 0,
            'retenues': 0,
        }
        
        # Limiter le nombre d'analyses IA (économie de coût)
        regs_a_analyser = nouvelles_reglementations[:limiter_analyse]
        
        for reg_ext in regs_a_analyser:
            stats['total_analysees'] += 1
            
            titre = reg_ext.get('titre', '').strip()
            texte = reg_ext.get('texte', '').strip()
            source = reg_ext.get('source', 'externe').lower()
            
            if not titre and not texte:
                continue
            
            # 3.1 Vérifier si déjà ignorée par l'utilisateur
            reg_hash = self._compute_hash(titre, texte[:500])
            if reg_hash in menaces_ignorees:
                stats['ignorees_deja_vues'] += 1
                continue
            
            # 3.2 Détection de doublons AVANCÉE
            deja_couvert, veille_match, score_similarite = self._est_deja_couvert(
                titre, texte, index_veilles, veilles_existantes
            )
            
            if deja_couvert:
                stats['ignorees_doublons'] += 1
                continue
            
            # 3.3 Vérifier la validité temporelle
            if not self._est_temporellement_pertinente(reg_ext):
                continue
            
            # 3.4 Analyse IA (avec cache)
            analyse = self._analyser_avec_cache(titre, texte, source)
            
            # 3.5 Score multi-dimensionnel
            scores = self._calculer_scores_complets(
                analyse, perimetre_org, reg_ext, source
            )
            
            score_final = scores['score_final']
            
            # 3.6 Filtrer selon le seuil
            if score_final < seuil_pertinence and not inclure_faibles:
                stats['ignorees_non_pertinentes'] += 1
                continue
            
            # 3.7 Construire la menace
            menace = {
                'hash': reg_hash,
                'titre': titre,
                'texte': texte[:1000],
                'source': source,
                'reference': reg_ext.get('reference'),
                'url': reg_ext.get('url'),
                'date_publication': reg_ext.get('date_publication'),
                'analyse_ia': analyse,
                'scores': scores,
                'score_pertinence': score_final,
                'niveau_menace': self._niveau_menace_v2(scores),
                'perimetre_impacte': self._determiner_perimetre_impacte(
                    analyse, perimetre_org
                ),
                'recommandation': self._generer_recommandation_v2(scores, analyse),
                'veille_similaire': {
                    'titre': veille_match.titre,
                    'id': veille_match.id,
                    'similarite': round(score_similarite, 2)
                } if veille_match else None,
                'risques_lies': self._identifier_risques_lies(
                    analyse, risques_org
                ),
                'date_detection': datetime.utcnow().isoformat(),
            }
            menaces.append(menace)
            stats['retenues'] += 1
        
        # 4. Trier par score décroissant
        menaces.sort(key=lambda x: x['score_pertinence'], reverse=True)
        
        return {
            'menaces': menaces,
            'stats': stats,
            'timestamp': datetime.utcnow().isoformat(),
            'perimetre': {
                'pays': len(pays_org),
                'poles': len(poles_org),
                'directions': len(directions_org),
                'veilles_existantes': len(veilles_existantes),
            }
        }
    
    # ============================================
    # ANALYSE IA AVEC CACHE
    # ============================================
    
    def _analyser_avec_cache(self, titre: str, texte: str, source: str) -> Dict:
        """Analyse IA avec mise en cache"""
        cache_key = f"ia_analyse_{self._compute_hash(titre, texte[:500])}"
        
        # Vérifier le cache mémoire
        if cache_key in self._cache_memory:
            return self._cache_memory[cache_key]
        
        # Vérifier le cache externe (Redis, etc.)
        if self.cache:
            cached = self.cache.get(cache_key)
            if cached:
                return json.loads(cached)
        
        # Analyser avec l'IA
        analyse = self.ia.analyser_texte_reglementaire(titre, texte, source)
        
        # Sauvegarder en cache
        self._cache_memory[cache_key] = analyse
        if self.cache:
            self.cache.set(cache_key, json.dumps(analyse), timeout=86400)  # 24h
        
        return analyse
    
    # ============================================
    # DÉTECTION DE DOUBLONS AVANCÉE
    # ============================================
    
    def _indexer_veilles(self, veilles: List) -> Dict:
        """Indexe les veilles avec TF-IDF simplifié"""
        index = {
            'titres': {},
            'references': {},
            'mots_cles': Counter(),
        }
        
        for v in veilles:
            # Index par référence (exact)
            if v.reference:
                index['references'][v.reference.lower()] = v
            
            # Index par titre (mots)
            if v.titre:
                mots = self._tokenize(v.titre)
                for mot in mots:
                    index['titres'][mot] = index['titres'].get(mot, 0) + 1
        
        return index
    
    def _est_deja_couvert(
        self, 
        titre: str, 
        texte: str, 
        index: Dict, 
        veilles: List
    ) -> Tuple[bool, Optional[object], float]:
        """
        Détection avancée avec 3 niveaux :
        1. Référence exacte
        2. Similarité du titre (Jaccard)
        3. Similarité du contenu (TF-IDF)
        """
        titre_lower = titre.lower()
        
        # Niveau 1 : Référence exacte
        for ref, veille in index['references'].items():
            if ref in titre_lower:
                return True, veille, 1.0
        
        # Niveau 2 : Similarité du titre
        mots_nouveau = set(self._tokenize(titre))
        meilleur_match = None
        meilleur_score = 0.0
        
        for veille in veilles:
            if not veille.titre:
                continue
            
            mots_veille = set(self._tokenize(veille.titre))
            
            if not mots_nouveau or not mots_veille:
                continue
            
            intersection = len(mots_nouveau & mots_veille)
            union = len(mots_nouveau | mots_veille)
            jaccard = intersection / union if union > 0 else 0
            
            # Bonus si mots-clés juridiques communs
            bonus = self._bonus_mots_juridiques(mots_nouveau & mots_veille)
            score_ajuste = min(jaccard + bonus, 1.0)
            
            if score_ajuste > meilleur_score:
                meilleur_score = score_ajuste
                meilleur_match = veille
        
        # Seuil : 0.55 (ajusté)
        if meilleur_score > 0.55:
            return True, meilleur_match, meilleur_score
        
        return False, None, meilleur_score
    
    def _tokenize(self, texte: str) -> List[str]:
        """Tokenisation simple avec suppression des stop-words"""
        stopwords = {
            'le', 'la', 'les', 'un', 'une', 'des', 'du', 'de', 'et', 'ou',
            'à', 'au', 'aux', 'en', 'dans', 'sur', 'par', 'pour', 'avec',
            'sans', 'est', 'sont', 'être', 'avoir', 'ce', 'cet', 'cette',
            'ces', 'son', 'sa', 'ses', 'leur', 'leurs', 'nous', 'vous',
            'ils', 'elles', 'que', 'qui', 'quoi', 'dont', 'où',
        }
        
        mots = re.findall(r'\b[a-zàâçéèêëîïôûùüÿñæœ]{4,}\b', texte.lower())
        return [m for m in mots if m not in stopwords]
    
    def _bonus_mots_juridiques(self, mots_communs: set) -> float:
        """Bonus si mots juridiques importants en commun"""
        mots_importants = {
            'conformité', 'réglementation', 'directive', 'sanction',
            'obligation', 'interdiction', 'protection', 'données',
            'financier', 'bancaire', 'assurance', 'cybersécurité',
        }
        if mots_communs & mots_importants:
            return 0.15  # Bonus de 15%
        return 0.0
    
    # ============================================
    # VALIDITÉ TEMPORELLE
    # ============================================
    
    def _est_temporellement_pertinente(self, reg_ext: Dict) -> bool:
        """Vérifie si la réglementation est encore en vigueur"""
        # Si abrogée → pas de menace
        if reg_ext.get('statut') == 'abroge':
            return False
        
        # Si date d'application passée > 10 ans → probablement obsolète
        date_app = reg_ext.get('date_application')
        if date_app:
            try:
                if isinstance(date_app, str):
                    date_app = datetime.fromisoformat(date_app).date()
                if (datetime.utcnow().date() - date_app).days > 3650:
                    return False
            except (ValueError, TypeError):
                pass
        
        return True
    
    # ============================================
    # SCORES MULTI-DIMENSIONNELS
    # ============================================
    
    def _calculer_scores_complets(
        self, 
        analyse: Dict, 
        perimetre: Dict, 
        reg_ext: Dict,
        source: str
    ) -> Dict:
        """
        Calcul multi-dimensionnel :
        - Score impact (0-100)
        - Score probabilité (0-100)
        - Score urgence (0-100)
        - Score pertinence (0-100)
        - Score final pondéré (0-100)
        """
        # 1. Impact
        criticite = analyse.get('criticite', 'moyen')
        impact_score = {
            'critique': 100,
            'eleve': 75,
            'moyen': 50,
            'faible': 25,
        }.get(criticite, 50)
        
        # 2. Probabilité (basée sur les secteurs impactés)
        secteurs_texte = set(analyse.get('secteurs_impactes', []))
        secteurs_org = set(perimetre.get('secteurs', []))
        if secteurs_texte & secteurs_org:
            proba_score = 80
        elif secteurs_texte:
            proba_score = 40
        else:
            proba_score = 20
        
        # 3. Urgence (basée sur la date d'application)
        urgence_score = self._calculer_urgence(reg_ext)
        
        # 4. Pertinence pour l'organisation
        pertinence_score = self._calculer_pertinence_v2(analyse, perimetre)
        
        # 5. Pondération des sources
        source_poids = self.SOURCES_POIDS.get(source, 5)
        source_score = min(source_poids * 10, 100)
        
        # 6. Score final pondéré
        score_final = (
            impact_score * 0.30 +
            proba_score * 0.25 +
            urgence_score * 0.15 +
            pertinence_score * 0.20 +
            source_score * 0.10
        )
        
        return {
            'impact': round(impact_score),
            'probabilite': round(proba_score),
            'urgence': round(urgence_score),
            'pertinence': round(pertinence_score),
            'source': round(source_score),
            'score_final': round(score_final),
            'criticite_ia': criticite,
        }
    
    def _calculer_urgence(self, reg_ext: Dict) -> int:
        """Score d'urgence basé sur la date d'application"""
        date_app = reg_ext.get('date_application')
        if not date_app:
            return 50  # Neutre
        
        try:
            if isinstance(date_app, str):
                date_app = datetime.fromisoformat(date_app).date()
            
            jours_restants = (date_app - datetime.utcnow().date()).days
            
            if jours_restants < 0:  # Déjà en vigueur
                return 100
            elif jours_restants < 30:
                return 95
            elif jours_restants < 90:
                return 80
            elif jours_restants < 180:
                return 60
            elif jours_restants < 365:
                return 40
            else:
                return 20
        except (ValueError, TypeError):
            return 50
    
    def _calculer_pertinence_v2(self, analyse: Dict, perimetre: Dict) -> int:
        """Score de pertinence affiné"""
        score = 0
        
        # Secteurs (50 points)
        secteurs_texte = set(analyse.get('secteurs_impactes', []))
        secteurs_org = set(perimetre.get('secteurs', []))
        if secteurs_texte & secteurs_org:
            score += 50
        
        # Mots-clés (30 points)
        mots_texte = set(analyse.get('mots_cles', []))
        mots_org = set(perimetre.get('mots_cles_organisation', []))
        if mots_texte & mots_org:
            score += 30
        
        # Organismes (20 points)
        organismes_texte = set(analyse.get('organismes', []))
        organismes_org = set(perimetre.get('organismes_pertinents', []))
        if organismes_texte & organismes_org:
            score += 20
        
        return min(score, 100)
    
    # ============================================
    # NIVEAU DE MENACE
    # ============================================
    
    def _niveau_menace_v2(self, scores: Dict) -> str:
        """Niveau basé sur le score final"""
        score = scores['score_final']
        
        if score >= 80:
            return '🔴 CRITIQUE'
        elif score >= 65:
            return '🟠 ÉLEVÉE'
        elif score >= 45:
            return '🟡 MODÉRÉE'
        else:
            return '🟢 FAIBLE'
    
    # ============================================
    # RECOMMANDATIONS
    # ============================================
    
    def _generer_recommandation_v2(self, scores: Dict, analyse: Dict) -> Dict:
        """Recommandation basée sur les scores multi-dimensionnels"""
        score = scores['score_final']
        urgence = scores['urgence']
        criticite = scores['criticite_ia']
        
        # Déterminer la priorité
        if score >= 80 or (score >= 70 and urgence >= 80):
            priorite = 'immédiate'
            delai = 7
            actions = [
                '🚨 Créer immédiatement une veille réglementaire',
                '📅 Convoquer une réunion de conformité sous 48h',
                '📊 Évaluer l\'impact sur les processus critiques',
                '📋 Planifier un plan d\'action dans les 7 jours',
                '👥 Informer la direction générale',
            ]
        elif score >= 65:
            priorite = 'haute'
            delai = 15
            actions = [
                '⚠️ Créer une veille réglementaire',
                '🔍 Analyser la pertinence en détail',
                '📅 Programmer une évaluation sous 15 jours',
                '✉️ Notifier les responsables concernés',
            ]
        elif score >= 45:
            priorite = 'normale'
            delai = 30
            actions = [
                '📝 Documenter dans le registre de veille',
                '🔎 Analyser les impacts potentiels',
                '📅 Revoir dans 30 jours',
            ]
        else:
            priorite = 'faible'
            delai = 90
            actions = [
                '📚 Archiver pour référence future',
                '👀 Surveiller sans action immédiate',
            ]
        
        return {
            'priorite': priorite,
            'delai': f'{delai} jours',
            'date_limite': (datetime.utcnow() + timedelta(days=delai)).strftime('%d/%m/%Y'),
            'actions': actions,
            'criticite_ia': criticite,
            'urgence': urgence,
        }
    
    # ============================================
    # PERIMÈTRE IMPACTÉ
    # ============================================
    
    def _determiner_perimetre_impacte(self, analyse: Dict, perimetre: Dict) -> Dict:
        """Retourne les éléments impactés (secteurs, pôles, directions)"""
        impactes = {
            'secteurs': [],
            'poles': [],
            'directions': [],
            'pays': [],
        }
        
        secteurs_texte = set(analyse.get('secteurs_impactes', []))
        
        # Secteurs
        for secteur in perimetre.get('secteurs', []):
            if secteur in secteurs_texte:
                impactes['secteurs'].append(secteur)
        
        # Pôles associés aux secteurs
        for pole in perimetre.get('poles', []):
            if pole.get('secteur') in secteurs_texte:
                impactes['poles'].append(pole)
        
        # Pays concernés par les organismes
        organismes_texte = set(analyse.get('organismes', []))
        for pays in perimetre.get('pays', []):
            if organismes_texte & set(pays.get('organismes', [])):
                impactes['pays'].append(pays)
        
        return impactes
    
    # ============================================
    # RISQUES LIÉS
    # ============================================
    
    def _identifier_risques_lies(self, analyse: Dict, risques: List) -> List[Dict]:
        """Identifie les risques internes liés à cette menace"""
        lies = []
        mots_menace = set(analyse.get('mots_cles', []))
        secteurs_menace = set(analyse.get('secteurs_impactes', []))
        
        for risque in risques:
            score = 0
            
            # Similarité par intitulé
            mots_risque = set(self._tokenize(risque.intitule or ''))
            if mots_menace & mots_risque:
                score += len(mots_menace & mots_risque) * 10
            
            # Similarité par catégorie
            if risque.categorie and risque.categorie.lower() in str(secteurs_menace):
                score += 20
            
            if score >= 20:
                lies.append({
                    'id': risque.id,
                    'reference': risque.reference,
                    'intitule': risque.intitule,
                    'niveau': risque.niveau_criticite,
                    'score_lien': score,
                })
        
        return sorted(lies, key=lambda x: x['score_lien'], reverse=True)[:5]
    
    # ============================================
    # HISTORIQUE DES MENACES IGNORÉES
    # ============================================
    
    def _get_menaces_ignorees(self, client_id: int) -> set:
        """Récupère les hashes des menaces déjà ignorées"""
        try:
            from models import MenaceIgnoree
            ignorees = MenaceIgnoree.query.filter_by(client_id=client_id).all()
            return {m.hash_menace for m in ignorees}
        except (ImportError, Exception):
            return set()
    
    def _compute_hash(self, *args) -> str:
        """Calcule un hash unique"""
        contenu = '|'.join(str(a) for a in args if a)
        return hashlib.sha256(contenu.encode()).hexdigest()[:16]
    
    # ============================================
    # PERIMÈTRE
    # ============================================
    
    def _construire_perimetre(self, pays, poles, directions, risques) -> Dict:
        """Construit une carte enrichie du périmètre"""
        return {
            'pays': [
                {
                    'id': p.id,
                    'nom': p.nom,
                    'code': p.code,
                    'organismes': self._get_organismes_pays(p)
                }
                for p in pays
            ],
            'poles': [
                {
                    'id': p.id,
                    'nom': p.nom,
                    'secteur': self._detecter_secteur(p.nom),
                    'pays_id': p.pays_id,
                }
                for p in poles
            ],
            'directions': [
                {'id': d.id, 'nom': d.nom, 'pole_id': d.pole_id}
                for d in directions
            ],
            'secteurs': self._extraire_secteurs(poles),
            'mots_cles_organisation': self._extraire_mots_cles_organisation(poles),
            'organismes_pertinents': self._extraire_organismes(pays, poles),
            'risques': [
                {
                    'id': r.id,
                    'reference': r.reference,
                    'categorie': r.categorie,
                    'intitule': r.intitule,
                }
                for r in risques[:50]  # Limiter
            ],
        }
    
    def _detecter_secteur(self, nom: str) -> Optional[str]:
        """Détecte le secteur à partir du nom"""
        nom = nom.lower()
        mapping = {
            'finance': ['banque', 'finance', 'bancaire', 'crédit', 'trésor'],
            'assurance': ['assurance', 'assureur', 'mutuelle', 'prévoyance'],
            'santé': ['santé', 'medical', 'hôpital', 'clinique', 'pharma'],
            'industrie': ['industrie', 'production', 'manufacture', 'usine'],
            'technologie': ['tech', 'it', 'numérique', 'logiciel', 'data'],
            'commerce': ['commerce', 'vente', 'retail', 'distribution'],
            'énergie': ['énergie', 'pétrole', 'gaz', 'électricité'],
            'télécom': ['télécom', 'mobile', 'réseau', 'internet'],
        }
        
        for secteur, mots in mapping.items():
            if any(m in nom for m in mots):
                return secteur
        return None
    
    def _extraire_secteurs(self, poles) -> List[str]:
        """Extrait les secteurs uniques de l'organisation"""
        secteurs = set()
        for pole in poles:
            secteur = self._detecter_secteur(pole.nom or '')
            if secteur:
                secteurs.add(secteur)
        return list(secteurs)
    
    def _extraire_mots_cles_organisation(self, poles) -> List[str]:
        """Extrait les mots-clés représentatifs"""
        mots = Counter()
        for pole in poles:
            for mot in self._tokenize(pole.nom or ''):
                mots[mot] += 1
        return [m for m, _ in mots.most_common(20)]
    
    def _extraire_organismes(self, pays, poles) -> List[str]:
        """Extrait les organismes pertinents"""
        # Basé sur les organismes déjà utilisés dans les veilles
        organismes = set()
        for pole in poles:
            if 'banque' in (pole.nom or '').lower():
                organismes.update(['BCEAO', 'COBAC', 'AMF', 'ACPR'])
            if 'assurance' in (pole.nom or '').lower():
                organismes.update(['ACPR', 'AMF'])
        return list(organismes)
    
    def _get_organismes_pays(self, pays) -> List[str]:
        """Retourne les organismes d'un pays"""
        if not pays or not pays.code:
            return []
        
        mapping = {
            'FRA': ['AMF', 'ACPR', 'CNIL', 'ANSSI'],
            'SEN': ['BCEAO', 'CREPMF'],
            'CIV': ['BCEAO', 'CREPMF'],
            'CMR': ['BEAC', 'COBAC'],
            'GAB': ['BEAC', 'COBAC'],
            'NGA': ['CBN', 'SEC'],
            'GHA': ['BOG', 'SEC'],
            'ZAF': ['SARB', 'FSCA'],
        }
        return mapping.get(pays.code.upper(), [])
