"""Recette : feuille de style commune (static/css/egalyx-theme.css).

  - servie, chargée par toutes les mises en page, AVANT tout autre style (les pages gardent la main) ;
  - aucune page n'utilise une variable CSS que ni elle, ni sa mise en page, ni la feuille commune ne définit
    (en clair comme en sombre) — c'est ce qui rendait des fenêtres transparentes ;
  - chaque couleur de surface / texte a sa valeur en mode sombre.
"""
import glob
import os
import re
os.environ['EGALYX_COLLECTE_AUTO'] = '0'
import socle
from socle import Muet, appel
res = []


def verif(nom, cond, detail=''):
    res.append(bool(cond)); print('OK   ' if cond else 'ÉCHEC', nom, detail)


RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T = os.path.join(RACINE, 'templates') + os.sep
CSS = os.path.join(RACINE, 'static', 'css', 'egalyx-theme.css')
MISES_EN_PAGE = ['base.html', 'base_auth.html', 'base_public.html', 'home.html', 'operateur/base_operateur.html', 'pricing.html']

print('--- Fichier et chargement')
verif('le fichier static/css/egalyx-theme.css existe', os.path.exists(CSS))
theme = open(CSS, encoding='utf-8').read()
for f in MISES_EN_PAGE:
    s = open(T + f, encoding='utf-8').read()
    i = s.find('egalyx-theme.css')
    autres = [p for p in (s.find('rel="stylesheet"', i + 20 if i >= 0 else 0), s.find('<style')) if p >= 0]
    premier = i >= 0 and all(i < p for p in [s.find('<style'), s.find('bootstrap')] if p >= 0)
    verif(f'{f} : charge la feuille commune en premier', premier)

USE = re.compile(r'var\(\s*(--[\w-]+)\s*(,)?')
DEF = re.compile(r'(?<![\w-])(--[\w-]+)\s*:(?!:)')
REF = re.compile(r'{%-?\s*(?:extends|include|import|from)\s+["\']([^"\']+)["\']')
LIEN = re.compile(r"url_for\('static',\s*filename=['\"](css/[^'\"]+)['\"]")
_cache = {}


def lire(r):
    if r not in _cache:
        try:
            _cache[r] = open(T + r, encoding='utf-8', errors='ignore').read()
        except OSError:
            _cache[r] = ''
    return _cache[r]


def selecteur(s, pos):
    o = s.rfind('{', 0, pos)
    if o < 0:
        return ''
    return s[max(s.rfind('}', 0, o), s.rfind('>', 0, o), s.rfind(';', 0, o)) + 1:o].strip()


def definitions(s):
    clair, sombre = set(), set()
    for m in DEF.finditer(s):
        if 'dark' in selecteur(s, m.start()):
            sombre.add(m.group(1))
        else:
            clair.add(m.group(1)); sombre.add(m.group(1))
    return clair, sombre


def fermeture(r, vu=None):
    vu = set() if vu is None else vu
    if r not in vu:
        vu.add(r)
        for x in REF.findall(lire(r)):
            fermeture(x, vu)
    return vu


# fragments inclus : on les juge avec la page qui les inclut
inclus_par = {}
for f in glob.glob(T + '**/*.html', recursive=True):
    r = os.path.relpath(f, T)
    for x in re.findall(r'{%-?\s*include\s+["\']([^"\']+)["\']', lire(r)):
        inclus_par.setdefault(x, set()).add(r)
NON_RENDUS = {'blog/article-template.html'}          # modèle de rédaction, jamais servi (egalyx/blog.py)
PY = ''.join(open(f, encoding='utf-8').read() for f in glob.glob(os.path.join(RACINE, 'egalyx', '*.py')))
pc, ps = definitions(PY)


def connues(r):
    clair, sombre = set(pc), set(ps)
    pages = fermeture(r)
    for parent in inclus_par.get(r, ()):
        pages |= fermeture(parent)
    for x in pages:
        c, d = definitions(lire(x)); clair |= c; sombre |= d
        for css in LIEN.findall(lire(x)):
            p = os.path.join(RACINE, 'static', css)
            if os.path.exists(p):
                c, d = definitions(open(p, encoding='utf-8').read()); clair |= c; sombre |= d
    return clair, sombre


print('--- Variables orphelines (utilisées sans valeur de repli, définies nulle part pour la page)')
orphelines = {}
nb = 0
for f in sorted(glob.glob(T + '**/*.html', recursive=True)):
    r = os.path.relpath(f, T)
    if r in NON_RENDUS:
        continue
    utilisees = {m.group(1) for m in USE.finditer(lire(r)) if not m.group(2)}
    # --bs-* : Bootstrap 5.3 ; noms construits par Jinja (--cot-{{…}}) ; --q : posée par le script de la page
    utilisees = {v for v in utilisees if not v.startswith(('--bs-', '--cot-')) and not v.endswith('-') and v != '--q'}
    if not utilisees:
        continue
    nb += 1
    clair, sombre = connues(r)
    manque = sorted((utilisees - clair) | (utilisees - sombre))
    if manque:
        orphelines[r] = manque
verif(f'{nb} pages analysées : aucune variable orpheline', not orphelines, str(dict(list(orphelines.items())[:5])))

print('--- Mode sombre')
racine = re.search(r':root\s*\{([^}]*)\}', theme).group(1)
sombre = re.search(r'\[data-bs-theme="dark"\]\s*\{([^}]*)\}', theme).group(1)
SURFACES = ['--card-bg', '--bg-secondary', '--text-primary', '--text-secondary', '--text-muted', '--border',
            '--eg-surface', '--eg-fond', '--eg-texte', '--eg-bordure', '--neutral-white', '--light', '--dark', '--gray-light']
manque = [v for v in SURFACES if v + ':' not in sombre.replace(' ', '')]
verif('chaque surface / couleur de texte a sa valeur en mode sombre', not manque, str(manque))
verif('le fond des fenêtres est opaque dans les deux modes', '--card-bg:#FFFFFF' in racine.replace(' ', '') and '--card-bg:#1E293B' in sombre.replace(' ', ''))

print('--- Pages réelles')
with Muet():
    A, ids = socle.preparer()
adm = socle.navigateur(A, ids['admin_a'])
r = appel(adm, 'GET', '/static/css/egalyx-theme.css')
verif('la feuille est servie', r.status_code == 200 and b'--card-bg' in r.data, str(r.status_code))
for url in ('/admin/directions?vue=cartes', '/admin/poles', '/dashboard'):
    h = appel(adm, 'GET', url).data.decode()
    i = h.find('egalyx-theme.css')
    verif(f'{url} : feuille commune chargée avant les styles de la page', 0 <= i < h.find('<style'), str(i))
anon = A.app.test_client()
for url in ('/', '/login'):
    rr = anon.get(url, follow_redirects=True)
    verif(f'{url} (public) : feuille commune chargée', b'egalyx-theme.css' in rr.data, str(rr.status_code))
op = socle.navigateur(A, ids['operateur'])
rr = op.get('/operateur/profil', follow_redirects=True)
verif('application des opérateurs : feuille commune chargée', b'egalyx-theme.css' in rr.data, str(rr.status_code))

print(f'\n{sum(res)}/{len(res)} vérifications réussies')
