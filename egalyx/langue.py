"""
egalyx/langue.py — bascule français / anglais fiable sur toutes les pages.

Avant : 5 « context processors » et 4 systèmes de traduction concurrents, une traduction par
morceaux qui remplaçait une partie de phrase (« Risques critiques » → « Risks critiques »),
une langue gardée dans l'adresse (?lang=en) et seuls ~60 gabarits sur 400 qui appelaient t().
De plus, un ancien script avait remplacé dans 158 gabarits des textes français par de l'anglais :
en français, l'interface affichait des morceaux d'anglais.

Maintenant :
  - une seule langue courante : session, puis cookie (1 an), puis langue de l'organisation, puis « fr » ;
  - /langue/<fr|en> l'enregistre et revient sur la même page, sans paramètre dans l'adresse ;
  - un seul dictionnaire (egalyx/traductions/*.tsv), complété par l'ancien CSV s'il existe ;
  - traduction exacte uniquement (jamais de remplacement partiel), insensible aux espaces, à la
    ponctuation finale, à la numérotation et à la casse ; modèles pour les messages variables
    (« 3 risque(s) importé(s) ») ;
  - toute page HTML est traduite à la sortie (textes et attributs visibles), y compris les textes
    écrits en dur dans les gabarits, les messages flash et l'attribut lang ;
  - le texte ajouté par JavaScript (fenêtres, alertes, confirmations, tableaux chargés en AJAX)
    est traduit dans le navigateur avec le même dictionnaire ;
  - en français, les restes d'anglais laissés par l'ancien script sont remis en français.
Un élément marqué translate="no" (ou classe notranslate) n'est jamais traduit.
"""
import csv
import hashlib
import json
import os
import re
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

from flask import Blueprint, Response, g, make_response, redirect, request, session, url_for
from markupsafe import Markup

LANGUES = ('fr', 'en')
DEFAUT = 'fr'
COOKIE = 'lang'
DOSSIER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'traductions')

bp = Blueprint('langue', __name__)


# ----------------------------------------------------------------------
# Langue courante
# ----------------------------------------------------------------------

def _avant_fin_body(html, ajout):
    """Insère avant le DERNIER </body> : le premier peut se trouver dans une chaîne JavaScript
    (fenêtre d'impression…), et y insérer un <script> casse le script de la page."""
    i = html.rfind('</body>')
    return html if i < 0 else html[:i] + ajout + html[i:]

def _valide(code):
    return code if code in LANGUES else None


def langue_courante():
    try:
        if getattr(g, 'egalyx_langue', None):
            return g.egalyx_langue
    except RuntimeError:
        return DEFAUT
    code = _valide(request.args.get('lang'))
    if code:
        session['lang'] = code
    code = code or _valide(session.get('lang')) or _valide(request.cookies.get(COOKIE))
    if not code:
        try:
            from flask_login import current_user
            client = getattr(current_user, 'client', None) if current_user.is_authenticated else None
            code = _valide(getattr(client, 'langue', None))
        except Exception:
            code = None
    g.egalyx_langue = code or DEFAUT
    return g.egalyx_langue


def _avant_requete():
    g.egalyx_langue = None
    g.current_lang = langue_courante()          # variable lue par l'ancien code (filtres, formats de date)


# ----------------------------------------------------------------------
# Dictionnaires
# ----------------------------------------------------------------------
_DICO = {'en': {}, 'fr': {}}      # cible → {source normalisée: traduction}
_BAS = {'en': {}, 'fr': {}}       # même chose, clé en minuscules
_MODELES = {'en': [], 'fr': []}   # cible → [(regex, gabarit)]
_VERSION = {'valeur': ''}

ESPACES = re.compile(r'\s+')
# préfixe (puces, numéros, symboles, emojis) / cœur / suffixe (ponctuation finale)
DECOUPE = re.compile(r'^([^A-Za-zÀ-ÿ«"\'(¿¡]*)(.*?)((?:\s*:?\s*\(?\s*\d[\d\s/%.,]*\)?)?[\s:!?.…*)»" \-–—·]*)$', re.S)
DECOUPE_SIMPLE = re.compile(r'^([^A-Za-zÀ-ÿ«"\'(¿¡]*)(.*?)([\s:!?.…*)»" ]*)$', re.S)


