"""Recette : le code se lit avec la version de Python de Render (render.yaml : PYTHON_VERSION).

Python 3.12 accepte des écritures que 3.11 refuse (guillemets réutilisés ou « \\' » dans les f-strings) :
un fichier qui passe ici en 3.13 peut faire tomber le déploiement. Nécessite pythonX.Y installé, sinon ignorée.
"""
import glob
import os
import re
import shutil
import subprocess
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
yaml = open(os.path.join(RACINE, 'render.yaml'), encoding='utf-8').read() if os.path.exists(os.path.join(RACINE, 'render.yaml')) else ''
m = re.search(r'PYTHON_VERSION\s*\n\s*value:\s*([0-9]+\.[0-9]+)', yaml)
version = m.group(1) if m else '3.11'
exe = shutil.which('python' + version)
if not exe:
    print(f'python{version} absent : recette ignorée')
    print('\n0/0 vérifications réussies'); sys.exit(0)
fichiers = [f for f in glob.glob(os.path.join(RACINE, '**', '*.py'), recursive=True)
            if not any(p in f for p in (os.sep + 'archives' + os.sep, 'site-packages', os.sep + '#' + os.sep, os.sep + 'sauvegarde_maj_'))]
code = 'import ast,sys\nko=[]\nfor f in sys.argv[1:]:\n    try: ast.parse(open(f,encoding="utf-8").read(), f)\n    except SyntaxError as e: ko.append(f"{f}:{e.lineno} {e.msg}")\nprint("\\n".join(ko))'
sortie = subprocess.run([exe, '-c', code] + fichiers, capture_output=True, text=True).stdout.strip()
ok = not sortie
print('OK   ' if ok else 'ÉCHEC', f'{len(fichiers)} fichiers Python lisibles par Python {version} (version de Render)', sortie[:800])
print(f'\n{int(ok)}/1 vérifications réussies')
