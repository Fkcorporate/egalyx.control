# generate_articles.py
from app import app, db
from models import Article, Categorie, Auteur
from datetime import datetime
import random
import requests

# Liste de sujets d'articles
SUJETS = [
    "L'impact de l'IA sur l'audit interne en 2024",
    "Comment réduire les risques de non-conformité",
    "Les 5 tendances de la gestion des risques",
    "Guide complet de la cartographie des risques",
    "OHADA : les nouvelles obligations comptables",
    "RGPD : audit de conformité en 5 étapes",
    "KRI vs KPI : quelles différences ?",
    "L'importance du contrôle interne en entreprise",
    "Audit interne : méthodologie et bonnes pratiques",
    "Les défis de la conformité réglementaire"
]

# Contenus prédéfinis (vous pouvez les enrichir)
CONTENUS = [
    """
    <h2>Introduction</h2>
    <p>L'intelligence artificielle transforme profondément les pratiques d'audit interne. Cette révolution technologique offre des opportunités sans précédent pour les professionnels du contrôle et de la gestion des risques.</p>
    
    <h2>1. L'IA au service de l'audit</h2>
    <p>Les algorithmes de machine learning permettent aujourd'hui d'analyser des volumes massifs de données en un temps record. Cette capacité d'analyse ouvre la voie à une détection plus précoce des anomalies et des risques.</p>
    
    <h2>2. Applications concrètes</h2>
    <ul>
        <li>Détection automatique des fraudes</li>
        <li>Analyse prédictive des risques</li>
        <li>Automatisation des contrôles récurrents</li>
        <li>Génération de recommandations intelligentes</li>
    </ul>
    
    <h2>Conclusion</h2>
    <p>L'adoption de l'IA dans les fonctions d'audit n'est plus une option mais une nécessité pour rester compétitif.</p>
    """,
    # Ajoutez d'autres contenus...
]

def generer_slug(titre):
    """Génère un slug à partir du titre"""
    import re
    slug = titre.lower()
    slug = re.sub(r'[àáâãäå]', 'a', slug)
    slug = re.sub(r'[èéêë]', 'e', slug)
    slug = re.sub(r'[ìíîï]', 'i', slug)
    slug = re.sub(r'[òóôõö]', 'o', slug)
    slug = re.sub(r'[ùúûü]', 'u', slug)
    slug = re.sub(r'[^a-z0-9]+', '-', slug)
    return slug.strip('-')

def generer_articles(nombre=5):
    """Génère automatiquement des articles"""
    with app.app_context():
        # Récupérer une catégorie et un auteur existants
        categorie = Categorie.query.first()
        auteur = Auteur.query.first()
        
        if not categorie or not auteur:
            print("❌ Créez d'abord une catégorie et un auteur dans l'admin")
            return
        
        for i in range(nombre):
            titre = random.choice(SUJETS) + f" - Partie {i+1}"
            slug = generer_slug(titre)
            contenu = random.choice(CONTENUS)
            
            article = Article(
                titre=titre,
                slug=slug,
                accroche=f"Découvrez comment {titre.lower()} peut transformer votre organisation.",
                contenu=contenu,
                excerpt=f"Article sur {titre.lower()} avec des conseils pratiques.",
                tags="audit, risques, conformité, IA",
                categorie_id=categorie.id,
                auteur_id=auteur.id,
                est_publie=True,
                temps_lecture=random.randint(3, 8),
                meta_description=f"Article complet sur {titre.lower()} - Conseils et bonnes pratiques",
                date_publication=datetime.now(),
                date_modification=datetime.now(),
                date_creation=datetime.now()
            )
            
            db.session.add(article)
            print(f"✅ Article généré : {titre}")
        
        db.session.commit()
        print(f"\n🎉 {nombre} articles générés avec succès !")

if __name__ == "__main__":
    generer_articles(10)