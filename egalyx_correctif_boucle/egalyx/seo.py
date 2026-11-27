"""
egalyx/seo.py — référencement naturel : une seule adresse par page, un plan du site sans erreur, des pages
de mots-clés réelles.

Ce que fait ce module :
  - page d'accueil servie directement à « / » ; « /home » renvoie définitivement (301) vers « / » ;
  - adresse unique : balise canonical vers https://www.egalyx.com ; la redirection egalyx.com → www dans
    l'application est désactivée par défaut (EGALYX_SEO_REDIRECTION_HOTE=1 pour l'activer) ; les autres hôtes (ex. xxx.onrender.com) reçoivent « X-Robots-Tag: noindex » pour ne pas faire doublon ;
  - barre finale : /fonctionnalites/ renvoie (301) vers /fonctionnalites au lieu d'une erreur 404 ;
  - /robots.txt simple et correct (un seul plan du site, rien qui bloque les pages publiques) ;
  - pages de mots-clés (egalyx/seo_pages.py) servies par un gabarit commun avec FAQ et données structurées ;
  - /ci, /côte-d-ivoire → /cote-divoire (vraie page) ; /afrique → /conformite-ohada-logiciel ;
  - sitemap_base() : la partie « pages du site » du plan du site (le blog ajoute ses articles, egalyx/blog.py).

Réglages (variables d'environnement, facultatives) :
  EGALYX_SEO_HOTE        hôte officiel (défaut www.egalyx.com)
  EGALYX_SEO_REDIRIGER   hôtes à renvoyer vers l'hôte officiel, séparés par des virgules (défaut egalyx.com)
"""
import os
from datetime import date

from flask import Response, abort, redirect, render_template, request, url_for
from flask_login import current_user

from egalyx.seo_pages import PAGES, ORDRE, FAQ_ACCUEIL

HOTE = os.environ.get('EGALYX_SEO_HOTE', 'www.egalyx.com').strip().lower()
SITE = 'https://' + HOTE
A_REDIRIGER = {h.strip().lower() for h in os.environ.get('EGALYX_SEO_REDIRIGER', 'egalyx.com').split(',') if h.strip()}
HOTES_LOCAUX = ('localhost', '127.0.0.1', '0.0.0.0', '::1')
MAJ_SITE = '2026-11-26'   # date de la dernière refonte des pages publiques (lastmod du plan du site)

# Pages publiques du plan du site (en plus des pages de mots-clés et du blog) : (chemin, priorité, fréquence)
PAGES_SITE = [
    ('/', '1.0', 'weekly'),
    ('/fonctionnalites', '0.9', 'monthly'),
    ('/tarifs', '0.8', 'monthly'),
    ('/securite', '0.6', 'monthly'),
    ('/a-propos', '0.6', 'monthly'),
    ('/contact', '0.7', 'yearly'),
    ('/blog/', '0.7', 'weekly'),
]

# Chemins sans intérêt pour les moteurs : réponse marquée « noindex » (la page reste accessible)
PREFIXES_NOINDEX = ('/auth/', '/login', '/logout', '/register', '/inscription', '/reset', '/mot-de-passe',
                    '/dashboard', '/super-admin', '/admin', '/api/', '/questionnaire-public', '/q/', '/signalement')

ROBOTS = """# robots.txt — Egalyx
User-agent: *
Allow: /
Disallow: /api/
Disallow: /admin/
Disallow: /super-admin/
Disallow: /auth/
Disallow: /login
Disallow: /logout
Disallow: /register
Disallow: /dashboard

Sitemap: {site}/sitemap.xml
"""


def _hote():
    return (request.host or '').split(':')[0].strip().lower()


def _local(h):
    return not h or h in HOTES_LOCAUX or h.endswith('.local') or h.endswith('.localhost')


def url_absolue(chemin):
    return SITE + chemin


def sitemap_base():
    """Le plan du site, partie « pages du site » : uniquement des pages qui répondent 200 et sont indexables."""
    lignes = []
    for chemin, prio, freq in PAGES_SITE:
        lignes.append((chemin, MAJ_SITE, freq, prio))
    for slug in ORDRE:
        p = PAGES[slug]
        lignes.append(('/' + slug, p.get('maj', MAJ_SITE), 'monthly', '0.9'))
    xml = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for chemin, maj, freq, prio in lignes:
        xml.append(f'    <url>\n        <loc>{SITE}{chemin}</loc>\n        <lastmod>{maj}</lastmod>\n'
                   f'        <changefreq>{freq}</changefreq>\n        <priority>{prio}</priority>\n    </url>')
    xml.append('</urlset>')
    return Response('\n'.join(xml) + '\n', mimetype='application/xml')


