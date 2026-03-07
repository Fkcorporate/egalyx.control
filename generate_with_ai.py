# generate_with_ai.py
import openai
from app import app, db
from models import Article, Categorie, Auteur
from datetime import datetime

# Configurez votre clé API OpenAI
openai.api_key = 'votre-clé-api-openai'

def generer_article_avec_ia(sujet):
    """Génère un article complet avec ChatGPT"""
    
    prompt = f"""
    Rédige un article de blog professionnel sur le sujet suivant : "{sujet}"
    
    L'article doit contenir :
    - Un titre accrocheur
    - Une introduction
    - 3-4 sections avec sous-titres
    - Une conclusion
    - Environ 800-1000 mots
    - Un style professionnel adapté aux experts en audit et gestion des risques
    - Format HTML avec balises h2, p, ul, li
    
    Réponds uniquement avec le contenu HTML.
    """
    
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Tu es un expert en audit interne et gestion des risques."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=2000
        )
        
        return response.choices[0].message.content
    except Exception as e:
        print(f"❌ Erreur OpenAI: {e}")
        return None

def generer_article_ia(sujet, categorie_id, auteur_id):
    """Génère et sauvegarde un article"""
    
    contenu = generer_article_avec_ia(sujet)
    if not contenu:
        return None
    
    article = Article(
        titre=sujet,
        slug=generer_slug(sujet),
        accroche=f"Article complet sur {sujet.lower()} rédigé par intelligence artificielle.",
        contenu=contenu,
        excerpt=f"Guide complet sur {sujet.lower()} généré par IA.",
        tags="IA,audit,risques",
        categorie_id=categorie_id,
        auteur_id=auteur_id,
        est_publie=True,
        temps_lecture=8,
        meta_description=f"Article généré par IA sur {sujet.lower()} - Découvrez notre analyse",
        date_publication=datetime.now(),
        date_modification=datetime.now(),
        date_creation=datetime.now()
    )
    
    db.session.add(article)
    db.session.commit()
    return article

# Utilisation
with app.app_context():
    sujet = "L'impact de l'intelligence artificielle sur l'audit interne en 2024"
    categorie = Categorie.query.first()
    auteur = Auteur.query.first()
    
    if categorie and auteur:
        article = generer_article_ia(sujet, categorie.id, auteur.id)
        print(f"✅ Article généré: /blog/{article.slug}")