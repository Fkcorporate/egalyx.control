"""
egalyx/blog.py — le blog public sert enfin les vrais articles (templates/blog/<slug>.html).

Avant : /blog/<slug> affichait toujours le même article RGPD fictif, quelle que soit l'adresse (100+ pages identiques
pour Google), et /blog/categorie/<x> des articles inventés.
Maintenant :
  - /blog/<slug>            → templates/blog/<slug>.html (404 propre sinon ; anciennes adresses → redirection 301) ;
  - /blog/                  → tous les articles, par catégorie, avec image, résumé et temps de lecture ;
  - /blog/categorie/<cat>   → articles de la catégorie ;
  - /sitemap.xml            → complété avec tous les articles (date de mise à jour réelle du fichier).
Les informations de chaque article (titre, description, catégorie, image, temps de lecture) sont lues dans le fichier
lui-même ; on peut les préciser en tête d'article :  {# blog: date=2026-03-15 categorie=conformite image=/static/... #}
"""
import json
import os
import re
import threading
from datetime import date, datetime
from html import unescape

from flask import abort, redirect, render_template, request, url_for
from jinja2 import TemplateNotFound

SITE = 'https://www.egalyx.com'
DATE_DEFAUT = '2026-11-12'          # date de la remise à plat du blog (modifiable article par article)
PAS_ARTICLES = {'index', 'article', 'article-template', 'auteur', 'categorie', 'tag', '_layout', '_carte'}
# Pages suspendues : avis clients et notes (« 1500+ avis certifiés », témoignages nominatifs) non vérifiables.
# Publier de faux avis est une pratique commerciale trompeuse (code de la consommation) et Google pénalise les fausses
# notes. Elles répondent « page introuvable » et ne sont ni listées ni dans le sitemap. Pour en remettre une en ligne
# (avec de vrais avis, clients d'accord), retirez son nom de cette liste.
SUSPENDUES = {'egalyx-avis-clients-certifies', 'avis-certifies-clients-egalyx-2026', 'logiciel-audit-interne-avis-clients',
              'avis-retours-clients-egalyx-alternatives'}
# Doublons fusionnés : l'ancienne adresse renvoie (301) vers la version complète, Google garde un seul article.
FUSIONS = {'conformite-rgpd-logiciel-gestion-risques': 'conformite-rgpd-logiciel-risques',
           # anciens liens de la page d'accueil (articles qui n'ont jamais existé)
           'comment-ia-transforme-audit-interne': 'ia-audit-interne-2026',
           'cartographie-risques-methodologie': 'cartographie-risques-entreprise-methode-2026',
           'nouveautes-ohada-2024': 'mise-en-conformite-ohada-entreprises-ivoiriennes'}
# « Dernières publications » de la page d'accueil : ces articles d'abord (avec leur image), sinon les plus récents
A_LA_UNE = [('ia-audit-interne-2026', '/static/images/blog-ia-audit.jpg'),
            ('cartographie-risques-entreprise-methode-2026', '/static/images/blog-cartographie.jpg'),
            ('mise-en-conformite-ohada-entreprises-ivoiriennes', '/static/images/blog-conformite.jpg')]

CATEGORIES = [   # (code, libellé, description, mots déclencheurs dans l'adresse) — l'ordre compte
    ('cybersecurite', 'Cybersécurité', 'Risques cyber, sécurité informatique et protection des données en entreprise.', ('cyber', 'securite', 'iot')),
    ('choisir-un-logiciel', 'Choisir un logiciel', 'Prix, comparatifs, retours d’expérience et critères de choix d’un logiciel d’audit, de contrôle interne ou de gestion des risques.',
     ('prix', 'devis', 'comparatif', 'avis', 'roi-', 'rentabiliser', 'achat', 'choisir', 'choix', 'meilleur', 'couts', 'gratuit', 'pourquoi')),
    ('conformite', 'Conformité', 'RGPD, OHADA, réglementations sectorielles et éthique : méthodes pour rester conforme.', ('rgpd', 'ohada', 'conformite', 'ethique', 'reglementaire')),
    ('kri', 'Indicateurs & KRI', 'Indicateurs clés de risque : choisir, mesurer et piloter.', ('kri', 'indicateurs')),
    ('gestion-des-risques', 'Gestion des risques', 'Cartographie, ISO 31000, risques financiers et pilotage des risques d’entreprise.', ('cartographie', 'risques', 'iso-31000', 'management')),
    ('controle-interne', 'Contrôle interne', 'Mettre en place et faire vivre un dispositif de contrôle interne efficace.', ('controle-interne', 'controle_interne', 'normes_controle')),
    ('gouvernance-rse', 'Gouvernance & RSE', 'Gouvernance d’entreprise, RSE et critères ESG.', ('gouvernance', 'rse', 'esg')),
    ('audit-interne', 'Audit interne', 'Méthodes, normes, planification et outils de l’audit interne.', ('audit',)),
]
CAT = {c[0]: c for c in CATEGORIES}
IMAGES_CAT = {c[0]: f'/static/images/blog/categories/{c[0]}.jpg' for c in CATEGORIES}
OG_CAT = {c[0]: f'/static/images/blog/categories/{c[0]}-og.jpg' for c in CATEGORIES}

