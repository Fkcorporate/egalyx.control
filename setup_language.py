# setup_language.py
import os
import csv
import json

def setup_translation_files():
    """Initialise les fichiers de traduction"""
    
    # Créer le dossier translations s'il n'existe pas
    if not os.path.exists('translations'):
        os.makedirs('translations', exist_ok=True)
    
    # Créer un fichier CSV de base si vide
    csv_file = 'translations/to_translate.csv'
    if not os.path.exists(csv_file) or os.path.getsize(csv_file) == 0:
        with open(csv_file, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['french', 'english'])
            
            # Ajouter les traductions de base
            base_translations = [
                ['Tableau de bord', 'Dashboard'],
                ['Gestion des risques', 'Risk Management'],
                ['Audit', 'Audit'],
                ['Paramètres', 'Settings'],
                ['Utilisateurs', 'Users'],
                ['Déconnexion', 'Logout'],
                ['Cartographie', 'Mapping'],
                ['Indicateurs KRI', 'KRI Indicators'],
                ['Veille règlementaire', 'Regulatory Watch'],
                ['Logigrammes', 'Flowcharts'],
                ['Audit Interne', 'Internal Audit'],
                ['Questionnaires', 'Questionnaires'],
                ['Administration', 'Administration'],
                ['Actions rapides', 'Quick Actions'],
                ['Vue Client', 'Client View'],
                ['Profil', 'Profile'],
                ['Super Admin', 'Super Admin'],
                ['Gestion Clients', 'Client Management'],
                ['Formules d\'abonnement', 'Subscription Plans'],
                ['Tous les Utilisateurs', 'All Users'],
                ['Enregistrer', 'Save'],
                ['Annuler', 'Cancel'],
                ['Modifier', 'Edit'],
                ['Supprimer', 'Delete'],
                ['Créer', 'Create'],
                ['Rechercher', 'Search']
            ]
            
            for french, english in base_translations:
                writer.writerow([french, english])
        
        print(f"✅ Fichier CSV créé avec {len(base_translations)} traductions")
    
    # Créer les fichiers JSON
    for lang in ['fr', 'en']:
        json_file = f'translations/{lang}.json'
        if not os.path.exists(json_file):
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump({}, f, ensure_ascii=False, indent=2)
            print(f"✅ Fichier {json_file} créé")
    
    return True

def load_translations():
    """Charge les traductions depuis le CSV"""
    translations = {'fr': {}, 'en': {}}
    
    try:
        csv_file = 'translations/to_translate.csv'
        if os.path.exists(csv_file):
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    french = row.get('french', '').strip()
                    english = row.get('english', '').strip()
                    
                    if french and english:
                        translations['fr'][french] = french  # Français → Français
                        translations['en'][french] = english  # Français → Anglais
            
            print(f"✅ {len(translations['fr'])} traductions chargées")
        else:
            print(f"⚠️ Fichier CSV non trouvé: {csv_file}")
            
    except Exception as e:
        print(f"❌ Erreur chargement traductions: {e}")
    
    return translations

# Exécuter le setup
if __name__ == '__main__':
    setup_translation_files()
    translations = load_translations()