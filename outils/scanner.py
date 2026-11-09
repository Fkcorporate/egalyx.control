"""Analyse statique des routes d'un module de app.py : cloisonnement client, permission, anomalies."""
import ast, re, sys, json
src = open('/home/claude/v4/app.py', encoding='utf-8').read()
lignes = src.split('\n')
arbre = ast.parse(src)
MOTIFS = {k: re.compile(v) for k, v in {
    'logigramme': r"logigramme|processus|etape|organigramme",
    'campagne': r"campagne",
    'audit': r"^/audit|/audits|feuille|constatation|recommandation|mission|programme.?audit|rapport.?audit|/plan-action|plans-action|plan_action",
}.items()}
PERM = re.compile(r"has_permission\(|should_display_module\(|permission_required\(|super_admin_required|admin_required|role_required|is_client_admin|role\s*(==|in)")
CLOISON = re.compile(r"check_client_access\(|get_client_object_or_404\(|get_client_filter\(|client_id\s*=\s*current_user\.client_id|\.client_id\s*!=\s*current_user\.client_id|\.client_id\s*==\s*current_user\.client_id|verifier_acces|_verifier_client|client_id=_?cid|filter_by\([^)]*client_id")
GET = re.compile(r"\.query\.get(_or_404)?\(|session\.get\(\w+,|\.get_or_404\(")
res = []
for n in arbre.body:
    if not isinstance(n, ast.FunctionDef):
        continue
    routes = []
    for d in n.decorator_list:
        if isinstance(d, ast.Call) and getattr(d.func, 'attr', '') == 'route' and d.args and isinstance(d.args[0], ast.Constant):
            m = [k.value for k in d.keywords if k.arg == 'methods']
            meth = [e.value for e in d.keywords[0].value.elts] if d.keywords and isinstance(d.keywords[0].value, ast.List) else ['GET']
            routes.append((d.args[0].value, meth))
    if not routes:
        continue
    corps = '\n'.join(lignes[n.lineno - 1:n.end_lineno])
    deco = '\n'.join(lignes[n.decorator_list[0].lineno - 1:n.lineno])
    for chemin, meth in routes:
        for mod, rx in MOTIFS.items():
            if rx.search(chemin):
                res.append({'module': mod, 'ligne': n.lineno, 'fonction': n.name, 'chemin': chemin, 'methodes': meth,
                            'login': 'login_required' in deco or 'super_admin_required' in deco,
                            'permission': bool(PERM.search(corps + deco)),
                            'id': '<int:' in chemin, 'charge_par_id': bool(GET.search(corps)),
                            'cloison': bool(CLOISON.search(corps)), 'taille': n.end_lineno - n.lineno,
                            'debug': bool(re.search(r"debug|test|fix", chemin))})
                break
json.dump(res, open('/home/claude/audit/routes.json', 'w'), ensure_ascii=False, indent=1)
for mod in MOTIFS:
    r = [x for x in res if x['module'] == mod]
    sans_login = [x for x in r if not x['login']]
    fuite = [x for x in r if x['id'] and x['charge_par_id'] and not x['cloison'] and not x['debug']]
    sans_perm = [x for x in r if not x['permission'] and not x['debug']]
    print(f"\n===== {mod.upper()} : {len(r)} routes — sans connexion : {len(sans_login)}, "
          f"objet chargé par id SANS contrôle d'organisation : {len(fuite)}, sans contrôle de permission : {len(sans_perm)}, debug/test : {sum(x['debug'] for x in r)}")
    for x in fuite:
        print(f"  FUITE  l.{x['ligne']:>6} {','.join(x['methodes']):<12} {x['chemin']}  ({x['fonction']})")
    for x in sans_login:
        print(f"  PUBLIC l.{x['ligne']:>6} {x['chemin']}")
