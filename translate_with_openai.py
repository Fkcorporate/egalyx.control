# translate_with_openai.py
import csv
import openai
import os
import time
import json
from datetime import datetime

# Configuration OpenAI
openai.api_key = os.environ.get("OPENAI_API_KEY")
if not openai.api_key:
    print("❌ OPENAI_API_KEY non configurée")
    print("Configurez-la avec: export OPENAI_API_KEY='votre-clé'")
    exit(1)

def traduire_avec_gpt(texte_fr, retry_count=0):
    """Traduit un texte français en anglais avec GPT-3.5"""
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": """Tu es un traducteur professionnel français-anglais spécialisé dans:
                - Gestion des risques (Risk Management)
                - Audit et conformité (Audit & Compliance)
                - Contrôle interne (Internal Control)
                - Gouvernance d'entreprise (Corporate Governance)
                
                Règles de traduction:
                1. Sois technique et précis
                2. Garde les acronymes (KRI, PDF, CSV, etc.)
                3. Pour les noms propres/titres, traduis le sens
                4. Pour les phrases complètes, traduis naturellement
                5. Réponds UNIQUEMENT avec la traduction, rien d'autre"""},
                {"role": "user", "content": f"Traduis ce terme en anglais: '{texte_fr}'"}
            ],
            temperature=0.1,  # Basse température pour plus de cohérence
            max_tokens=100
        )
        
        traduction = response.choices[0].message.content.strip()
        
        # Nettoyer la réponse
        traduction = traduction.replace('"', '').replace("'", "").strip()
        
        # Vérifier que c'est une vraie traduction (pas identique au français)
        if traduction.lower() == texte_fr.lower():
            print(f"⚠️  Traduction identique à l'original: {texte_fr}")
            return texte_fr  # Garder l'original
        
        return traduction
        
    except openai.error.RateLimitError:
        if retry_count < 3:
            wait_time = 5 * (retry_count + 1)
            print(f"⏳ Rate limit, attente {wait_time} secondes...")
            time.sleep(wait_time)
            return traduire_avec_gpt(texte_fr, retry_count + 1)
        else:
            print(f"❌ Rate limit persistante pour: {texte_fr}")
            return texte_fr
            
    except Exception as e:
        print(f"❌ Erreur GPT pour '{texte_fr}': {e}")
        return texte_fr