def cle(texte):
    return ESPACES.sub(' ', texte.replace('’', "'").replace(' ', ' ')).strip()


def _ajouter(cible, source, traduction):
    source, traduction = cle(source), traduction.strip()
    if not source or not traduction or source == traduction:
        return
    if '{}' in source:
        # Une partie variable = une valeur (nombre, nom, référence) : un seul « mot », sauf entre
        # guillemets. Sinon « {} sur {} » avalerait des phrases entières (« visible sur le blog »).
        morceaux = source.split('{}')
        motif = '^'
        for i, m in enumerate(morceaux):
            motif += re.escape(m)
            if i < len(morceaux) - 1:
                entre_guillemets = m[-1:] in '"\'«“‘' and m[-1:] != ''
                motif += '([^"«»“”]{1,120}?)' if entre_guillemets else '(\\S{1,60}?)'
        if len(re.sub(r'[^A-Za-zÀ-ÿ]', '', source.replace('{}', ''))) < 4:
            return                                    # trop peu de texte fixe pour être sûr
        _MODELES[cible].append((re.compile(motif + '$'), traduction))
        return
    _DICO[cible].setdefault(source, traduction)
    _BAS[cible].setdefault(source.lower(), traduction)     # titres en capitales, phrases en minuscules


def charger(dossier=DOSSIER, ancien_csv=None):
    """Charge fr_en*.tsv (français → anglais). Chaque ligne : « source<TAB>traduction ».
    Les lignes du fichier anglais_restant.tsv (anglais laissé dans les gabarits → français)
    servent dans les deux sens : en français on remet le texte français, en anglais on garde
    l'anglais et le texte français éventuel est traduit."""
    _DICO['en'].clear(); _DICO['fr'].clear(); _BAS['en'].clear(); _BAS['fr'].clear(); _MODELES['en'].clear(); _MODELES['fr'].clear()
    empreinte = hashlib.sha1()
    if os.path.isdir(dossier):
        # fr_en d'abord (référence), puis compléments, puis les restes d'anglais
        for nom in sorted(os.listdir(dossier), key=lambda n: (n.startswith('anglais_restant'), n)):
            if not nom.endswith('.tsv'):
                continue
            chemin = os.path.join(dossier, nom)
            with open(chemin, encoding='utf-8') as f:
                contenu = f.read()
            empreinte.update(contenu.encode())
            for ligne in contenu.splitlines():
                if not ligne.strip() or ligne.startswith('#') or '\t' not in ligne:
                    continue
                a, b = ligne.split('\t', 1)
                if nom.startswith('anglais_restant'):
                    _ajouter('fr', a, b)          # anglais → français
                    _ajouter('en', b, a)          # français → anglais
                else:
                    _ajouter('en', a, b)
    # Ancien fichier translations/to_translate.csv (3 000 entrées) : en complément seulement
    if ancien_csv and os.path.exists(ancien_csv):
        try:
            with open(ancien_csv, encoding='utf-8') as f:
                premiere = f.readline(); f.seek(0)
                for row in csv.reader(f, delimiter=';' if premiere.count(';') > premiere.count(',') else ','):
                    if len(row) >= 2 and len(cle(row[0])) > 3:
                        _ajouter('en', row[0].strip().strip('"'), row[1].strip().strip('"'))
        except Exception as e:
            print(f"⚠️ Langue : ancien CSV ignoré ({e})")
    for cible in _MODELES:
        _MODELES[cible].sort(key=lambda m: -len(m[0].pattern))
    _VERSION['valeur'] = empreinte.hexdigest()[:10]
    return len(_DICO['en']), len(_DICO['fr'])


