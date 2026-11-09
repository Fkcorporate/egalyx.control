"""Ce qui n'est pas disponible n'apparaît nulle part + page des permissions cohérente avec les modules."""
import re, sys
import socle, objets
from socle import Muet, appel
with Muet():
    A, ids = socle.preparer()
    O = objets.peupler_objets(A, ids)['a']
import models as M
from models import db
from egalyx.modules_client import MODULES
res = []
def verif(nom, cond, detail=''):
    res.append(bool(cond)); print('OK   ' if cond else 'ÉCHEC', nom, detail)
def nav(role): return socle.navigateur(A, ids[role])
def page(role, url):
    r = appel(nav(role), 'get', url, follow_redirects=False); socle.cause(A); return r, r.data.decode('utf-8', 'ignore')
def modules(actifs):
    with A.app.app_context():
        c = db.session.get(M.Client, 1); c.modules_actifs = actifs; db.session.commit()
TOUS = {k: True for k in MODULES}
PAGES = ['/dashboard', '/risques', f'/cartographie/{O["carto"]}', f'/risque/{O["risque"]}', '/audits', '/ma-semaine',
         '/plans-action/independants', '/dashboard-strategique', '/aide/']
HREF = re.compile(r'<a\b[^>]*\bhref="(/[^"#?]*)')
ACTION = re.compile(r'<form\b[^>]*\baction="(/[^"#?]*)')
def modules_lies(html):
    from egalyx.modules_client import module_de_la_requete
    trouves = {}
    with A.app.test_request_context():
        ad = A.app.url_map.bind('localhost')
        for rx, meth in ((HREF, 'GET'), (ACTION, 'POST')):
            for chemin in rx.findall(html):
                try:
                    ep, args = ad.match(chemin, method=meth)
                except Exception:
                    continue
                mod = module_de_la_requete(ep, chemin)
                if mod:
                    trouves.setdefault(mod, set()).add((chemin, bool(args)))
    return trouves

print('--- Module non souscrit : invisible partout')
modules(TOUS | {'kri': False, 'incidents': False, 'pca': False})
fuites = {}
for u in PAGES:
    r, t = page('admin_a', u)
    if r.status_code != 200:
        continue
    for mod in ('kri', 'incidents', 'pca'):
        for chemin, _o in modules_lies(t).get(mod, ()):
            fuites.setdefault(mod, set()).add((u, chemin))
verif('Aucun lien ni formulaire vers KRI, incidents ou PCA (admin client, 9 pages)', not fuites, str({k: list(v)[:3] for k, v in fuites.items()}))
r, t = page('admin_a', '/dashboard')
verif('Script de masquage des blocs KRI / incidents / PCA présent', 'blocs des modules indisponibles' in t and 'KRI' in t[t.find('blocs des modules'):][:600])
modules(None)

print('--- Permission absente : fonction invisible')
with A.app.app_context():
    u = db.session.get(M.User, ids['lecteur']); p = dict(u.permissions); p.update({'can_manage_risks': True, 'can_manage_kri': False}); u.permissions = p; db.session.commit()
fuites = set()
for url in PAGES:
    r, t = page('lecteur', url)
    if r.status_code != 200:
        continue
    for chemin, objet in modules_lies(t).get('kri', ()):
        if not objet:
            fuites.add((url, chemin))
verif('Sans permission KRI : aucun lien vers la liste ou la création de KRI', not fuites, str(list(fuites)[:4]))

print('--- IA désactivée pour le client')
modules(TOUS | {'ia': False})
fuites = set()
from egalyx.ia import ENDPOINTS_IA
for url in PAGES + [f'/audit/{O.get("audit", 1)}']:
    r, t = page('admin_a', url)
    if r.status_code != 200:
        continue
    with A.app.test_request_context():
        ad = A.app.url_map.bind('localhost')
        for chemin in HREF.findall(t) + ACTION.findall(t):
            try:
                ep, _a = ad.match(chemin, method='GET')
            except Exception:
                try:
                    ep, _a = ad.match(chemin, method='POST')
                except Exception:
                    continue
            if ep in ENDPOINTS_IA:
                fuites.add((url, chemin))
