"""Recette SEO du site public (test client) : plan du site, adresses, redirections, balises, données structurées."""
import os, re, sys, json
os.environ['EGALYX_COLLECTE_AUTO'] = '0'
sys.path[:0] = ['.', '..']
import socle
from socle import Muet
with Muet():
    A, ids = socle.preparer()
c = A.app.test_client()
W = 'https://www.egalyx.com'
pb = []
def ok(cond, msg):
    if not cond: pb.append(msg)
r = c.get('/sitemap.xml', base_url=W)
xml = r.get_data(as_text=True)
urls = re.findall(r'<loc>([^<]+)</loc>', xml)
print('sitemap', r.status_code, len(urls), 'adresses')
ok(len(urls) == len(set(urls)), 'doublons dans le sitemap')
titres, descs = {}, {}
for u in urls:
    p = u.replace(W, '') or '/'
    r = c.get(p, base_url=W); t = r.get_data(as_text=True)
    if r.status_code != 200:
        pb.append(f'{p} -> {r.status_code} {r.headers.get("Location")}'); continue
    can = re.search(r'<link rel="canonical" href="([^"]+)"', t)
    ok(can and can.group(1) == u, f'{p} canonical {can.group(1) if can else None}')
    rob = re.search(r'<meta name="robots" content="([^"]+)"', t)
    ok(not rob or 'noindex' not in rob.group(1), f'{p} robots {rob.group(1) if rob else None}')
    ok('noindex' not in (r.headers.get('X-Robots-Tag') or ''), f'{p} en-tête noindex')
    ti = re.search(r'<title>\s*(.*?)\s*</title>', t, re.S); ti = ti.group(1).strip() if ti else ''
    de = re.search(r'<meta name="description" content="([^"]*)"', t); de = de.group(1).strip() if de else ''
    ok(ti, f'{p} sans titre'); ok(de, f'{p} sans description')
    titres.setdefault(ti, []).append(p); descs.setdefault(de, []).append(p)
    nb_h1 = len(re.findall(r'<h1[\s>]', t))
    ok(nb_h1 == 1, f'{p} : {nb_h1} h1')
    for bloc in re.findall(r'<script type="application/ld\+json">(.*?)</script>', t, re.S):
        try: json.loads(bloc)
        except Exception as e: pb.append(f'{p} JSON-LD invalide : {e}')
    for mot in ('Marie Laurent', 'Pierre Dubois', 'Clients premium', '500+', 'ratingValue', 'FabriceKonan', '+225-07-07'):
        ok(mot not in t, f'{p} contient « {mot} »')
    for h in set(re.findall(r'href="(/[^"#?]*)', t)):
        if h.startswith(('/static', '/auth', '/application', '/manifest', '/cookies', '/support', '/docs')) or h in ('/',): continue
        if h.startswith('/blog/') or h.lstrip('/') in ('fonctionnalites','tarifs','a-propos','contact','securite','mentions-legales','confidentialite'):
            pass
        rr = c.get(h, base_url=W)
        ok(rr.status_code == 200, f'lien interne {h} (depuis {p}) -> {rr.status_code} {rr.headers.get("Location")}')
for k, v in titres.items():
    ok(len(v) == 1, f'titre en double « {k[:50]} » : {v}')
for k, v in descs.items():
    ok(len(v) == 1, f'description en double : {v}')
print('--- redirections et adresses')
for p, attendu in [('/home', '/'), ('/ci', '/cote-divoire'), ('/afrique', '/conformite-ohada-logiciel'),
                   ('/fonctionnalites/', '/fonctionnalites'), ('/a-propos/', '/a-propos'),
                   ('/blog/conformite-rgpd-2026', '/blog/conformite-rgpd-logiciel-risques'),
                   ('/blog/logiciel_gestion_risques_abidjan', '/cote-divoire'), ('/blog', W + '/blog/')]:
    r = c.get(p, base_url=W); loc = r.headers.get('Location', '')
    ok(r.status_code in (301, 308) and loc.replace(W, '') == attendu.replace(W, ''), f'{p} -> {r.status_code} {loc} (attendu {attendu})')
    print(p, r.status_code, loc)
for base, p in [('https://egalyx.com', '/'), ('https://egalyx.com', '/tarifs?x=1'), ('http://www.egalyx.com', '/blog/')]:
    r = c.get(p, base_url=base, headers={'X-Forwarded-Proto': base.split(':')[0]})
    print(base, p, r.status_code, r.headers.get('Location'))
    ok(r.status_code == 301 and r.headers.get('Location') == W + p, f'{base}{p} -> {r.status_code} {r.headers.get("Location")}')
r = c.get('/', base_url='https://egalyx-control.onrender.com'); print('onrender', r.status_code, r.headers.get('X-Robots-Tag'))
ok('noindex' in (r.headers.get('X-Robots-Tag') or ''), 'onrender sans noindex')
r = c.get('/', base_url=W); ok(r.status_code == 200 and 'X-Robots-Tag' not in r.headers, f'/ -> {r.status_code}')
t = r.get_data(as_text=True); ok('"FAQPage"' in t and 'Questions fréquentes' in t, 'FAQ accueil absente')
r = c.get('/robots.txt', base_url=W); print('robots', r.status_code, r.get_data(as_text=True).count('Sitemap'))
ok(r.status_code == 200 and 'Sitemap: https://www.egalyx.com/sitemap.xml' in r.get_data(as_text=True), 'robots.txt')
r = c.get('/page-qui-n-existe-pas', base_url=W); t = r.get_data(as_text=True)
ok(r.status_code == 404 and 'Page introuvable | Egalyx' in t and 'noindex' in t, f'404 : {r.status_code}')
r = c.get('/auth/login_fullscreen', base_url=W); ok('noindex' in (r.headers.get('X-Robots-Tag') or ''), 'login indexable')
# articles trop courts : noindex
r = c.get('/blog/controle-interne-strategique', base_url=W); t = r.get_data(as_text=True)
ok(r.status_code == 200 and 'content="noindex, follow' in t, f'article court : {r.status_code} noindex absent')
ok('/blog/controle-interne-strategique' not in xml, 'article court dans le sitemap')
for s in ('audit-seo-tools-2025', 'egalyx-avis-clients-certifies'):
    ok(c.get('/blog/' + s, base_url=W).status_code == 404, s + ' toujours en ligne')
print('\n'.join(pb) if pb else 'AUCUN PROBLÈME')
print(len(pb), 'problème(s)')
sys.exit(1 if pb else 0)