def page_cle(slug):
    p = PAGES.get(slug)
    if not p:
        abort(404)
    liees = [dict(slug=s, **{k: PAGES[s][k] for k in ('court', 'resume')}) for s in p.get('liens', []) if s in PAGES]
    from egalyx import blog as _blog
    from flask import current_app
    articles = []
    for s in p.get('blog', []):
        a = _blog._par_slug(current_app, s)
        if a and a.get('indexable', True):
            articles.append(a)
    return render_template('seo/page_cle.html', page=p, slug=slug, pages_liees=liees, articles=articles,
                           site=SITE, maj_affichee=date.fromisoformat(p.get('maj', MAJ_SITE)).strftime('%d/%m/%Y'))


def enregistrer(app):
    from egalyx.commun import exempter_controle_ancien
    vues = app.view_functions

    # ---------- 1. adresse unique ----------
    # DÉSACTIVÉ PAR DÉFAUT (27/11/2026) : sur Render, le domaine (www / sans www, http / https) est déjà redirigé
    # par l'hébergeur ou par Cloudflare ; une seconde redirection dans l'application provoquait une boucle infinie.
    # La balise canonical (toujours https://www.egalyx.com/...) suffit à Google. Ne l'activer
    # (EGALYX_SEO_REDIRECTION_HOTE=1) que si l'hébergeur ne redirige rien lui-même.
    def seo_hote_canonique():
        if os.environ.get('EGALYX_SEO_REDIRECTION_HOTE', '').strip() != '1':
            return None
        h = _hote()
        if _local(h) or h not in A_REDIRIGER:
            return None
        cible = SITE + request.full_path if request.query_string else SITE + request.path
        return redirect(cible, 301 if request.method in ('GET', 'HEAD') else 308)
    app.before_request_funcs.setdefault(None, []).insert(0, seo_hote_canonique)

    @app.after_request
    def seo_entetes(rep):
        try:
            h = _hote()
            chemin = request.path or '/'
            principal = {HOTE, HOTE[4:] if HOTE.startswith('www.') else 'www.' + HOTE}
            if not _local(h) and h not in principal:
                rep.headers['X-Robots-Tag'] = 'noindex, nofollow'          # onrender.com, sous-domaines clients
            elif chemin.startswith(PREFIXES_NOINDEX) and 'X-Robots-Tag' not in rep.headers:
                rep.headers['X-Robots-Tag'] = 'noindex, follow'
        except Exception:  # noqa: BLE001
            pass
        return rep

    # ---------- 2. page d'accueil à la racine ----------
    def index():
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))
        return render_template('home.html')

    def home():
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))
        return redirect('/', 301)

    if 'index' in vues:
        vues['index'] = index
    if 'home' in vues:
        vues['home'] = home

    # ---------- 3. barre finale : /page/ → /page ----------
    try:
        ancien_404 = next(iter(app.error_handler_spec[None][404].values()))
    except Exception:  # noqa: BLE001
        ancien_404 = None

    def seo_404(e):
        chemin = request.path or '/'
        if request.method in ('GET', 'HEAD') and chemin != '/' and chemin.endswith('/'):
            sans = chemin.rstrip('/') or '/'
            try:
                app.url_map.bind('x').match(sans, method='GET')
                qs = request.query_string.decode('utf-8', 'ignore')
                return redirect(sans + ('?' + qs if qs else ''), 301)
            except Exception:  # noqa: BLE001
                pass
        if ancien_404 is not None:
            return ancien_404(e)
        return render_template('errors/404.html'), 404
    app.register_error_handler(404, seo_404)

    # ---------- 4. robots.txt et plan du site ----------
    def robots_txt():
        return Response(ROBOTS.format(site=SITE), mimetype='text/plain')
    if 'robots_txt' not in vues:
        app.add_url_rule('/robots.txt', 'robots_txt', robots_txt)

    # ---------- 5. pages de mots-clés ----------
    noms = {'robots_txt', 'index', 'home'}
    for slug in ORDRE:
        if slug == 'cote-divoire':
            continue                                   # servie par page_ci ci-dessous (route existante)
        ep = 'seo_' + slug.replace('-', '_')
        if ep not in vues:
            app.add_url_rule('/' + slug, ep, (lambda s=slug: page_cle(s)))
        noms.add(ep)

    def page_ci(*a, **k):
        if request.path.rstrip('/') == '/cote-divoire':
            return page_cle('cote-divoire')
        return redirect('/cote-divoire', 301)
    if 'page_ci' in vues:
        vues['page_ci'] = page_ci
    else:
        app.add_url_rule('/cote-divoire', 'page_ci', page_ci)
        app.add_url_rule('/ci', 'page_ci_court', page_ci)
    noms.add('page_ci')

    def page_afrique(*a, **k):
        return redirect('/conformite-ohada-logiciel', 301)
    if 'page_afrique' in vues:
        vues['page_afrique'] = page_afrique
        noms.add('page_afrique')

    exempter_controle_ancien(app, noms)
    app.jinja_env.globals['seo_faq_accueil'] = FAQ_ACCUEIL
    app.jinja_env.globals['seo_pages_cles'] = lambda: [dict(slug=s, **{k: PAGES[s][k] for k in ('court', 'resume')})
                                                       for s in ORDRE]
