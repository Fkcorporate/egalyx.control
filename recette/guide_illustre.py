"""Recette : guide illustré pas à pas dans le centre d'aide (captures annotées)."""
import os
import re
os.environ['EGALYX_COLLECTE_AUTO'] = '0'
import socle
from socle import Muet
res = []


def verif(nom, cond, detail=''):
    res.append(bool(cond)); print('OK   ' if cond else 'ÉCHEC', nom, detail)


with Muet():
    A, ids = socle.preparer()
from egalyx import aide, aide_contenu
from egalyx.guide_illustre import GUIDES, CATEGORIE

print('--- Contenu')
verif('catégorie « Guide illustré » en tête du centre d’aide', aide_contenu.CATEGORIES[0] == CATEGORIE)
verif('23 guides', len(GUIDES) == 23, str(len(GUIDES)))
verif('identifiants uniques dans tout le centre d’aide', len({a['id'] for a in aide_contenu.ARTICLES}) == len(aide_contenu.ARTICLES))
verif('guides ajoutés une seule fois', sum(1 for a in aide_contenu.ARTICLES if a['cat'] == 'guide') == len(GUIDES))
statique = os.path.join(A.app.root_path, 'static')
images = [x['image'] for g in GUIDES for x in g['illustrations']]
manquantes = [i for i in images if not os.path.isfile(os.path.join(statique, i))]
verif(f'{len(images)} captures présentes sur le disque', not manquantes, str(manquantes))
from PIL import Image
petites = []
for i in images:
    im = Image.open(os.path.join(statique, i))
    if im.width < 1000:
        petites.append(i)
verif('captures lisibles (≥ 1000 px de large)', not petites, str(petites))
lourdes = [i for i in images if os.path.getsize(os.path.join(statique, i)) > 400_000]
verif('captures légères (< 400 Ko chacune)', not lourdes, str(lourdes))
verif('chaque étape a un titre ; chaque repère un texte', all(x['titre'] and all(r.strip() for r in x['reperes']) for g in GUIDES for x in g['illustrations']))
verif('texte des étapes repris pour la recherche et l’assistant', all(len(g['etapes']) == len(g['illustrations']) for g in GUIDES))
with A.app.test_request_context():
    mauvais = [(g['id'], e) for g in GUIDES for _l, e in g['liens'] if e not in A.app.view_functions]
verif('liens « aller à la page » valides', not mauvais, str(mauvais))

print('--- Pages')
c = socle.navigateur(A, ids['admin_a'])
with Muet():
    r = c.get('/aide/')
h = r.data.decode()
verif('accueil de l’aide : bandeau du guide illustré', r.status_code == 200 and h.count('class="gi-tuile"') == len(GUIDES), str(h.count('class="gi-tuile"')))
verif('accueil : vignettes en chargement différé', 'loading="lazy"' in h)
verif('accueil : la catégorie n’est pas listée deux fois', 'id="cat-guide"' not in h)
with Muet():
    r = c.get('/aide/fiche/guide-cartographie')
h = r.data.decode()
g = next(x for x in GUIDES if x['id'] == 'guide-cartographie')
verif('fiche guide : 200', r.status_code == 200)
verif('fiche guide : une section par capture', h.count('class="pg-carte gi-etape"') == len(g['illustrations']))
verif('fiche guide : sommaire des étapes', h.count('href="#etape-') == len(g['illustrations']))
verif('fiche guide : pastilles numérotées = repères', h.count('class="gi-pastille"') == sum(len(x['reperes']) for x in g['illustrations']))
srcs = re.findall(r'<img src="([^"]+)"', h)
ok_img = all(c.get(s).status_code == 200 for s in srcs if '/static/aide/guide/' in s)
verif('fiche guide : images servies', ok_img and len([s for s in srcs if '/static/aide/guide/' in s]) == len(g['illustrations']))
verif('fiche guide : agrandissement (bouton + fenêtre)', 'gi-agrandir' in h and 'id="giZoom"' in h and "key === 'Escape'" in h)
verif('fiche guide : texte alternatif sur chaque image', h.count('alt="Capture d\'écran') == len(g['illustrations']) or h.count('alt="Capture d&#39;écran') == len(g['illustrations']))
verif('fiche guide : guides précédent et suivant proposés', 'href="/aide/fiche/guide-risque"' in h and 'href="/aide/fiche/guide-installer-mac"' in h)
corps = h.split('class="pg-carte gi-etape"', 1)[1].split('id="giZoom"', 1)[0]
verif('fiche guide : **gras** rendu en gras', '<strong>Nouvelle Cartographie</strong>' in corps and '**' not in corps)
with Muet():
    r = c.get('/aide/fiche/presentation')
verif('fiche ordinaire inchangée (pas de section guide)', r.status_code == 200 and 'class="pg-carte gi-etape"' not in r.data.decode())
with Muet():
    r = c.get('/aide/guide-complet')
h = r.data.decode()
verif('guide complet imprimable : toutes les captures', r.status_code == 200 and h.count('<figure class="illu">') == len(images), str(h.count('<figure class="illu">')))
tous = 0
for gg in GUIDES:
    with Muet():
        tous += c.get(f"/aide/fiche/{gg['id']}").status_code == 200
verif('les 23 guides s’ouvrent', tous == len(GUIDES), str(tous))

print('--- Droits')
anonyme = A.app.test_client()
with Muet():
    r = anonyme.get('/aide/')
verif('visiteur non connecté : aide accessible, sans le guide (captures internes)', r.status_code == 200 and 'gi-tuile"' not in r.data.decode().split('</style>')[-1])
with Muet():
    r = anonyme.get('/aide/fiche/guide-cartographie')
verif('visiteur non connecté : fiche guide refusée', r.status_code == 404, str(r.status_code))
lecteur = socle.navigateur(A, ids['lecteur'])
with Muet():
    r = lecteur.get('/aide/fiche/guide-administration')
h = r.data.decode()
verif('guide administrateur vu par un simple utilisateur : consultable, avec le cadenas et sans lien', r.status_code == 200 and 'class="ad-verrou"' in h and 'fa-arrow-right me-1"></i>Utilisateurs' not in h)
with Muet():
    h = c.get('/aide/fiche/guide-administration').data.decode()
verif('guide administrateur vu par l’administrateur : liens présents, pas de cadenas', 'class="ad-verrou"' not in h and 'fa-arrow-right me-1"></i>Utilisateurs' in h)

print('--- Recherche et assistant')
with A.app.test_request_context():
    from flask_login import login_user
    import models as M
    u = M.User.query.get(ids['admin_a']); login_user(u)
    trouve = [a['id'] for _s, a in aide.chercher('installer l’application sur mon mac')]
    verif('recherche « installer l’application sur mon mac » → guide Mac', trouve and trouve[0] == 'guide-installer-mac', str(trouve[:3]))
    trouve = [a['id'] for _s, a in aide.chercher('guide illustré cartographie')]
    verif('recherche « guide illustré cartographie » → guide cartographie', 'guide-cartographie' in trouve[:2], str(trouve[:3]))
    rep = aide.repondre('comment installer l application sur mac')
    verif('assistant : répond avec le guide et un bouton « Fiche complète »', rep and rep['article'] == 'guide-installer-mac'
          and any('guide-installer-mac' in x['url'] for x in rep['actions']), str(rep and rep.get('article')))

print(f'\n{sum(res)}/{len(res)} vérifications réussies')
