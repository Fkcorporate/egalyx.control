"""Pour chaque route de app.py : {paramètre d'URL: modèle chargé}, déduit du code de la route."""
import ast, re, json, collections
src = open('/home/claude/v4/app.py', encoding='utf-8').read()
lignes = src.split('\n'); arbre = ast.parse(src)
modeles = set(re.findall(r'^class (\w+)\(db\.Model\)', open('/home/claude/v4/models.py', encoding='utf-8').read(), re.M))
carte, sans = {}, collections.Counter()
for n in arbre.body:
    if not isinstance(n, ast.FunctionDef):
        continue
    routes = [d.args[0].value for d in n.decorator_list if isinstance(d, ast.Call) and getattr(d.func, 'attr', '') == 'route'
              and d.args and isinstance(d.args[0], ast.Constant)]
    if not routes:
        continue
    corps = '\n'.join(lignes[n.lineno - 1:n.end_lineno])
    params = sorted({p for r in routes for p in re.findall(r'<int:([a-z_]+)>', r)})
    m = {}
    for p in params:
        pats = [rf'(\w+)\.query\.get(?:_or_404)?\(\s*{p}\s*\)', rf'session\.get\(\s*(\w+)\s*,\s*{p}\s*\)',
                rf'get_client_object_or_404\(\s*(\w+)\s*,\s*{p}\s*\)', rf'(\w+)\.query\.filter_by\(\s*id\s*=\s*{p}\b']
        trouves = [x for pat in pats for x in re.findall(pat, corps) if x in modeles]
        if trouves:
            m[p] = collections.Counter(trouves).most_common(1)[0][0]
        else:
            sans[p] += 1
    if m:
        carte[n.name] = m
json.dump(carte, open('/home/claude/audit/carte_routes.json', 'w'), indent=0, ensure_ascii=False)
nb = sum(len(v) for v in carte.values())
print(len(carte), 'routes avec au moins un paramètre identifié,', nb, 'paramètres reliés à un modèle')
print('paramètres non reliés :', sans.most_common(25))