_cache, _verrou = {}, threading.Lock()


def _dossier(app):
    return os.path.join(app.root_path, 'templates', 'blog')


def _texte(html):
    html = re.sub(r'\{[%#].*?[%#]\}', ' ', html, flags=re.S)
    html = re.sub(r'\{\{.*?\}\}', ' ', html, flags=re.S)
    html = re.sub(r'<(script|style)[^>]*>.*?</\1>', ' ', html, flags=re.S | re.I)
    return re.sub(r'\s+', ' ', unescape(re.sub(r'<[^>]+>', ' ', html))).strip()


def _bloc(src, nom):
    m = re.search(r'\{%-?\s*block ' + nom + r'\s*-?%\}(.*?)\{%-?\s*endblock', src, re.S)
    return _texte(m.group(1)) if m else ''


def categorie_de(slug, mots=''):
    cle = slug.lower()
    for code, _l, _d, declencheurs in CATEGORIES:
        if any(d in cle for d in declencheurs):
            return code
    return 'audit-interne'


def _lire(chemin, slug):
    src = open(chemin, encoding='utf-8', errors='replace').read()
    entete = dict(re.findall(r'(\w+)=(\S+)', (re.search(r'\{#\s*blog:(.*?)#\}', src, re.S) or [None, ''])[1] or ''))
    titre = _bloc(src, 'title') or slug.replace('-', ' ').capitalize()
    titre_court = re.split(r'\s+[|–-]\s+(?:Blog\s+)?Egalyx.*$', titre)[0].strip()
    h1m = re.search(r'<h1[^>]*>(.*?)</h1>', src, re.S)
    h1 = _texte(h1m.group(1)) if h1m else titre_court
    h1 = re.sub(r'^[^\wÀ-ÿ]+', '', h1).strip()                     # émoji de tête retiré pour les listes
    desc = _bloc(src, 'meta_description')
    if not desc:
        m = re.search(r'<meta name="description" content="([^"]+)"', src)
        desc = unescape(m.group(1)) if m else ''
    corps = src.split('{% block content %}', 1)[-1]
    if not desc:
        p = re.search(r'<p[^>]*>(.*?)</p>', corps, re.S)
        desc = _texte(p.group(1)) if p else ''
    if len(desc) > 158:
        desc = desc[:155].rsplit(' ', 1)[0] + '…'
    mots = _bloc(src, 'meta_keywords')
    cat = entete.get('categorie') if entete.get('categorie') in CAT else categorie_de(slug, mots)
    nb_mots = len(_texte(corps).split())
    canon = re.search(r'\{%\s*block canonical\s*%\}\s*https?://[^/]+/blog/([^\s{]+?)\s*\{%', src)
    modif = datetime.fromtimestamp(os.path.getmtime(chemin)).date().isoformat()
    return {
        'slug': slug, 'url': f'/blog/{slug}', 'titre': titre_court, 'titre_page': titre, 'h1': h1, 'description': desc,
        'mots_cles': mots, 'categorie': cat, 'categorie_libelle': CAT[cat][1],
        'image': entete.get('image') or IMAGES_CAT[cat], 'image_og': entete.get('image') or OG_CAT[cat],
        'date': entete.get('date', DATE_DEFAUT), 'date_modif': max(modif, entete.get('date', DATE_DEFAUT)),
        'lecture': max(2, round(nb_mots / 220)), 'mots': nb_mots,
        'jsonld_propre': bool(re.search(r'"@type"\s*:\s*"(BlogPosting|Article|NewsArticle)"', src)),
        'fil_propre': 'breadcrumb' in corps, 'autonome': '{% extends' not in src,
        'ancien_slug': canon.group(1).strip('/') if canon and canon.group(1).strip('/') != slug else None,
    }


