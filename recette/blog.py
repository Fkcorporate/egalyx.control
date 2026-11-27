"""Recette : blog public — vrais articles servis, SEO par page, catégories, sitemap, pages suspendues, redirections."""
import re, json, collections
import socle
from socle import Muet
res = []


def verif(nom, cond, detail=''):
    res.append(bool(cond))
    print('OK   ' if cond else 'ÉCHEC', nom, detail)


with Muet():
    A, ids = socle.preparer()
from egalyx import blog
c = A.app.test_client()
arts = blog.catalogue(A.app)
verif('Articles trouvés dans templates/blog', len(arts) >= 1, str(len(arts)))
erreurs, titres, descs, pb = [], collections.Counter(), collections.Counter(), collections.defaultdict(list)
for a in arts:
    r = c.get(a['url']); t = r.get_data(as_text=True)
    if r.status_code != 200:
        erreurs.append((a['slug'], r.status_code)); continue
    titre = re.search(r'<title>(.*?)</title>', t, re.S).group(1).strip()
    desc = (re.search(r'<meta name="description" content="([^"]*)"', t) or [None, ''])[1]
    titres[titre] += 1; descs[desc] += 1
    can = re.findall(r'<link rel="canonical" href="([^"]+)"', t)
    if can != ['https://www.egalyx.com' + a['url']]: pb['canonical'].append(a['slug'])
    if len(titre) > 66: pb['titre long'].append(a['slug'])
    if not 50 <= len(desc) <= 165: pb['description'].append(a['slug'])
    if t.count('<h1') != 1: pb['h1'].append(a['slug'])
    if 'AggregateRating' in t: pb['note'].append(a['slug'])
    for b in re.findall(r'<script type="application/ld\+json">(.*?)</script>', t, re.S):
        try: json.loads(b)
        except Exception: pb['json-ld'].append(a['slug'])
verif('Chaque article s\'affiche (vraie page, plus l\'article fictif)', not erreurs, str(erreurs[:5]))
h1s = collections.Counter(a['h1'] for a in arts)
verif('Titres H1 uniques (pas deux articles identiques)', all(v == 1 for v in h1s.values()), str([k for k, v in h1s.items() if v > 1][:3]))
verif('Titres uniques', all(v == 1 for v in titres.values()), str([k for k, v in titres.items() if v > 1][:3]))
verif('Descriptions uniques', all(v == 1 for v in descs.values()))
for k in ('canonical', 'titre long', 'description', 'h1', 'note', 'json-ld'):
    verif(f'SEO : {k} correct sur toutes les pages', not pb[k], str(pb[k][:5]))
r = c.get('/blog/'); t = r.get_data(as_text=True)
verif('Page /blog/ : tous les articles, catégories, données structurées', r.status_code == 200 and t.count('class="carte"') + 1 >= len(arts) and 'CollectionPage' in t)
r = c.get('/blog/categorie/conformite')
verif('Catégorie', r.status_code == 200 and 'Conformité' in r.get_data(as_text=True))
r = c.get('/blog/categorie/Conformité'); verif('Ancienne adresse de catégorie → 301', r.status_code == 301)
verif('Adresse inconnue → 404 (plus d\'article fictif)', c.get('/blog/article-qui-n-existe-pas').status_code == 404)
verif('Adresse en .html → 301 vers l\'adresse propre', c.get(arts[0]['url'] + '.html').status_code == 301)
for s in blog.SUSPENDUES:
    verif(f'Page suspendue « {s} » : 404', c.get('/blog/' + s).status_code == 404)
for s, cible in blog.FUSIONS.items():
    r = c.get('/blog/' + s); verif(f'Doublon fusionné « {s} » → 301', r.status_code == 301 and r.headers['Location'].endswith(cible))
sm = c.get('/sitemap.xml').get_data(as_text=True)
verif('Sitemap : tous les articles, sans les pages suspendues', all(a['url'] in sm for a in arts) and not any('/blog/' + s + '<' in sm for s in blog.SUSPENDUES))
t = c.get('/home').get_data(as_text=True)
verif('Accueil : une seule canonical, la sienne', re.findall(r'rel="canonical" href="([^"]+)"', t) == ['https://www.egalyx.com/home'])
verif('Menu : lien Blog', 'href="/blog/">Blog</a>' in t)
print(f'\n{sum(res)}/{len(res)} vérifications réussies')