def _depuis_dico(c, cible):
    d = _DICO[cible]
    if c in d:
        return d[c]
    bas = c.lower()
    if bas in _BAS[cible]:
        t = _BAS[cible][bas]
        if c.isupper() and len(c) > 3:
            return t.upper()
        if c[:1].isupper() and t[:1].islower():
            return t[:1].upper() + t[1:]
        if c[:1].islower() and t[:1].isupper() and not t[:2].isupper():
            return t[:1].lower() + t[1:]
        return t
    for motif, gabarit in _MODELES[cible]:
        m = motif.match(c)
        if m:
            vals = iter(m.groups())
            return re.sub(r'\{\}', lambda _x: next(vals, ''), gabarit)
    return None


def traduire(texte, cible=None):
    """Traduction exacte d'un texte d'interface ; renvoie le texte inchangé s'il est inconnu."""
    if texte is None:
        return ''
    cible = cible or langue_courante()
    s = str(texte)
    if not s.strip():
        return s
    c = cle(s)
    t = _depuis_dico(c, cible)
    for decoupe in (DECOUPE_SIMPLE, DECOUPE):
        if t is not None:
            break
        m = decoupe.match(c)
        if m and m.group(2) and (m.group(1) or m.group(3)):
            coeur = _depuis_dico(m.group(2), cible)
            if coeur is not None:
                suffixe = m.group(3)
                if cible == 'en':                       # « Total : » → « Total: »
                    suffixe = re.sub(r'^[\s\u00a0]+(?=[:!?;])', '', suffixe)
                elif cible == 'fr':
                    suffixe = re.sub(r'^(?=[:!?;])', '\u00a0', suffixe)
                t = m.group(1) + coeur + suffixe
    if t is None:
        return s
    # garder les espaces de début et de fin d'origine (mise en page HTML)
    debut = s[:len(s) - len(s.lstrip())]
    fin = s[len(s.rstrip()):]
    return debut + t + fin


def t(texte, *args, **kwargs):
    r = traduire(texte)
    if args or kwargs:
        try:
            r = r % (args or kwargs)
        except Exception:
            pass
    return Markup(r) if isinstance(texte, Markup) else r


# ----------------------------------------------------------------------
# Traduction des pages HTML à la sortie
# ----------------------------------------------------------------------
JETONS = re.compile(r'(<!--.*?-->|<[^>]+>)', re.S)
BLOCS_IGNORES = ('script', 'style', 'textarea', 'pre', 'code', 'svg')
ATTRIBUTS = re.compile(r'''(\s(?:placeholder|title|aria-label|alt|data-bs-original-title|data-title|data-confirm|label)\s*=\s*)(["'])(.*?)\2''', re.S | re.I)
VALEUR_BOUTON = re.compile(r'''(\svalue\s*=\s*)(["'])(.*?)\2''', re.S | re.I)
NOM_BALISE = re.compile(r'<\s*(/?)\s*([a-zA-Z0-9]+)')
LANG_HTML = re.compile(r'(<html\b[^>]*\blang=)(["\'])[a-z-]*\2', re.I)
ENTITES = {'&amp;': '&', '&#39;': "'", '&#x27;': "'", '&quot;': '"', '&nbsp;': ' ', '&rsquo;': '’',
           '&eacute;': 'é', '&egrave;': 'è', '&agrave;': 'à', '&ccedil;': 'ç', '&ecirc;': 'ê'}
ENTITE = re.compile('|'.join(map(re.escape, ENTITES)))


def _texte_html(brut, cible, attribut=False):
    if not brut.strip() or '{{' in brut:
        return brut
    clair = ENTITE.sub(lambda m: ENTITES[m.group(0)], brut) if '&' in brut else brut
    tr = traduire(clair, cible)
    if tr == clair:
        return brut
    tr = tr.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    if attribut:
        tr = tr.replace('"', '&quot;')
    return tr


