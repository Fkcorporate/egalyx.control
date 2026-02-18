#!/usr/bin/env python3
# save as: test_render_complet.py

import os
import sys
import importlib
import traceback

print("="*60)
print("🔍 TEST COMPLET DE L'APPLICATION SUR RENDER")
print("="*60)
print(f"Heure: {__import__('datetime').datetime.now()}")
print(f"Python: {sys.version}")
print(f"Répertoire courant: {os.getcwd()}")
print("-"*60)

# 1. TEST DES IMPORTS DE BASE
print("\n📦 1. TEST DES IMPORTS DE BASE")
try:
    import flask
    print(f"   ✅ Flask: {flask.__version__}")
except Exception as e:
    print(f"   ❌ Flask: {e}")

try:
    import flask_sqlalchemy
    print(f"   ✅ Flask-SQLAlchemy")
except Exception as e:
    print(f"   ❌ Flask-SQLAlchemy: {e}")

try:
    import flask_wtf
    print(f"   ✅ Flask-WTF")
except Exception as e:
    print(f"   ❌ Flask-WTF: {e}")

try:
    import psycopg2
    print(f"   ✅ psycopg2")
except Exception as e:
    print(f"   ❌ psycopg2: {e}")

# 2. TEST D'IMPORT DE L'APPLICATION
print("\n📄 2. TEST D'IMPORT DE L'APPLICATION")
try:
    # Essayer d'importer l'app
    import app
    print(f"   ✅ Module 'app' importé")
    
    # Vérifier les attributs importants
    if hasattr(app, 'app'):
        print(f"   ✅ app.app existe")
    else:
        print(f"   ❌ app.app n'existe pas")
    
    # Vérifier db
    if hasattr(app, 'db'):
        print(f"   ✅ app.db existe")
        print(f"   Type de db: {type(app.db)}")
        if hasattr(app.db, 'metadata'):
            print(f"   ✅ db.metadata existe")
        else:
            print(f"   ❌ db.metadata n'existe PAS")
    else:
        print(f"   ❌ app.db n'existe pas")
    
    # Vérifier csrf
    if hasattr(app, 'csrf'):
        print(f"   ✅ app.csrf existe")
        print(f"   Type de csrf: {type(app.csrf)}")
        if hasattr(app.csrf, 'exempt'):
            print(f"   ✅ csrf.exempt existe")
        else:
            print(f"   ❌ csrf.exempt n'existe PAS")
    else:
        print(f"   ❌ app.csrf n'existe pas")
    
except Exception as e:
    print(f"   ❌ Erreur import app: {e}")
    traceback.print_exc()

# 3. RECHERCHE DES OBJETS FAKE
print("\n🔎 3. RECHERCHE DES OBJETS 'FAKE'")
try:
    with open('app.py', 'r') as f:
        content = f.read()
        
    fake_lines = []
    for i, line in enumerate(content.split('\n'), 1):
        if 'Fake' in line and '#' not in line[:line.find('Fake')]:
            fake_lines.append(f"   Ligne {i}: {line.strip()}")
    
    if fake_lines:
        print("   ⚠️  OBJETS FAKE TROUVÉS:")
        for line in fake_lines:
            print(line)
    else:
        print("   ✅ Aucun objet Fake trouvé")
except Exception as e:
    print(f"   ❌ Erreur lecture app.py: {e}")

# 4. TEST DE CONNEXION À LA BASE DE DONNÉES
print("\n🗄️ 4. TEST DE CONNEXION À LA BASE DE DONNÉES")
try:
    # Essayer de se connecter via les variables d'environnement
    db_url = os.environ.get('DATABASE_URL') or os.environ.get('DB_URL')
    if db_url:
        print(f"   ✅ URL de base trouvée")
        # Cacher le mot de passe pour l'affichage
        safe_url = db_url.replace('://', '://***:***@') if '@' in db_url else db_url
        print(f"   URL: {safe_url[:50]}...")
        
        # Tenter une connexion directe
        import psycopg2
        try:
            conn = psycopg2.connect(db_url)
            print(f"   ✅ Connexion réussie")
            cur = conn.cursor()
            cur.execute("SELECT version();")
            version = cur.fetchone()
            print(f"   Version PostgreSQL: {version[0][:50]}...")
            cur.close()
            conn.close()
        except Exception as e:
            print(f"   ❌ Erreur connexion: {e}")
    else:
        print(f"   ❌ Aucune URL de base de données trouvée")
except Exception as e:
    print(f"   ❌ Erreur: {e}")

