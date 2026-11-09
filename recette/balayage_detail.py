"""Pages de détail (avec identifiant) : erreurs serveur par rôle, et fuites entre organisations
(l'admin de l'organisation B ne doit jamais voir les données de l'organisation A)."""
import re, json, sys
import socle, objets
from socle import Muet, appel
DANGER = socle.DANGER
with Muet():
    A, ids = socle.preparer()
    obj = objets.peupler_objets(A, ids)
MARQUES_A = ['Carto a', 'Risque a', 'Programme a', 'Mission a', 'Reco a', 'Campagne a', 'Plan a', 'Direction a',
             'PA-a', 'MA-a', 'PL-a', 'CC-a', 'PAC-a', 'R-a<', 'Risque proposé a']
routes = []
for r in A.app.url_map.iter_rules():
    if 'GET' not in r.methods or not r.arguments or r.rule.startswith('/static'):
        continue
    if DANGER.search(r.endpoint) or DANGER.search(r.rule):
        continue
    conv = {a: type(r._converters[a]).__name__ for a in r.arguments}
    if any(c != 'IntegerConverter' for c in conv.values()):
        continue
    routes.append(r)
res = {}
for role in sys.argv[1:] or ['gestionnaire', 'admin_a', 'operateur', 'lecteur', 'admin_b']:
    c = socle.navigateur(A, ids[role])
    for r in routes:
        url = r.rule
        for a in r.arguments:
            url = re.sub(r'<int:' + a + '>', '1', url)
        rep = appel(c, 'get', url)
        code = rep.status_code
        err = socle.cause(A) if code >= 500 else ''
        socle.cause(A)
        fuite = ''
        if role == 'admin_b' and code == 200:
            txt = rep.data.decode('utf-8', 'ignore')
            vus = [m for m in MARQUES_A if m in txt]
            fuite = ','.join(vus)
        res.setdefault(r.endpoint, {'rule': r.rule})[role] = [code, err, fuite]
json.dump(res, open(socle.ICI + '/balayage_detail.json', 'w'), ensure_ascii=False, indent=1)
print(len(routes), 'pages de détail')
for role in sys.argv[1:] or ['gestionnaire', 'admin_a', 'operateur', 'lecteur', 'admin_b']:
    print(role, sum(1 for v in res.values() if v.get(role, [0])[0] >= 500), 'erreurs serveur')
print('fuites B->A:', [(v['rule'], v['admin_b'][2]) for v in res.values() if v.get('admin_b', [0, '', ''])[2]])