def analyser_fichier():
    """Analyse le fichier CSV et identifie ce qui reste à traduire"""
    
    fichier_csv = 'translations/to_translate.csv'
    
    if not os.path.exists(fichier_csv):
        print(f"❌ Fichier non trouvé: {fichier_csv}")
        return None, None, None
    
    # Lire le fichier
    with open(fichier_csv, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        lignes = list(reader)
    
    # Analyser l'état
    total = len(lignes)
    traduits = 0
    non_traduits = 0
    partiellement_traduits = 0
    
    for ligne in lignes:
        texte_fr = ligne['french'].strip() if ligne['french'] else ''
        texte_en = ligne.get('english', '').strip() if ligne.get('english') else ''
        
        if not texte_fr:
            continue
            
        if texte_en and texte_en != texte_fr:
            traduits += 1
        elif texte_en == texte_fr or texte_en == '':
            non_traduits += 1
        else:
            partiellement_traduits += 1
    
    return lignes, total, non_traduits

def traduire_fichier_complet():
    """Traduit toutes les entrées manquantes"""
    
    lignes, total, non_traduits = analyser_fichier()
    
    if not lignes:
        return
    
    print("📊 ANALYSE DU FICHIER")
    print("=" * 50)
    print(f"Total des entrées: {total}")
    print(f"Déjà traduites: {total - non_traduits}")
    print(f"À traduire: {non_traduits}")
    print("=" * 50)
    
    if non_traduits == 0:
        print("✅ Toutes les traductions sont complètes!")
        return
    
    # Afficher un échantillon des termes à traduire
    print("\n🔍 ÉCHANTILLON des termes à traduire:")
    print("-" * 50)
    echantillon = []
    for ligne in lignes[:10]:
        texte_fr = ligne['french'].strip() if ligne['french'] else ''
        texte_en = ligne.get('english', '').strip() if ligne.get('english') else ''
        
        if texte_fr and (not texte_en or texte_en == texte_fr):
            echantillon.append(texte_fr)
    
    for i, terme in enumerate(echantillon[:5]):
        print(f"{i+1}. {terme}")
    
    # Demander confirmation
    print(f"\n💸 Estimation coût: ~${(non_traduits * 0.002):.3f} USD")
    reponse = input(f"\nTraduire {non_traduits} termes avec GPT-3.5? (oui/non): ").strip().lower()
    
    if reponse not in ['oui', 'o', 'yes', 'y']:
        print("❌ Annulé")
        return
    
    # Traduction
    print(f"\n🚀 Début de la traduction...")
    print("=" * 50)
    
    traduits = 0
    erreurs = 0
    fichier_csv = 'translations/to_translate.csv'
    
    # Sauvegarde de backup
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = f"translations/to_translate_backup_{timestamp}.csv"
    with open(backup_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['french', 'english'])
        writer.writeheader()
        writer.writerows(lignes)
    print(f"💾 Backup créé: {backup_file}")
    
    for i, ligne in enumerate(lignes):
        texte_fr = ligne['french'].strip() if ligne['french'] else ''
        texte_en = ligne.get('english', '').strip() if ligne.get('english') else ''
        
        # Vérifier si besoin de traduction
        if texte_fr and (not texte_en or texte_en == texte_fr):
            try:
                print(f"\n[{i+1}/{total}] Traduction: {texte_fr[:70]}...")
                
                # Traduire
                traduction = traduire_avec_gpt(texte_fr)
                
                if traduction and traduction != texte_fr:
                    ligne['english'] = traduction
                    traduits += 1
                    print(f"   ✅ → {traduction[:70]}...")
                else:
                    print(f"   ⚠️  Gardé l'original")
                    ligne['english'] = texte_fr
                
                # Pause pour éviter rate limiting
                time.sleep(0.3)
                
                # Sauvegarde progressive toutes les 20 traductions
                if traduits % 20 == 0:
                    with open(fichier_csv, 'w', encoding='utf-8', newline='') as f:
                        writer = csv.DictWriter(f, fieldnames=['french', 'english'])
                        writer.writeheader()
                        writer.writerows(lignes)
                    print(f"💾 Sauvegarde intermédiaire ({traduits}/{non_traduits})")
                    
            except Exception as e:
                print(f"❌ Erreur: {e}")
                ligne['english'] = texte_fr  # Garder l'original en cas d'erreur
                erreurs += 1
                continue
    
    # Sauvegarde finale
    with open(fichier_csv, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['french', 'english'])
        writer.writeheader()
        writer.writerows(lignes)
    
    # Rapport final
    print("\n" + "=" * 50)
    print("🎉 TRADUCTION TERMINÉE!")
    print("=" * 50)
    print(f"✅ Termes traduits: {traduits}")
    print(f"⚠️  Erreurs: {erreurs}")
    print(f"📊 Total final: {total} entrées")
    print(f"💾 Fichier: {fichier_csv}")
    print(f"💾 Backup: {backup_file}")
    
    # Vérifier le résultat
    print("\n📋 APERÇU FINAL (premières 10 lignes):")
    print("-" * 80)
    for i, ligne in enumerate(lignes[:10]):
        fr = ligne['french'][:40] if ligne['french'] else ''
        en = ligne['english'][:40] if ligne.get('english') else ''
        print(f"{fr:<40} → {en}")
    
    print("\n✅ Pour tester: ajoutez '?lang=en' à vos URLs")

def verifier_traductions():
    """Vérifie la qualité des traductions"""
    
    lignes, total, non_traduits = analyser_fichier()
    
    if not lignes:
        return
    
    print("🔍 VÉRIFICATION DES TRADUCTIONS")
    print("=" * 50)
    
    problemes = []
    
    for i, ligne in enumerate(lignes):
        texte_fr = ligne['french'].strip() if ligne['french'] else ''
        texte_en = ligne.get('english', '').strip() if ligne.get('english') else ''
        
        if texte_fr:
            # Vérifier différents problèmes
            if not texte_en:
                problemes.append(f"Ligne {i+1}: Pas de traduction - '{texte_fr}'")
            elif texte_en == texte_fr:
                problemes.append(f"Ligne {i+1}: Traduction identique - '{texte_fr}'")
            elif len(texte_en) > len(texte_fr) * 3:  # Trop long
                problemes.append(f"Ligne {i+1}: Traduction trop longue - '{texte_fr[:30]}...'")
    
    if problemes:
        print(f"⚠️  {len(problemes)} problèmes détectés:")
        for probleme in problemes[:10]:  # Afficher seulement les 10 premiers
            print(f"   {probleme}")
        
        if len(problemes) > 10:
            print(f"   ... et {len(problemes) - 10} autres")
    else:
        print("✅ Toutes les traductions semblent correctes!")
    
    return problemes

if __name__ == '__main__':
    print("🌐 TRADUCTEUR OpenAI pour Contrôle Interne")
    print("=" * 50)
    
    while True:
        print("\nOptions:")
        print("1. Analyser le fichier")
        print("2. Traduire automatiquement")
        print("3. Vérifier les traductions")
        print("4. Quitter")
        
        choix = input("\nChoix (1-4): ").strip()
        
        if choix == '1':
            lignes, total, non_traduits = analyser_fichier()
            if lignes:
                print(f"\n📊 Résultat: {total} entrées, {non_traduits} à traduire")
        
        elif choix == '2':
            traduire_fichier_complet()
        
        elif choix == '3':
            verifier_traductions()
        
        elif choix == '4':
            print("👋 Au revoir!")
            break
        
        else:
            print("❌ Choix invalide")