def traduire_html(html, cible):
    sortie, ignore, sans_trad = [], [], []
    for morceau in JETONS.split(html):
        if not morceau:
            continue
        if morceau.startswith('<'):
            if morceau.startswith('<!--') or morceau.startswith('<!'):
                sortie.append(morceau)
                continue
            m = NOM_BALISE.match(morceau)
            if m:
                fermante, nom = m.group(1) == '/', m.group(2).lower()
                auto = morceau.endswith('/>') or nom in ('br', 'hr', 'img', 'input', 'meta', 'link', 'wbr', 'source', 'col', 'area')
                if nom in BLOCS_IGNORES:
                    if fermante:
                        if ignore and ignore[-1] == nom:
                            ignore.pop()
                    elif not auto:
                        ignore.append(nom)
                elif not fermante and not auto and ('translate="no"' in morceau or 'notranslate' in morceau):
                    sans_trad.append([nom, 0])
                elif sans_trad and nom == sans_trad[-1][0] and not auto:
                    sans_trad[-1][1] += -1 if fermante else 1
                    if sans_trad[-1][1] < 0:
                        sans_trad.pop()
                if not fermante and not ignore and not sans_trad:
                    if nom == 'html':
                        morceau = LANG_HTML.sub(lambda x: f'{x.group(1)}{x.group(2)}{cible}{x.group(2)}', morceau)
                    morceau = ATTRIBUTS.sub(lambda x: x.group(1) + x.group(2) + _texte_html(x.group(3), cible, True) + x.group(2), morceau)
                    if nom in ('input', 'button') and re.search(r'type\s*=\s*["\']?(submit|button|reset)', morceau, re.I):
                        morceau = VALEUR_BOUTON.sub(lambda x: x.group(1) + x.group(2) + _texte_html(x.group(3), cible, True) + x.group(2), morceau)
            sortie.append(morceau)
        elif ignore or sans_trad:
            sortie.append(morceau)
        else:
            sortie.append(_texte_html(morceau, cible))
    return ''.join(sortie)


def _apres_requete(reponse):
    try:
        cible = langue_courante()
    except Exception:
        return reponse
    if reponse.direct_passthrough or reponse.is_streamed or reponse.status_code in (204, 304):
        return reponse
    if reponse.mimetype == 'text/html' and not request.path.startswith('/static/'):
        if cible == 'fr' and not _DICO['fr'] and not _MODELES['fr']:
            return reponse
        try:
            html = reponse.get_data(as_text=True)
            nouveau = traduire_html(html, cible)
            if cible != 'fr' or nouveau != html:
                nouveau = _avant_fin_body(nouveau, _script_navigateur(cible))
            reponse.set_data(nouveau)
        except Exception as e:
            print(f"⚠️ Langue : page non traduite ({e})")
    elif reponse.mimetype == 'application/json' and cible != 'fr':
        try:
            donnees = reponse.get_json(silent=True)
            if isinstance(donnees, dict) and any(k in donnees for k in ('message', 'error', 'erreur')):
                for k in ('message', 'error', 'erreur'):
                    if isinstance(donnees.get(k), str):
                        donnees[k] = traduire(donnees[k], cible)
                reponse.set_data(json.dumps(donnees, ensure_ascii=False, default=str))
        except Exception:
            pass
    return reponse


def _script_navigateur(cible):
    try:
        src = url_for('langue.dictionnaire', cible=cible, v=_VERSION['valeur'])
    except Exception:
        return ''
    return f'<script src="{src}" defer></script>'


