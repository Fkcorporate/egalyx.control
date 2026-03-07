# import_articles_csv.py
import csv
from app import app, db
from models import Article, Categorie, Auteur
from datetime import datetime

def importer_articles_csv(fichier_csv):
    """Importe des articles depuis un fichier CSV"""
    
    with app.app_context():
        categorie = Categorie.query.first()
        auteur = Auteur.query.first()
        
        if not categorie or not auteur:
            print("❌ Créez d'abord une catégorie et un auteur")
            return
        
        with open(fichier_csv, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            compteur = 0
            
            for row in reader:
                article = Article(
                    titre=row['titre'],
                    slug=generer_slug(row['titre']),
                    accroche=row.get('accroche', ''),
                    contenu=row['contenu'],
                    excerpt=row.get('excerpt', ''),
                    tags=row.get('tags', ''),
                    categorie_id=categorie.id,
                    auteur_id=auteur.id,
                    est_publie=True,
                    temps_lecture=int(row.get('temps_lecture', 5)),
                    meta_description=row.get('meta_description', ''),
                    date_publication=datetime.now(),
                    date_modification=datetime.now(),
                    date_creation=datetime.now()
                )
                
                db.session.add(article)
                compteur += 1
            
            db.session.commit()
            print(f"✅ {compteur} articles importés depuis {fichier_csv}")

# Format du CSV attendu :
# titre,contenu,accroche,excerpt,tags,temps_lecture,meta_description