r, t = page('admin_a', '/dashboard')
verif('Aucun lien vers une fonction d\'IA', not fuites, str(list(fuites)[:4]))
verif('Les boutons et blocs d\'IA sont masqués (scripts présents)', 'eg-ia-masque' in t and 'intelligence artificielle' in t.lower())
r, _ = page('admin_a', '/analyse-ia')
verif('Les pages d\'IA restent bloquées côté serveur', r.status_code in (302, 403, 404), str(r.status_code))
modules(None)

print('--- Registre des recommandations : module et permissions')
r, t = page('admin_a', '/permissions-inexistante')
r, t = page('admin_a', f'/client-admin/utilisateur/{ids["lecteur"]}/permissions')
verif('Page des permissions : le registre des recommandations y figure', r.status_code == 200 and 'can_view_recommandations' in t and 'can_manage_recommandations' in t, str(r.status_code))
verif('… ainsi que les permissions oubliées jusqu\'ici (voir les campagnes, réaliser, PCA…)', all(x in t for x in ('can_view_campaigns', 'can_conduct_campaigns', 'can_view_bcp', 'can_view_incidents', 'can_manage_logigram')))
r, t = page('lecteur', '/recommandations/registre')
verif('Sans permission : pas de registre', r.status_code in (302, 403))
with A.app.app_context():
    u = db.session.get(M.User, ids['lecteur']); p = dict(u.permissions); p['can_view_recommandations'] = True; u.permissions = p; db.session.commit()
r, t = page('lecteur', '/recommandations/registre')
verif('« Voir le registre » : le registre s\'ouvre, sans bouton de création', r.status_code == 200 and 'externe/nouvelle' not in t, str(r.status_code))
r, _ = page('lecteur', '/recommandations/externe/nouvelle')
verif('… et la création est refusée', r.status_code in (302, 403))
modules(TOUS | {'recommandations': False})
r, t = page('admin_a', '/dashboard')
verif('Module non souscrit : registre absent du menu', 'recommandations/registre' not in t and '/recommandations/' not in re.sub(r'<script.*?</script>', '', t, flags=re.S))
verif('… et inaccessible', page('admin_a', '/recommandations/registre')[0].status_code in (302, 403, 404))
r, t = page('operateur', '/operateur/profil')
verif('… et absent de l\'espace opérateur', r.status_code == 200 and 'recommandations/miennes' not in t, str(r.status_code))

print('--- Page des permissions : modules non souscrits verrouillés')
modules(TOUS | {'kri': False, 'recommandations': False})
r, t = page('admin_a', f'/client-admin/utilisateur/{ids["lecteur"]}/permissions')
kri = re.search(r'<input[^>]*id="can_manage_kri"[^>]*>', t)
verif('La case « Gérer les KRI » est grisée (module non souscrit)', kri and 'disabled' in kri.group(0) and 'Module non souscrit' in t, kri.group(0) if kri else '')
r = appel(nav('admin_a'), 'post', f'/client-admin/utilisateur/{ids["lecteur"]}/permissions',
          data={'can_view_dashboard': 'y', 'can_manage_kri': 'y', 'can_manage_recommandations': 'y', 'can_manage_campaigns': 'y'}); socle.cause(A)
with A.app.app_context():
    p = db.session.get(M.User, ids['lecteur']).permissions
verif('Requête forcée : les permissions des modules non souscrits restent à « non »', p.get('can_manage_kri') is False and p.get('can_manage_recommandations') is False, str({k: p.get(k) for k in ('can_manage_kri', 'can_manage_recommandations')}))
verif('« Gérer les campagnes » entraîne « voir les campagnes »', p.get('can_manage_campaigns') and p.get('can_view_campaigns'))
with A.app.app_context():
    u = db.session.get(M.User, ids['gestionnaire']); p = dict(u.permissions); p['can_manage_kri'] = True; u.permissions = p; db.session.commit()
    verif('Tout autre écran (enregistrement direct) : le droit reste sans effet tant que le module est désactivé',
          db.session.get(M.User, ids['gestionnaire']).has_permission('can_manage_kri') is False)
modules(None)

print(f'\n{sum(res)}/{len(res)} vérifications réussies')
sys.exit(0 if all(res) else 1)
