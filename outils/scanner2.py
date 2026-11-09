import ast, re, json, collections
src = open('/home/claude/v4/app.py', encoding='utf-8').read(); L = src.split('\n'); arbre = ast.parse(src)
modeles = set(re.findall(r'^class (\w+)\(db\.Model\)', open('/home/claude/v4/models.py', encoding='utf-8').read(), re.M))
MODS = {'incidents': r'incident', 'kri': r'/kri|kri/|mesure', 'pca': r'pca|continuite', 'qualite': r'qualite|non-conformite|grille',
        'veille': r'veille|organisme', 'questionnaires': r'questionnaire|question/|reponse', 'plans_action': r'plan-action|plans-action|sous-action',
        'dispositifs': r'dispositif', 'operateur': r'operateur', 'tickets': r'ticket', 'c2n': r'c2n|controle-n2|planification|referentiel|non-conformite'}
VERBES = re.compile(r'supprimer|cloturer|changer|archiver|valider|restaurer|activer|desactiver|dupliquer|delete|terminer|lancer|approuver|rejeter|escalader|resoudre|toggle')
PERM = re.compile(r"has_permission\(|should_display_module\(|permission_required|super_admin_required|admin_required|peut_\w+")
ROLE = re.compile(r"role\s*(==|in|not in)|is_client_admin")
stats = collections.defaultdict(collections.Counter); details = collections.defaultdict(list)
for n in arbre.body:
    if not isinstance(n, ast.FunctionDef):
        continue
    rs = []
    for d in n.decorator_list:
        if isinstance(d, ast.Call) and getattr(d.func, 'attr', '') == 'route' and d.args and isinstance(d.args[0], ast.Constant):
            meth = ['GET']
            for k in d.keywords:
                if k.arg == 'methods' and isinstance(k.value, (ast.List, ast.Tuple)):
                    meth = [e.value for e in k.value.elts]
            rs.append((d.args[0].value, meth))
    if not rs:
        continue
    corps = '\n'.join(L[n.lineno - 1:n.end_lineno]); deco = '\n'.join(L[n.decorator_list[0].lineno - 1:n.lineno])
    for chemin, meth in rs:
        mod = next((m for m, rx in MODS.items() if re.search(rx, chemin)), None)
        if not mod or re.search(r'debug|test|fix', chemin):
            continue
        s = stats[mod]; s['routes'] += 1
        ecrit = bool(set(meth) & {'POST', 'PUT', 'DELETE', 'PATCH'})
        if 'login_required' not in deco and 'super_admin_required' not in deco:
            s['public'] += 1; details[mod].append(('PUBLIC', chemin))
        if PERM.search(corps + deco): s['permission'] += 1
        elif ROLE.search(corps): s['role'] += 1
        else:
            s['aucun'] += 1
            if ecrit: s['ecrit_sans'] += 1
        if meth == ['GET'] and VERBES.search(chemin) and not re.search('export|telecharger|pdf', chemin):
            s['get_modif'] += 1; details[mod].append(('GET-MODIF', chemin))
        for imp in re.findall(r'from models import ([^\n]+)', corps):
            for nom in re.findall(r'\b([A-Z]\w+)\b', imp):
                if nom not in modeles and nom not in ('db',):
                    s['import_inexistant'] += 1; details[mod].append(('MODELE INEXISTANT ' + nom, chemin))
        if 'except:' in corps or 'except Exception' in corps:
            s['erreurs_masquees'] += 1
        if re.search(r"str\(e\)", corps):
            s['erreur_affichee'] += 1
print(f"{'module':16}{'routes':>7}{'perm.':>7}{'rôle':>6}{'aucun':>7}{'écrit sans':>11}{'public':>8}{'GET modif':>10}{'modèle absent':>14}")
for m, s in stats.items():
    print(f"{m:16}{s['routes']:>7}{s['permission']:>7}{s['role']:>6}{s['aucun']:>7}{s['ecrit_sans']:>11}{s['public']:>8}{s['get_modif']:>10}{s['import_inexistant']:>14}")
json.dump({k: v for k, v in details.items()}, open('/home/claude/audit/details2.json', 'w'), ensure_ascii=False, indent=1)
for m, d in details.items():
    for t, c in d:
        print(f"  [{m}] {t:30} {c}")
