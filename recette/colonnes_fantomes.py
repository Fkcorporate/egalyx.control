"""Colonnes « fantômes » : valeurs que le code écrit sur un objet de la base alors que la colonne n'existe pas.
L'écran semble fonctionner, mais rien n'est enregistré. Recherche statique, confirmée par le modèle réel."""
import ast, os, re, json, sys
import socle
from socle import Muet
with Muet():
    A = socle.charger(False)
import models as M
from models import db
# 1. Noms connus de chaque modèle : colonnes, relations, propriétés, méthodes
modeles = {c.__name__: c for c in db.Model.__subclasses__()}
def tous(c, vus=None):
    for s in c.__subclasses__():
        modeles[s.__name__] = s; tous(s)
for c in list(modeles.values()): tous(c)
connus = {}
for nom, c in modeles.items():
    try:
        mp = c.__mapper__
    except Exception:
        continue
    n = set(mp.all_orm_descriptors.keys()) | set(dir(c))
    connus[nom] = n
# 2. Variables dont on peut deviner le modèle : x = Modele(...), x = Modele.query..., x = db.session.get(Modele, ..), get_or_404(Modele..)
PAT = [re.compile(r'^\s*(\w+)\s*=\s*(\w+)\('), re.compile(r'^\s*(\w+)\s*=\s*(\w+)\.query\b'),
       re.compile(r'^\s*(\w+)\s*=\s*db\.session\.get\((\w+)'), re.compile(r'^\s*(\w+)\s*=\s*get_client_object_or_404\((\w+)'),
       re.compile(r'^\s*for (\w+) in (\w+)\.query\b')]
fichiers = ['app.py', 'models.py'] + [os.path.join('egalyx', f) for f in os.listdir('egalyx') if f.endswith('.py')]
trouves = {}
for f in fichiers:
    lignes = open(f, encoding='utf-8').read().split('\n')
    typ = {}
    for i, l in enumerate(lignes, 1):
        if re.match(r'^(def|@app|class) ', l):
            typ = {}
        for p in PAT:
            m = p.match(l)
            if m and m.group(2) in connus:
                typ[m.group(1)] = m.group(2)
        m = re.match(r'^\s*(\w+)\.(\w+)\s*=[^=]', l)
        if m and m.group(1) in typ:
            var, attr = m.groups(); mod = typ[var]
            if attr not in connus[mod] and not attr.startswith('_'):
                trouves.setdefault((mod, attr), []).append(f'{f}:{i}')
print(len(trouves), 'écritures vers une colonne inexistante')
for (mod, attr), ou in sorted(trouves.items(), key=lambda x: -len(x[1])):
    print(f'  {mod}.{attr:32} {len(ou):3} fois  ex. {ou[0]}')
json.dump({f'{k[0]}.{k[1]}': v for k, v in trouves.items()}, open(socle.ICI + '/colonnes_fantomes.json', 'w'), indent=1)