# ----------------------------------------------------------------------
# Côté navigateur : même dictionnaire pour le texte ajouté par JavaScript
# ----------------------------------------------------------------------
JS_TRADUCTEUR = r"""
(function () {
  var D = window.EGALYX_DICO || {}, B = {}, M = (window.EGALYX_MODELES || []).map(function (m) { return [new RegExp(m[0]), m[1]]; });
  Object.keys(D).forEach(function (k) { var b = k.toLowerCase(); if (!(b in B)) B[b] = D[k]; });
  function cle(s) { return s.replace(/’/g, "'").replace(/ /g, ' ').replace(/\s+/g, ' ').trim(); }
  function dico(c) {
    if (Object.prototype.hasOwnProperty.call(D, c)) return D[c];
    var b = c.toLowerCase();
    if (Object.prototype.hasOwnProperty.call(B, b)) { var t = B[b];
      if (c.length > 3 && c === c.toUpperCase()) return t.toUpperCase();
      if (c[0] && c[0] !== c[0].toLowerCase()) return t[0].toUpperCase() + t.slice(1);
      if (c[0] && c[0] !== c[0].toUpperCase() && t[1] && t[1] === t[1].toLowerCase()) return t[0].toLowerCase() + t.slice(1);
      return t; }
    for (var i = 0; i < M.length; i++) { var m = c.match(M[i][0]); if (m) { var k = 1; return M[i][1].replace(/\{\}/g, function () { return m[k++] || ''; }); } }
    return null;
  }
  function tr(s) {
    if (!s || !/[A-Za-zÀ-ÿ]/.test(s)) return s;
    var c = cle(s), t = dico(c);
    if (t === null) {
      [/^([^A-Za-zÀ-ÿ«"'(]*)(.*?)([\s:!?.…*)»" ]*)$/, /^([^A-Za-zÀ-ÿ«"'(]*)(.*?)((?:\s*:?\s*\(?\s*\d[\d\s\/%.,]*\)?)?[\s:!?.…*)»" \-–—·]*)$/].forEach(function (re) { if (t !== null) return; var m = c.match(re);
      if (m && m[2] && (m[1] || m[3])) { var x = dico(m[2]); if (x !== null) t = m[1] + x + (CIBLE === 'en' ? m[3].replace(/^\s+(?=[:!?;])/, '') : m[3]); } });
    }
    if (t === null) return s;
    var d = s.match(/^\s*/)[0], f = s.match(/\s*$/)[0];
    return d + t + f;
  }
  window.egalyxT = tr;
  var IGN = /^(SCRIPT|STYLE|TEXTAREA|PRE|CODE|INPUT)$/, ATTR = ['placeholder', 'title', 'aria-label', 'alt', 'data-bs-original-title'];
  function bloque(n) { for (var e = n; e && e.nodeType === 1; e = e.parentElement) { if (IGN.test(e.tagName) || e.getAttribute('translate') === 'no' || (e.classList && e.classList.contains('notranslate'))) return true; } return false; }
  function noeud(n) {
    if (n.nodeType === 3) { if (!bloque(n.parentElement)) { var v = tr(n.nodeValue); if (v !== n.nodeValue) n.nodeValue = v; } return; }
    if (n.nodeType !== 1 || bloque(n)) return;
    ATTR.forEach(function (a) { var v = n.getAttribute(a); if (v) { var w = tr(v); if (w !== v) n.setAttribute(a, w); } });
    if ((n.tagName === 'INPUT' || n.tagName === 'BUTTON') && /^(submit|button|reset)$/i.test(n.type) && n.value) { var w = tr(n.value); if (w !== n.value) n.value = w; }
    var w2 = document.createTreeWalker(n, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT), x;
    while ((x = w2.nextNode())) { if (x.nodeType === 3) { if (!bloque(x.parentElement)) { var v2 = tr(x.nodeValue); if (v2 !== x.nodeValue) x.nodeValue = v2; } } else if (!bloque(x)) { ATTR.forEach(function (a) { var v = x.getAttribute(a); if (v) { var w = tr(v); if (w !== v) x.setAttribute(a, w); } }); } }
  }
  ['alert', 'confirm', 'prompt'].forEach(function (f) { var o = window[f]; if (o) window[f] = function (msg) { var a = Array.prototype.slice.call(arguments); if (typeof msg === 'string') a[0] = msg.split('\n').map(tr).join('\n'); return o.apply(window, a); }; });
  function demarrer() {
    noeud(document.body);
    new MutationObserver(function (ms) { ms.forEach(function (m) {
      if (m.type === 'characterData') { var v = tr(m.target.nodeValue); if (v !== m.target.nodeValue && !bloque(m.target.parentElement)) m.target.nodeValue = v; }
      else m.addedNodes.forEach(noeud);
    }); }).observe(document.body, { childList: true, subtree: true, characterData: true });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', demarrer); else demarrer();
})();
"""


