# smart_translate.py
import csv
import os

def translate_with_intelligence():
    """Traduction intelligente des textes restants"""
    
    print("🤖 TRADUCTION INTELLIGENTE")
    print("="*60)
    
    # Charger les traductions existantes
    existing_translations = {}
    csv_file = 'translations/to_translate.csv'
    
    if os.path.exists(csv_file):
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            try:
                next(reader)  # Skip header
                for row in reader:
                    if len(row) >= 2:
                        existing_translations[row[0]] = row[1]
            except:
                pass
    
    print(f"📦 Traductions existantes: {len(existing_translations)}")
    
    # Traductions automatiques pour les termes courants
    auto_translations = {
        # Basé sur votre liste précédente
        "Description": "Description",
        "Critique": "Critical",
        "Faible": "Low",
        "Élevé": "High",
        "Responsable": "Responsible",
        "Non évalué": "Not evaluated",
        "Catégorie": "Category",
        "Référence": "Reference",
        "Non assigné": "Not assigned",
        "Non définie": "Not defined",
        "Terminé": "Completed",
        "Direction": "Department",
        "Administration": "Administration",
        "Rôle": "Role",
        "Identique": "Identical",
        "Créé le": "Created on",
        "Département": "Department",
        "Intitulé": "Title",
        "Probabilité": "Probability",
        "Conformité": "Compliance",
        
        # Expressions composées
        "Date de création": "Creation date",
        "Date de modification": "Modification date",
        "Statut actuel": "Current status",
        "Actions possibles": "Possible actions",
        "Voir détails": "View details",
        "Télécharger le fichier": "Download file",
        "Aucun résultat": "No results",
        "Rechercher...": "Search...",
        "Filtrer par": "Filter by",
        "Trier par": "Sort by",
        "Exporter en CSV": "Export to CSV",
        "Exporter en PDF": "Export to PDF",
        "Importer des données": "Import data",
        "Sélectionner tout": "Select all",
        "Désélectionner tout": "Deselect all",
        "Confirmer la suppression": "Confirm deletion",
        "Êtes-vous sûr ?": "Are you sure?",
        "Cette action est irréversible": "This action is irreversible",
        
        # Statuts
        "En cours": "In progress",
        "En attente": "Pending",
        "Validé": "Validated",
        "Rejeté": "Rejected",
        "Archivé": "Archived",
        "Actif": "Active",
        "Inactif": "Inactive",
        
        # Gravité
        "Mineur": "Minor",
        "Modéré": "Moderate",
        "Majeur": "Major",
        
        # Types
        "Opérationnel": "Operational",
        "Financier": "Financial",
        "Réglementaire": "Regulatory",
        "Stratégique": "Strategic",
    }
    
    # Appliquer aux templates directement
    templates_dir = 'templates'
    updated_files = 0
    updated_texts = 0
    
    for root, dirs, files in os.walk(templates_dir):
        if 'backups' in root:
            continue
            
        for file in files:
            if file.endswith('.html'):
                file_path = os.path.join(root, file)
                
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                original_content = content
                
                # Appliquer les traductions automatiques
                for french, english in auto_translations.items():
                    if french in content and french not in existing_translations:
                        # Remplacer intelligemment (uniquement le texte, pas dans les tags)
                        pattern = r'>([^<]*?)' + re.escape(french) + r'([^<]*?)<'
                        
                        def replace_match(match):
                            before = match.group(1)
                            after = match.group(2)
                            return f'>{before}{english}{after}<'
                        
                        content = re.sub(pattern, replace_match, content)
                        updated_texts += 1
                
                if content != original_content:
                    # Sauvegarder
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    
                    updated_files += 1
    
    print(f"\n📊 RÉSULTATS:")
    print(f"Fichiers mis à jour: {updated_files}")
    print(f"Textes traduits: {updated_texts}")
    
    # Ajouter au CSV
    added_to_csv = 0
    with open(csv_file, 'a', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        
        for french, english in auto_translations.items():
            if french not in existing_translations:
                writer.writerow([french, english])
                added_to_csv += 1
    
    print(f"Traductions ajoutées au CSV: {added_to_csv}")
    
    return updated_files

def test_language_switch():
    """Teste le fonctionnement du changement de langue"""
    
    print("\n🧪 TEST DU CHANGEMENT DE LANGUE")
    print("-"*60)
    
    test_script = '''
// Test du système de langue
console.log('🔍 TEST LANGUE DÉMARRÉ');

// Vérifier le localStorage
const savedLang = localStorage.getItem('app_lang');
console.log('LocalStorage lang:', savedLang);

// Vérifier les cookies
console.log('Cookies:', document.cookie);

// Vérifier les boutons
const btnFr = document.getElementById('btnFr');
const btnEn = document.getElementById('btnEn');
console.log('Bouton FR présent:', !!btnFr);
console.log('Bouton EN présent:', !!btnEn);

// Simuler un clic
if (btnFr && btnEn) {
    console.log('Boutons OK - système prêt');
    
    // Ajouter des listeners pour debug
    btnFr.addEventListener('click', function() {
        console.log('🇫🇷 FRANÇAIS cliqué');
    });
    
    btnEn.addEventListener('click', function() {
        console.log('🇬🇧 ENGLISH cliqué');
    });
} else {
    console.error('❌ Boutons non trouvés');
}

// Vérifier la langue actuelle
const htmlLang = document.documentElement.lang;
console.log('HTML lang attribute:', htmlLang);
'''
    
    print("Copiez ce code dans la console du navigateur (F12):")
    print(test_script)
    
    print("\n📋 CHECKLIST:")
    print("1. Ouvrez http://localhost:5000")
    print("2. Ouvrez la console (F12)")
    print("3. Collez le code ci-dessus")
    print("4. Cliquez sur FRANÇAIS et ENGLISH")
    print("5. Vérifiez les messages dans la console")

def main():
    """Fonction principale"""
    
    print("🚀 SOLUTION COMPLÈTE POUR LES TRADUCTIONS")
    print("="*60)
    
    # 1. Traduction intelligente
    translate_with_intelligence()
    
    # 2. Instructions pour tester
    test_language_switch()
    
    # 3. Prochaines étapes
    print(f"\n{'='*60}")
    print("🎯 PROCHAINES ÉTAPES")
    print("="*60)
    
    print("1. Redémarrez Flask:")
    print("   flask run")
    print("\n2. Testez le changement de langue:")
    print("   http://localhost:5000")
    print("   Cliquez sur FRANÇAIS et ENGLISH")
    print("\n3. Si ça ne marche pas:")
    print("   - Ouvrez la console (F12)")
    print("   - Vérifiez les erreurs")
    print("   - Exécutez le code de test")
    print("\n4. Pour les derniers textes:")
    print("   python clean_false_positives.py")
    print("   Traduisez seulement translations/real_missing.csv")

if __name__ == '__main__':
    import re
    main()