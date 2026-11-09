"""Balayage : ouvre toutes les pages sans paramètre, pour chaque rôle, et relève les erreurs serveur."""
import re, json, time, sys
import socle
from socle import Muet, appel
with Muet():
    A, ids = socle.preparer()
DANGER = socle.DANGER
routes = []
for r in A.app.url_map.iter_rules():
    if 'GET' not in r.methods or r.arguments or r.endpoint == 'static' or r.rule.startswith('/static'):
        continue
    if DANGER.search(r.endpoint) or DANGER.search(r.rule):
        continue
    routes.append((r.rule, r.endpoint))
routes.sort()
roles = sys.argv[1:] or ['superadmin', 'admin_a', 'gestionnaire', 'operateur', 'lecteur']
res = {}
t0 = time.time()
for role in roles:
    c = socle.navigateur(A, ids[role])
    for rule, ep in routes:
        r = appel(c, 'get', rule)
        code = r.status_code
        err = socle.cause(A) if code >= 500 else ''
        socle.cause(A)
        res.setdefault(ep, {'rule': rule})[role] = [code, err]
print(len(routes), 'pages,', len(roles), 'rôles,', int(time.time() - t0), 's')
json.dump(res, open(socle.ICI + '/balayage.json', 'w'), ensure_ascii=False, indent=1)
for role in roles:
    ko = [(ep, v[role][1]) for ep, v in res.items() if v[role][0] >= 500]
    print(role, ':', len(ko), 'erreurs serveur')