@bp.route('/langue/dictionnaire-<cible>.js')
def dictionnaire(cible):
    if cible not in LANGUES:
        return Response('', mimetype='application/javascript', status=404)
    d = {k: v for k, v in _DICO[cible].items() if len(k) <= 300}
    modeles = [[m.pattern, gab] for m, gab in _MODELES[cible]]
    corps = ('window.EGALYX_DICO=' + json.dumps(d, ensure_ascii=False, separators=(',', ':')) + ';'
             'window.EGALYX_MODELES=' + json.dumps(modeles, ensure_ascii=False) + ';'
             'var CIBLE=' + json.dumps(cible) + ';' + JS_TRADUCTEUR)
    r = Response(corps, mimetype='application/javascript')
    r.headers['Cache-Control'] = 'public, max-age=31536000, immutable' if request.args.get('v') else 'no-cache'
    return r


def _retour_sur(cible_url):
    """Adresse de retour : même site uniquement, sans paramètre lang."""
    if not cible_url:
        return None
    p = urlsplit(cible_url)
    if p.netloc and p.netloc != request.host:
        return None
    if not p.path.startswith('/') or p.path.startswith('//'):
        return None
    requete = urlencode([(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True) if k != 'lang'])
    return urlunsplit(('', '', p.path, requete, p.fragment))


@bp.route('/langue/<code>')
def changer(code):
    code = _valide(code) or DEFAUT
    session['lang'] = code
    g.egalyx_langue = code
    retour = _retour_sur(request.args.get('suivant')) or _retour_sur(request.referrer) or '/'
    reponse = make_response(redirect(retour))
    reponse.set_cookie(COOKIE, code, max_age=365 * 24 * 3600, samesite='Lax', secure=request.is_secure, httponly=False)
    return reponse


def _contexte():
    code = langue_courante()
    return {'t': t, 'translate': t, '_': t, 'current_lang': code, 'lang': code, 'get_locale': lambda: code,
            'available_langs': {'fr': {'name': 'Français', 'flag': 'fr', 'dir': 'ltr'}, 'en': {'name': 'English', 'flag': 'gb', 'dir': 'ltr'}},
            'is_english': code == 'en', 'is_french': code == 'fr', 'egalyx_langue': code}


def enregistrer(app):
    app.register_blueprint(bp)
    ancien = os.path.join(app.root_path, 'translations', 'to_translate.csv')
    nb_en, nb_fr = charger(ancien_csv=ancien)
    print(f"✅ Langue : {nb_en} traductions vers l'anglais, {nb_fr} corrections vers le français")
    # Retire les anciens choix de langue (ils réécrivaient la session à chaque page et l'affichaient dans les journaux)
    avant = app.before_request_funcs.setdefault(None, [])
    avant[:] = [f for f in avant if not (getattr(f, '__name__', '') == 'handle_language'
                                         or (getattr(f, '__name__', '') == 'before_request'
                                             and 'current_lang' in getattr(getattr(f, '__code__', None), 'co_names', ())))]
    avant.insert(0, _avant_requete)
    app.after_request(_apres_requete)
    app.context_processor(_contexte)            # enregistré en dernier : remplace les 5 anciens
    app.jinja_env.globals.update(t=t, translate=t, _=t)
    app.jinja_env.filters['t'] = t
    app.jinja_env.filters['translate'] = lambda texte, lang=None: traduire(texte, lang)
    # L'ancien système (translation_system.translate) est utilisé par du code Python : même moteur
    import sys
    module_app = sys.modules.get(app.import_name)
    ancien_sys = getattr(module_app, 'translation_system', None)
    if ancien_sys is not None:
        ancien_sys.translate = lambda texte, lang='en': traduire(texte, lang)
