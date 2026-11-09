import ast, re, collections, sys
sys.path.insert(0, '/home/claude/v4'); sys.path.insert(0, '/home/claude/v4/tests/stubs')
from egalyx.modules_client import module_de_la_requete
src = open('/home/claude/v4/app.py', encoding='utf-8').read(); L = src.split('\n'); arbre = ast.parse(src)
modeles = set(re.findall(r'^class (\w+)\(db\.Model\)', open('/home/claude/v4/models.py', encoding='utf-8').read(), re.M))
MODS = {
 'Campagnes de contrôle': r'^/controle/|^/operateur/campagne|^/operateur/fichier-campagne|^/campagne/<int:campagne_id>/(creer-nc|synchroniser|lier|exporter-non)',
 'Contrôle N2 (C2N)': r'/c2n|controle-n2',
 'Incidents': r'incident',
 'Support (tickets)': r'ticket|/support',
 'PCA': r'pca|continuite',
 'Dispositifs de maîtrise': r'dispositif',
 "Plans d'action risques": r'plan-action-risque|plans-action-risque|risque/<int:[a-z_]+>/plan|sous-action-risque',
 "Plans d'action audit": r'audit/<int:audit_id>/plan|plan-action/<int|plans-action$|/plan-action/|sous-action/',
}
chemins = collections.defaultdict(list)
st = collections.defaultdict(collections.Counter); exemples = collections.defaultdict(list)
for n in arbre.body:
    if not isinstance(n, ast.FunctionDef):
        continue
    for d in n.decorator_list:
        if not (isinstance(d, ast.Call) and getattr(d.func, 'attr', '') == 'route' and d.args and isinstance(d.args[0], ast.Constant)):
            continue
        ch = d.args[0].value; meth = ('GET',)
        for k in d.keywords:
            if k.arg == 'methods' and isinstance(k.value, (ast.List, ast.Tuple)):
                meth = tuple(sorted(e.value for e in k.value.elts))
        mod = next((m for m, rx in MODS.items() if re.search(rx, ch)), None)
        if not mod or re.search(r'debug|test|fix', ch):
            continue
        corps = '\n'.join(L[n.lineno - 1:n.end_lineno]); deco = '\n'.join(L[d.lineno - 1:n.lineno])
        s = st[mod]; s['routes'] += 1
        chemins[(mod, re.sub(r'<[^>]+>', '<>', ch), meth)].append(n.name)
        ecrit = bool(set(meth) & {'POST', 'PUT', 'DELETE', 'PATCH'})
        if ecrit:
            s['ecritures'] += 1
            ex = re.sub(r'<int:[a-z_]+>', '1', re.sub(r'<[a-z_]+>', 'x', ch))
            if module_de_la_requete(n.name, ex) is None and not re.search(r"has_permission\(|should_display_module\(", corps):
                s['ecr_non_gardees'] += 1; exemples[mod].append('écriture sans garde : ' + ch)
        if 'login_required' not in deco and 'super_admin_required' not in deco and 'login_required' not in '\n'.join(L[n.decorator_list[0].lineno-1:n.lineno]):
            s['publiques'] += 1; exemples[mod].append('sans connexion : ' + ch)
        for imp in re.findall(r'from models import \(?([^\n)]+)', corps):
            for nom in re.findall(r'\b([A-Z][A-Za-z0-9]+)\b', imp):
                if nom not in modeles:
                    s['modele_absent'] += 1; exemples[mod].append(f'modèle inexistant {nom} : {ch}')
        s['erreur_brute'] += len(re.findall(r"str\(e\)", corps)) > 0
        s['print'] += len(re.findall(r"^\s*print\(", corps, re.M))
        if meth == ('GET',) and re.search(r'supprimer|cloturer|archiver|valider|restaurer|activer|resoudre|escalader|terminer', ch) and not re.search('export|pdf|telecharger', ch):
            s['get_modif'] += 1; exemples[mod].append('modifie par simple lien : ' + ch)
for (mod, ch, m), fs in chemins.items():
    if len(fs) > 1:
        st[mod]['doublons'] += 1; exemples[mod].append(f'adresse en double {ch} {m} : {fs}')
print(f"{'module':26}{'routes':>7}{'écrit.':>7}{'non gardées':>12}{'publiques':>10}{'doublons':>9}{'GET modif':>10}{'modèle abs.':>12}{'str(e)':>7}{'print':>7}")
for m in MODS:
    s = st[m]
    print(f"{m:26}{s['routes']:>7}{s['ecritures']:>7}{s['ecr_non_gardees']:>12}{s['publiques']:>10}{s['doublons']:>9}{s['get_modif']:>10}{s['modele_absent']:>12}{s['erreur_brute']:>7}{s['print']:>7}")
for m in MODS:
    for e in exemples[m][:8]:
        print(f'  [{m}] {e}')
