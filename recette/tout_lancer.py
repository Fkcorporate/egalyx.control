"""Lance toute la recette et affiche un résumé.

    python recette/tout_lancer.py

Utilise une base SQLite de test (recette/recette.db), jamais votre vraie base, et aucune clé du fichier .env
n'est nécessaire. Code de sortie 0 si tout est bon, 1 sinon."""
import os, subprocess, sys, json
ICI = os.path.dirname(os.path.abspath(__file__))
ETAPES = [
    ('Circuit campagne ↔ contrôle interne N2 (22 vérifications)', 'circuit_campagne.py', []),
    ('Tableau de bord : modules du client et permissions', 'tableau_de_bord.py', []),
    ('Tableau de bord stratégique : signaux de vigilance', 'strategique.py', []),
    ('Recommandations, KRI, audit (53 vérifications)', 'ameliorations.py', []),
    ('Plans d\'action et recommandations : modules et permissions', 'coherence_modules.py', []),
    ('Processus et logigrammes', 'logigramme.py', []),
    ('Logigrammes : versions, validation, couloirs, vérification', 'logigramme_gouvernance.py', []),
    ('Masquage partout + permissions cohérentes avec les modules', 'masquage_permissions.py', []),
    ('Cartographie : évaluation en 3 phases par campagne', 'cartographie_campagne.py', []),
    ('Modules désactivés puis réactivés : menus et droits', 'modules_reactives.py', []),
    ('PCA : droits, validation, exercices, activations, documents', 'pca.py', []),
    ('Qualité : droits, validation, non-conformités, revues', 'qualite.py', []),
    ('Super admin : supprimer / réinitialiser / exporter un client', 'gestion_clients.py', []),
    ('Recommandations : suppression de l\'historique', 'historique_recommandations.py', []),
    ('KRI : modules du client contre formule ; scripts des pages intacts', 'kri_formule.py', []),
    ('Sécurité des décisions par rôle', 'securite.py', []),
    ('Pages sans identifiant, 6 rôles', 'balayage.py', ['superadmin', 'admin_a', 'gestionnaire', 'validateur', 'operateur', 'lecteur']),
    ('Pages de détail + étanchéité entre organisations', 'balayage_detail.py', []),
    ('Colonnes fantômes', 'colonnes_fantomes.py', []),
]
BRUIT = ('🟢', '🔐', '📋', '✅', '⚠', '❌', '   ', '🔧', '🔒')
ok_global = True
for titre, script, args in ETAPES:
    print(f'\n=== {titre}', flush=True)
    p = subprocess.run([sys.executable, os.path.join(ICI, script)] + args, capture_output=True, text=True)
    lignes = [l for l in p.stdout.splitlines() if l.strip() and not l.lstrip().startswith(BRUIT)]
    print('\n'.join(lignes[-18:]))
    if p.returncode != 0:
        ok_global = False
        print(p.stderr[-1500:])


def charge(n):
    try:
        return json.load(open(os.path.join(ICI, n), encoding='utf-8'))
    except Exception:
        return None


sec = charge('securite.json') or []
trous = [(l['action'], r) for l in sec for r, v in l.items() if isinstance(v, dict) and v['fait'] and not v['attendu']]
erreurs = []
for n in ('balayage.json', 'balayage_detail.json'):
    for ep, v in (charge(n) or {}).items():
        for r, x in v.items():
            if r != 'rule' and x[0] >= 500 and x[1] and 'weasyprint' not in x[1]:
                erreurs.append((v['rule'], x[1][:120]))
                break
fuites = [v['rule'] for v in (charge('balayage_detail.json') or {}).values() if v.get('admin_b', [0, '', ''])[2]]
print('\n=== Résumé')
print(f'Actions faites par un rôle qui ne devrait pas : {len(trous)}', trous[:10])
print(f'Pages en erreur (cause identifiée) : {len(erreurs)}')
for e in erreurs:
    print('   ', e[0], '→', e[1])
print(f'Fuites entre organisations : {len(fuites)}', fuites)
sys.exit(0 if ok_global and not fuites else 1)