def catalogue(app):
    """Tous les articles (mis en cache, relus quand un fichier change)."""
    dossier = _dossier(app)
    try:
        noms = sorted(f for f in os.listdir(dossier) if f.endswith('.html'))
    except OSError:
        return []
    signature = tuple((n, os.path.getmtime(os.path.join(dossier, n))) for n in noms)
    with _verrou:
        if _cache.get('signature') == signature:
            return _cache['articles']
    articles = []
    for n in noms:
        slug = n[:-5]
        if slug in PAS_ARTICLES or slug in SUSPENDUES or slug in FUSIONS or slug.startswith('_'):
            continue
        try:
            articles.append(_lire(os.path.join(dossier, n), slug))
        except Exception:  # noqa: BLE001
            continue
    articles.sort(key=lambda a: (a['date'], a['titre']), reverse=True)
    with _verrou:
        _cache.update(signature=signature, articles=articles,
                      redirections={a['ancien_slug']: a['slug'] for a in articles if a['ancien_slug']})
    return articles


def _par_slug(app, slug):
    for a in catalogue(app):
        if a['slug'] == slug:
            return a
    return None


def lies(app, art, n=3):
    meme = [a for a in catalogue(app) if a['categorie'] == art['categorie'] and a['slug'] != art['slug']]
    if len(meme) < n:
        meme += [a for a in catalogue(app) if a['slug'] != art['slug'] and a not in meme][:n - len(meme)]
    # rotation stable : des articles différents d'une page à l'autre (maillage interne)
    k = sum(map(ord, art['slug'])) % max(1, len(meme))
    return (meme[k:] + meme[:k])[:n]


def jsonld_article(art):
    data = [{
        '@context': 'https://schema.org', '@type': 'BreadcrumbList', 'itemListElement': [
            {'@type': 'ListItem', 'position': 1, 'name': 'Accueil', 'item': SITE + '/'},
            {'@type': 'ListItem', 'position': 2, 'name': 'Blog', 'item': SITE + '/blog/'},
            {'@type': 'ListItem', 'position': 3, 'name': art['categorie_libelle'], 'item': f"{SITE}/blog/categorie/{art['categorie']}"},
            {'@type': 'ListItem', 'position': 4, 'name': art['h1'][:110], 'item': SITE + art['url']}]}]
    if not art['jsonld_propre']:
        data.append({
            '@context': 'https://schema.org', '@type': 'BlogPosting', 'headline': art['h1'][:110],
            'description': art['description'], 'image': [SITE + art['image_og'], SITE + art['image']],
            'datePublished': art['date'], 'dateModified': art['date_modif'], 'inLanguage': 'fr-FR',
            'articleSection': art['categorie_libelle'], 'keywords': art['mots_cles'] or None, 'wordCount': art['mots'],
            'mainEntityOfPage': {'@type': 'WebPage', '@id': SITE + art['url']},
            'author': {'@type': 'Organization', 'name': 'Équipe Egalyx', 'url': SITE + '/a-propos'},
            'publisher': {'@type': 'Organization', 'name': 'Egalyx Control',
                          'logo': {'@type': 'ImageObject', 'url': SITE + '/static/logo-512x512.png'}}})
    return json.dumps([{k: v for k, v in d.items() if v is not None} for d in data], ensure_ascii=False, indent=1)


