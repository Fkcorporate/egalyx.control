"""
Ajoute à la base SQLite les colonnes de la v4 (double authentification, contrôles de processus).
N'exige pas de démarrer l'application. Ne supprime rien. Fait une copie de sécurité avant.

    python reparer_base.py                    # cherche la base (instance/*.db, *.db)
    python reparer_base.py chemin/vers/base.db
"""
import glob
import os
import shutil
import sqlite3
import sys
from datetime import datetime

COLONNES = {
    'user': [
        ('totp_secret_chiffre', 'VARCHAR(255)'),
        ('totp_actif', 'BOOLEAN DEFAULT 0'),
        ('totp_active_le', 'DATETIME'),
        ('totp_dernier_pas', 'INTEGER'),
        ('totp_codes_secours', 'JSON'),
    ],
    'clients': [
        ('modules_actifs', 'JSON'),
    ],
    'controle_processus': [
        ('processus_id', 'INTEGER REFERENCES processus(id)'),
        ('etape_id', 'INTEGER REFERENCES etape_processus(id)'),
    ],
    'campagnes_controle': [
        ('soumis_par_id', 'INTEGER REFERENCES user(id)'),
        ('date_soumission', 'DATETIME'),
        ('valide_par_id', 'INTEGER REFERENCES user(id)'),
        ('date_validation', 'DATETIME'),
        ('commentaire_validation', 'TEXT'),
        ('rejete_par_id', 'INTEGER REFERENCES user(id)'),
        ('date_rejet', 'DATETIME'),
        ('raison_rejet', 'TEXT'),
        ('rouvert_par_id', 'INTEGER REFERENCES user(id)'),
        ('date_rouverture', 'DATETIME'),
        ('raison_rouverture', 'TEXT'),
        ('historique_actions', 'JSON'),
    ],
}


def trouver_bases():
    ici = os.path.dirname(os.path.abspath(__file__))
    candidats = []
    for motif in ('instance/*.db', 'instance/*.sqlite', 'instance/*.sqlite3', '*.db', '*.sqlite', '*.sqlite3'):
        candidats += glob.glob(os.path.join(ici, motif))
    return [c for c in candidats if 'user' in tables(c)]


def tables(chemin):
    try:
        with sqlite3.connect(chemin) as cnx:
            return {r[0] for r in cnx.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    except sqlite3.Error:
        return set()


def reparer(chemin):
    copie = f"{chemin}.avant-v4-{datetime.now():%Y%m%d-%H%M%S}"
    shutil.copy2(chemin, copie)
    print(f"Copie de sécurité : {copie}")
    ajoutees = 0
    with sqlite3.connect(chemin) as cnx:
        existantes = tables(chemin)
        for table, colonnes in COLONNES.items():
            if table not in existantes:
                print(f"  (table {table} absente : elle sera créée au démarrage)")
                continue
            presentes = {r[1] for r in cnx.execute(f'PRAGMA table_info("{table}")')}
            for nom, type_sql in colonnes:
                if nom in presentes:
                    print(f"  déjà présente : {table}.{nom}")
                    continue
                cnx.execute(f'ALTER TABLE "{table}" ADD COLUMN "{nom}" {type_sql}')
                print(f"  ✅ ajoutée : {table}.{nom}")
                ajoutees += 1
    print(f"Terminé : {ajoutees} colonne(s) ajoutée(s) dans {chemin}")


if __name__ == '__main__':
    bases = sys.argv[1:] or trouver_bases()
    if not bases:
        print("Aucune base SQLite contenant la table « user » trouvée. Indiquez son chemin : "
              "python reparer_base.py chemin/vers/base.db")
        sys.exit(1)
    for b in bases:
        print(f"Base : {b}")
        reparer(b)
    print("Redémarrez l'application.")