# 5. VÉRIFICATION DES VARIABLES D'ENVIRONNEMENT
print("\n🌍 5. VARIABLES D'ENVIRONNEMENT")
env_vars = ['FLASK_ENV', 'FLASK_DEBUG', 'DATABASE_URL', 'SECRET_KEY']
for var in env_vars:
    value = os.environ.get(var)
    if value:
        if var == 'DATABASE_URL':
            value = '***' + value[-10:] if len(value) > 10 else '***'
        elif var == 'SECRET_KEY':
            value = '***'
        print(f"   ✅ {var}: {value}")
    else:
        print(f"   ❌ {var}: non défini")

# 6. TEST DES MODULES PROBLÉMATIQUES
print("\n🔧 6. TEST DES MODULES PROBLÉMATIQUES")

# WeasyPrint
try:
    import weasyprint
    print(f"   ✅ WeasyPrint: {weasyprint.__version__}")
except Exception as e:
    print(f"   ❌ WeasyPrint: {e}")

# email_validator
try:
    import email_validator
    print(f"   ✅ email_validator")
except Exception as e:
    print(f"   ❌ email_validator: {e}")

# 7. CRÉATION D'UNE PETITE APPLICATION DE TEST
print("\n🚀 7. TEST DE CRÉATION D'UNE APPLICATION MINIMALE")
try:
    from flask import Flask
    from flask_sqlalchemy import SQLAlchemy
    from flask_wtf.csrf import CSRFProtect
    
    test_app = Flask(__name__)
    test_app.config['SECRET_KEY'] = 'test'
    test_db = SQLAlchemy(test_app)
    test_csrf = CSRFProtect(test_app)
    
    print(f"   ✅ Application de test créée")
    print(f"   ✅ test_db type: {type(test_db)}")
    print(f"   ✅ test_db.metadata: {hasattr(test_db, 'metadata')}")
    print(f"   ✅ test_csrf.exempt: {hasattr(test_csrf, 'exempt')}")
    
except Exception as e:
    print(f"   ❌ Erreur création app test: {e}")

# 8. RECHERCHE DE LA FONCTION PROBLEMATIQUE
print("\n🔍 8. RECHERCHE DE LA FONCTION refresh_sqlalchemy_metadata")
try:
    import app
    if hasattr(app, 'refresh_sqlalchemy_metadata'):
        print(f"   ✅ Fonction trouvée")
        # Vérifier son contenu
        import inspect
        lines = inspect.getsourcelines(app.refresh_sqlalchemy_metadata)
        print(f"   Code de la fonction:")
        for i, line in enumerate(lines[0][:10]):  # 10 premières lignes max
            print(f"      {line.rstrip()}")
    else:
        print(f"   ❌ Fonction non trouvée")
except Exception as e:
    print(f"   ❌ Erreur: {e}")

# 9. VÉRIFICATION DES FICHIERS CRITIQUES
print("\n📁 9. FICHIERS CRITIQUES")
fichiers = ['app.py', 'requirements.txt', 'render-build.sh', 'wsgi.py']
for fichier in fichiers:
    if os.path.exists(fichier):
        size = os.path.getsize(fichier)
        print(f"   ✅ {fichier} ({size} octets)")
        if fichier == 'requirements.txt':
            with open(fichier, 'r') as f:
                content = f.read()
                lines = content.strip().split('\n')
                print(f"      {len(lines)} dépendances")
    else:
        print(f"   ❌ {fichier} manquant")

# 10. RÉSUMÉ
print("\n" + "="*60)
print("📊 RÉSUMÉ DES PROBLÈMES IDENTIFIÉS")
print("="*60)

# Analyser les erreurs potentielles
problemes = []

if 'FakeDB' in str(locals().get('fake_lines', [])):
    problemes.append("❌ FakeDB détecté - Remplacer par vraie instance SQLAlchemy")
if 'FakeCSRF' in str(locals().get('fake_lines', [])):
    problemes.append("❌ FakeCSRF détecté - Remplacer par vraie instance CSRFProtect")
if not hasattr(app, 'db') or not hasattr(app.db, 'metadata'):
    problemes.append("❌ Problème avec db.metadata")
if 'email_validator' not in str(locals()):
    problemes.append("❌ email_validator non installé")
if 'weasyprint' not in str(locals()):
    problemes.append("❌ weasyprint non installé")

if problemes:
    for p in problemes:
        print(p)
else:
    print("✅ Aucun problème majeur détecté")

print("\n✅ Test terminé")