def enregistrer(app):
    from egalyx.commun import exempter_controle_ancien

    def page_blog():
        arts = catalogue(app)
        cats = [(c[0], c[1], sum(1 for a in arts if a['categorie'] == c[0])) for c in CATEGORIES]
        return render_template('blog/index.html', articles=arts, categories=[c for c in cats if c[2]],
                               categorie_active=None, total=len(arts))

    def page_categorie(categorie):
        if categorie not in CAT:
            # anciens liens (« Gestion des risques », « conformité »…) : on retrouve la catégorie
            import unicodedata
            simple = unicodedata.normalize('NFKD', categorie.lower()).encode('ascii', 'ignore').decode().replace(' ', '-')
            trouve = next((c[0] for c in CATEGORIES if simple in (c[0], c[0].replace('-', '')) or c[0].startswith(simple)), None)
            if trouve:
                return redirect(url_for('blog_categorie', categorie=trouve), 301)
            abort(404)
        arts = [a for a in catalogue(app) if a['categorie'] == categorie]
        cats = [(c[0], c[1], sum(1 for a in catalogue(app) if a['categorie'] == c[0])) for c in CATEGORIES]
        return render_template('blog/index.html', articles=arts, categories=[c for c in cats if c[2]],
                               categorie_active=CAT[categorie], total=len(catalogue(app)))

    def page_article(slug):
        if (slug or '').endswith('.html'):
            return redirect(url_for('blog_article', slug=slug[:-5]), 301)
        if slug in FUSIONS:
            return redirect(url_for('blog_article', slug=FUSIONS[slug]), 301)
        if not re.fullmatch(r'[A-Za-z0-9_\-]{1,120}', slug or '') or slug in SUSPENDUES or slug in PAS_ARTICLES:
            abort(404)
        art = _par_slug(app, slug)
        if art is None:
            cible = _cache.get('redirections', {}).get(slug)
            if cible:
                return redirect(url_for('blog_article', slug=cible), 301)
            abort(404)
        try:
            return render_template(f'blog/{slug}.html', article_meta=art, articles_lies=lies(app, art),
                                   jsonld_blog=jsonld_article(art), blog_categories=CATEGORIES,
                                   date_article=datetime.strptime(art['date'], '%Y-%m-%d').strftime('%d/%m/%Y'),
                                   author='l’équipe Egalyx', auteur='l’équipe Egalyx')
        except TemplateNotFound:
            abort(404)

    for ep, f in (('blog_index', page_blog), ('blog_categorie', page_categorie), ('blog_article', page_article)):
        if ep in app.view_functions:
            f.__name__ = ep
            app.view_functions[ep] = f

    # sitemap : on ajoute tous les articles et les catégories
    origine = app.view_functions.get('sitemap')
    if origine is not None:
        def sitemap_complet(*a, **k):
            rep = origine(*a, **k)
            try:
                from flask import make_response
                rep = make_response(rep)
                xml = rep.get_data(as_text=True)
                lignes = []
                for c in CATEGORIES:
                    lignes.append(f'    <url>\n        <loc>{SITE}/blog/categorie/{c[0]}</loc>\n        <changefreq>weekly</changefreq>\n        <priority>0.6</priority>\n    </url>\n')
                for art in catalogue(app):
                    lignes.append(f"    <url>\n        <loc>{SITE}{art['url']}</loc>\n        <lastmod>{art['date_modif']}</lastmod>\n"
                                  f"        <changefreq>monthly</changefreq>\n        <priority>0.7</priority>\n"
                                  f"        <image:image><image:loc>{SITE}{art['image']}</image:loc></image:image>\n    </url>\n")
                xml = xml.replace('<loc>https://www.egalyx.com/blog</loc>', '<loc>https://www.egalyx.com/blog/</loc>')
                xml = xml.replace('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
                                  '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">', 1)
                xml = xml.replace('</urlset>', ''.join(lignes) + '</urlset>')
                rep.set_data(xml)
                rep.mimetype = 'application/xml'
            except Exception:  # noqa: BLE001
                pass
            return rep
        sitemap_complet.__name__ = 'sitemap'
        app.view_functions['sitemap'] = sitemap_complet

    exempter_controle_ancien(app, {'blog_index', 'blog_categorie', 'blog_article', 'sitemap'})
    app.jinja_env.globals['blog_categories_liste'] = CATEGORIES

    def blog_a_la_une(n=3):
        arts, vus = [], set()
        for slug, image in A_LA_UNE:
            a = _par_slug(app, slug)
            if a:
                arts.append(dict(a, image=image)); vus.add(slug)
        arts += [a for a in catalogue(app) if a['slug'] not in vus][:max(0, n - len(arts))]
        return arts[:n]
    app.jinja_env.globals['blog_a_la_une'] = blog_a_la_une
