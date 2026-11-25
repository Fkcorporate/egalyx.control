"""
egalyx/cartouche_qualite.py — cartouche qualité en haut de chaque page du rapport d'audit.

Exigence de maîtrise documentaire (ISO 9001…) : chaque page porte le cartouche du système qualité du client,
reproduit à l'identique de celui qu'il utilise déjà, par exemple :
  | logo | RAPPORT D'AUDIT INTERNE | CODE              | DATE      | VERSION | PAGE   |
  |      |                         | ENR 003/ PRG-AUDI | 1/03/2023 | 00      | 2 de 5 |

Paramétrage (Identité de l'organisation > Cartouche qualité), par l'administrateur de l'organisation :
  - titre du document (jusqu'à 3 lignes) ;
  - jusqu'à 5 cases libres « intitulé / valeur » (CODE, DATE, VERSION, RÉF., INDICE, ÉMETTEUR…) ; une valeur
    peut reprendre l'audit : {reference}, {titre_audit}, {date_rapport}, {annee} ;
  - case PAGE : intitulé et format (« 2 de 5 », « 2 sur 5 », « 2/5 », « Page 2 sur 5 ») ou pas de case PAGE ;
  - logo de l'organisation dans la première case, ou pas de case logo ;
  - police (Arial ou Times), tailles, titre et intitulés en gras ou non, épaisseur et couleur des traits,
    largeur des cases logo et titre, cartouche aussi sur la page de garde ou non.

Le cartouche est dessiné directement par chaque format (pas de « papier » superposé, pas de réduction du rapport) :
  - PDF élégant (WeasyPrint) : en-tête de page répété (Cartouche.html / Cartouche.css), numéro de page natif ;
  - export PDF et rapport complet PDF (ReportLab) : dessiné sur chaque page (document_pdf()) ;
  - rapports Word : en-tête de chaque page, champs PAGE / NUMPAGES mis à jour par Word (cartouche_word()).
Quand il est activé, il remplace le papier à en-tête PDF déposé pour le rapport d'audit, et la numérotation
habituelle des pages (la case PAGE en tient lieu).

Stockage : ClientConfiguration.preferences['cartouche_qualite'] (base de données : survit aux redéploiements).
"""
import base64
import io
import logging
import re
from datetime import datetime
from xml.sax.saxutils import escape

from flask import Blueprint, abort, flash, g, has_request_context, redirect, request, send_file, url_for
from markupsafe import Markup

from egalyx.commun import client_id_courant, client_requis, est_super_admin, journaliser

journal = logging.getLogger('egalyx.cartouche_qualite')
bp = Blueprint('cartouche_qualite', __name__, url_prefix='/organisation/cartouche-qualite')

CLE = 'cartouche_qualite'
MAX_COLONNES = 5
FORMATS_PAGE = {
    'n_de_N': '2 de 5',
    'n_sur_N': '2 sur 5',
    'n/N': '2/5',
    'page_n_sur_N': 'Page 2 sur 5',
    'aucune': 'Pas de case PAGE',
}
POLICES = {'arial': ('Arial', 'Helvetica'), 'times': ('Times New Roman', 'Times-Roman')}
TRAITS = {'fin': 0.5, 'moyen': 0.9, 'epais': 1.4}
COLONNES_DEFAUT = [{'libelle': 'CODE', 'valeur': ''}, {'libelle': 'DATE', 'valeur': ''}, {'libelle': 'VERSION', 'valeur': ''}]
DEFAUT = {
    'actif': False, 'titre': "RAPPORT D'AUDIT INTERNE", 'colonnes': COLONNES_DEFAUT,
    'page_libelle': 'PAGE', 'page_format': 'n_de_N', 'logo': True, 'police': 'arial',
    'taille': 8.5, 'taille_titre': 9.5, 'titre_gras': False, 'libelles_gras': False,
    'trait': 'fin', 'couleur_trait': '#000000', 'premiere_page': True,
    'largeur_logo': 13, 'largeur': 'page',
}
LARGEURS = {'page': 'Largeur de la page (185 mm, comme un en-tête Word)', 'texte': 'Largeur du texte du rapport'}
LONGUEURS = {'titre': 150, 'libelle': 24, 'valeur': 60, 'page_libelle': 24}
CHAMPS = {'reference': "référence de l'audit", 'titre_audit': "titre de l'audit",
          'date_rapport': 'date du rapport', 'annee': 'année'}
MM = 72 / 25.4


def _m():
    import models
    return models


# ================================================================ réglage
def _nettoyer(v, n):
    return ' '.join(str(v or '').split())[:n]


def _nombre(v, defaut, mini, maxi):
    try:
        return min(max(float(str(v).replace(',', '.')), mini), maxi)
    except (TypeError, ValueError):
        return defaut


def normaliser(brut):
    """Réglage complet et sûr à partir de ce qui est stocké (y compris l'ancien format code / date / version)."""
    r = dict(DEFAUT)
    brut = dict(brut or {})
    if 'colonnes' not in brut and any(k in brut for k in ('code', 'date', 'version')):     # ancien réglage
        brut['colonnes'] = [{'libelle': 'CODE', 'valeur': brut.get('code', '')},
                            {'libelle': 'DATE', 'valeur': brut.get('date', '')},
                            {'libelle': 'VERSION', 'valeur': brut.get('version', '')}]
    r['actif'] = bool(brut.get('actif', False))
    titre = '\n'.join(l.strip() for l in str(brut.get('titre') or '').replace('\r', '').split('\n') if l.strip())
    r['titre'] = '\n'.join(titre.split('\n')[:3])[:LONGUEURS['titre']] or DEFAUT['titre']
    cols = []
    for c in (brut.get('colonnes') if isinstance(brut.get('colonnes'), list) else COLONNES_DEFAUT):
        if not isinstance(c, dict):
            continue
        lib = _nettoyer(c.get('libelle'), LONGUEURS['libelle'])
        val = _nettoyer(c.get('valeur'), LONGUEURS['valeur'])
        if lib or val:
            cols.append({'libelle': lib, 'valeur': val})
    r['colonnes'] = cols[:MAX_COLONNES]
    r['page_libelle'] = _nettoyer(brut.get('page_libelle', DEFAUT['page_libelle']), LONGUEURS['page_libelle'])
    r['page_format'] = brut.get('page_format') if brut.get('page_format') in FORMATS_PAGE else DEFAUT['page_format']
    r['logo'] = brut.get('logo', True) is not False
    r['police'] = brut.get('police') if brut.get('police') in POLICES else DEFAUT['police']
    r['taille'] = _nombre(brut.get('taille'), DEFAUT['taille'], 7, 11)
    r['taille_titre'] = _nombre(brut.get('taille_titre'), DEFAUT['taille_titre'], 7, 14)
    r['titre_gras'] = bool(brut.get('titre_gras', DEFAUT['titre_gras']))
    r['libelles_gras'] = bool(brut.get('libelles_gras', DEFAUT['libelles_gras']))
    r['trait'] = brut.get('trait') if brut.get('trait') in TRAITS else DEFAUT['trait']
    coul = str(brut.get('couleur_trait') or '')
    r['couleur_trait'] = coul.upper() if re.fullmatch(r'#[0-9A-Fa-f]{6}', coul) else DEFAUT['couleur_trait']
    r['premiere_page'] = brut.get('premiere_page', True) is not False
    r['largeur_logo'] = _nombre(brut.get('largeur_logo'), DEFAUT['largeur_logo'], 8, 25)
    r['largeur'] = brut.get('largeur') if brut.get('largeur') in LARGEURS else DEFAUT['largeur']
    return r


def lire(cid):
    if not cid:
        return normaliser({})
    cache = g.setdefault('_eg_cartouche', {}) if has_request_context() else {}
    if cid in cache:
        return cache[cid]
    brut = {}
    try:
        conf = _m().ClientConfiguration.query.filter_by(client_id=cid).first()
        brut = ((conf.preferences or {}).get(CLE) if conf else None) or {}
    except Exception as e:  # noqa: BLE001
        journal.info('Cartouche illisible pour %s : %s', cid, e)
    r = normaliser(brut)
    cache[cid] = r
    return r


def actif(cid):
    r = lire(cid)
    return bool(r.get('actif')) and bool((r.get('titre') or '').strip())


def depuis_formulaire(form):
    """Réglage à partir du formulaire (cases libres : libelle_1..5 / valeur_1..5)."""
    brut = {
        'actif': form.get('actif') == '1', 'titre': form.get('titre') or '',
        'colonnes': [{'libelle': form.get(f'libelle_{i}', ''), 'valeur': form.get(f'valeur_{i}', '')}
                     for i in range(1, MAX_COLONNES + 1)],
        'page_libelle': form.get('page_libelle', 'PAGE'), 'page_format': form.get('page_format'),
        'logo': form.get('logo') == '1', 'police': form.get('police'), 'taille': form.get('taille'),
        'taille_titre': form.get('taille_titre'), 'titre_gras': form.get('titre_gras') == '1',
        'libelles_gras': form.get('libelles_gras') == '1', 'trait': form.get('trait'),
        'couleur_trait': form.get('couleur_trait'), 'premiere_page': form.get('premiere_page') == '1',
        'largeur_logo': form.get('largeur_logo'), 'largeur': form.get('largeur'),
    }
    # anciens champs (formulaire précédent, scripts) : code / date / version
    if not any(form.get(f'libelle_{i}') for i in range(1, MAX_COLONNES + 1)) and any(form.get(k) for k in ('code', 'date', 'version')):
        brut['colonnes'] = [{'libelle': 'CODE', 'valeur': form.get('code', '')}, {'libelle': 'DATE', 'valeur': form.get('date', '')},
                            {'libelle': 'VERSION', 'valeur': form.get('version', '')}]
        brut['premiere_page'] = True
    return normaliser(brut)


def enregistrer_reglage(cid, form):
    m = _m()
    r = depuis_formulaire(form)
    conf = m.ClientConfiguration.query.filter_by(client_id=cid).first()
    if conf is None:
        conf = m.ClientConfiguration(client_id=cid, couleurs={}, preferences={})
        m.db.session.add(conf)
    prefs = dict(conf.preferences or {})
    prefs[CLE] = r
    conf.preferences = prefs
    if has_request_context():
        g.pop('_eg_cartouche', None)
    return r


def _logo(cid):
    try:
        from egalyx.identite import logo_data_uri
        uri = logo_data_uri(cid) or ''
        mt = re.match(r'data:image/[a-z+]+;base64,(.+)$', uri, re.S)
        return base64.b64decode(mt.group(1)) if mt else None
    except Exception:  # noqa: BLE001
        return None


def _logo_uri(cid):
    try:
        from egalyx.identite import logo_data_uri
        return logo_data_uri(cid)
    except Exception:  # noqa: BLE001
        return None


# ================================================================ contenu (champs de l'audit, largeurs)
def valeurs_audit(audit=None):
    v = {'reference': '', 'titre_audit': '', 'date_rapport': datetime.now().strftime('%d/%m/%Y'), 'annee': str(datetime.now().year)}
    if audit is not None:
        v['reference'] = audit.reference or ''
        v['titre_audit'] = audit.titre or ''
        d = getattr(audit, 'rapport_definitif_le', None)
        if d:
            v['date_rapport'] = d.strftime('%d/%m/%Y')
            v['annee'] = str(d.year)
    return v


def remplir(texte, valeurs):
    return re.sub(r'\{([a-z_]+)\}', lambda m: str(valeurs[m.group(1)]) if m.group(1) in valeurs else m.group(0), texte or '')


def contenu(r, audit=None):
    """Cases à dessiner : titre, [(intitulé, valeur)], case page oui/non — champs de l'audit remplis."""
    v = valeurs_audit(audit)
    cols = [(c['libelle'], remplir(c['valeur'], v)) for c in r['colonnes']]
    return {'titre': remplir(r['titre'], v), 'colonnes': cols, 'page': r['page_format'] != 'aucune'}


def _largeur_texte(texte, r, taille, gras=False):
    """Largeur d'un texte (points) avec la police du cartouche (métriques Helvetica / Times de ReportLab)."""
    try:
        from reportlab.pdfbase.pdfmetrics import stringWidth
        base, b = _polices_rl(r)
        return max((stringWidth(l, b if gras else base, taille) for l in (texte or '').split('\n')), default=0)
    except Exception:  # noqa: BLE001
        return len(texte or '') * taille * 0.55


def largeurs(r, avec_logo, largeur_pt=None, audit=None):
    """Largeurs relatives (%) : logo, titre, [cases libres + page], calculées sur le contenu réel :
    chaque case reçoit la place de son texte, le titre ce qu'il lui faut, le reste est réparti."""
    largeur_pt = largeur_pt or largeur_cartouche_mm(r) * MM
    co = contenu(r, audit)
    lg = r['largeur_logo'] if avec_logo else 0
    cases = [(lib, val) for lib, val in co['colonnes']]
    if co['page']:
        exemple = texte_page(r['page_format'], 88, 88)
        cases.append((r['page_libelle'], exemple))
    if not cases:
        return lg, 100 - lg, []
    # + 8 % : les polices de Word / LibreOffice (Arial, Liberation…) sont un peu plus larges que les métriques PDF
    besoins = [max(_largeur_texte(lib, r, r['taille'], r['libelles_gras']), _largeur_texte(val, r, r['taille'], True), 18) * 1.08 + 12
               for lib, val in cases]
    besoin_titre = _largeur_texte(co['titre'], r, r['taille_titre'], r['titre_gras']) + 18
    dispo = largeur_pt * (100 - lg) / 100
    total = sum(besoins) + besoin_titre
    if total <= dispo:
        surplus = dispo - total               # réparti : moitié au titre, moitié aux cases
        titre = besoin_titre + surplus / 2
        besoins = [b + surplus / 2 / len(besoins) for b in besoins]
    else:                                    # manque de place : tout réduit dans la même proportion
        k = dispo / total
        titre = besoin_titre * k
        besoins = [b * k for b in besoins]
    return lg, titre / largeur_pt * 100, [b / largeur_pt * 100 for b in besoins]


def largeur_cartouche_mm(r, largeur_texte_mm=180):
    return 185 if r.get('largeur') == 'page' else largeur_texte_mm


def texte_page(fmt, n, total):
    return {'n_de_N': f'{n} de {total}', 'n_sur_N': f'{n} sur {total}', 'n/N': f'{n}/{total}',
            'page_n_sur_N': f'Page {n} sur {total}'}.get(fmt, '')


def hauteur_mm(r):
    """Hauteur du cartouche (mm), pour réserver la place en haut de page."""
    lignes = max(1, len(r['titre'].split('\n')))
    titre = lignes * r['taille_titre'] * 1.3 / MM + 4
    cases = (r['taille'] * 1.35 / MM + 2.6) + (r['taille'] * 1.35 / MM + 6) if (r['colonnes'] or r['page_format'] != 'aucune') else 0
    return round(max(titre, cases, 15 if r['logo'] else 0), 1)


# ================================================================ HTML (PDF élégant WeasyPrint, aperçu à l'écran)
def html(r, audit=None, cid=None, classe='eg-cartouche', logo_uri=None, largeur_texte_mm=None):
    """Tableau du cartouche. La case PAGE contient des compteurs CSS (remplis par WeasyPrint), ou « 1 de 5 » à l'écran.
    largeur_texte_mm : largeur du texte de la page (PDF) ; le cartouche « largeur de la page » déborde alors
    également à gauche et à droite. Sans elle (écran) : 100 % du conteneur."""
    if logo_uri is None and r['logo'] and cid:
        logo_uri = _logo_uri(cid)
    avec_logo = r['logo']
    c = contenu(r, audit)
    lmm = largeur_cartouche_mm(r, largeur_texte_mm or 180)
    lg, lt, lc = largeurs(r, avec_logo, lmm * MM, audit)
    if largeur_texte_mm:
        dimension = f'width:{lmm}mm;margin-left:{-(lmm - largeur_texte_mm) / 2:.2f}mm;'
    else:
        dimension = 'width:100%;'
    police = POLICES[r['police']][0]
    repli = 'Arial, Helvetica, Liberation Sans, sans-serif' if r['police'] == 'arial' else 'Times, Liberation Serif, serif'
    trait = f"{TRAITS[r['trait']]}pt solid {r['couleur_trait']}"
    cell = f'border:{trait};text-align:center;vertical-align:middle;'
    gras_lib = 'font-weight:700;' if r['libelles_gras'] else 'font-weight:400;'
    n_cases = len(lc)
    rows = 2 if n_cases else 1
    t = [f'<table class="{classe}" style="{dimension}border-collapse:collapse;table-layout:fixed;font-family:\'{police}\',{repli};'
         f'font-size:{r["taille"]}pt;color:#000;line-height:1.25;background:#fff;letter-spacing:0;">', '<colgroup>']
    if avec_logo:
        t.append(f'<col style="width:{lg:.2f}%">')
    t.append(f'<col style="width:{lt:.2f}%">')
    for w in lc:
        t.append(f'<col style="width:{w:.2f}%">')
    t.append('</colgroup><tr>')
    if avec_logo:
        img = (f'<img src="{logo_uri}" alt="" style="max-width:100%;max-height:13mm;display:block;margin:0 auto;">'
               if logo_uri else '')
        t.append(f'<td rowspan="{rows}" style="{cell}padding:1mm;">{img}</td>')
    titre = '<br>'.join(escape(l) for l in c['titre'].split('\n'))
    t.append(f'<td rowspan="{rows}" style="{cell}padding:1.2mm 2mm;font-size:{r["taille_titre"]}pt;'
             f'{"font-weight:700;" if r["titre_gras"] else "font-weight:400;"}">{titre}</td>')
    for lib, _ in c['colonnes']:
        t.append(f'<td style="{cell}{gras_lib}padding:0.8mm 1mm;">{escape(lib)}</td>')
    if c['page']:
        t.append(f'<td style="{cell}{gras_lib}padding:0.8mm 1mm;">{escape(r["page_libelle"])}</td>')
    t.append('</tr>')
    if n_cases:
        t.append('<tr>')
        for _, val in c['colonnes']:
            t.append(f'<td style="{cell}padding:2.6mm 1mm;font-weight:400;">{escape(val)}</td>')
        if c['page']:
            fmt = r['page_format']
            avant = 'Page ' if fmt == 'page_n_sur_N' else ''
            milieu = {'n_de_N': ' de ', 'n_sur_N': ' sur ', 'n/N': '/', 'page_n_sur_N': ' sur '}[fmt]
            t.append(f'<td style="{cell}padding:2.6mm 1mm;font-weight:400;">{avant}<b class="cq-n">1</b>{milieu}<b class="cq-total">5</b></td>')
        t.append('</tr>')
    t.append('</table>')
    return Markup(''.join(t))


def css(r):
    """Règles de page (WeasyPrint) : cartouche en tête de chaque page, marge haute réservée, numéro de page natif.
    Remplace la mention et la numérotation habituelles du rapport (la case PAGE en tient lieu)."""
    haut = 9 + hauteur_mm(r) + 7      # mm : bord de page → cartouche → contenu
    boite = 'content: element(egcartouche); width: 100%; vertical-align: bottom; padding-bottom: 6mm;'
    premiere = boite if r['premiere_page'] else 'content: none;'
    numero = 'content: none;' if r['page_format'] != 'aucune' else ''
    return Markup(f"""
        .eg-cartouche-courant {{ position: running(egcartouche); }}
        .eg-cartouche .cq-n, .eg-cartouche .cq-total {{ font-size: 0; }}
        .eg-cartouche .cq-n::after {{ content: counter(page); font-size: {r['taille']}pt; }}
        .eg-cartouche .cq-total::after {{ content: counter(pages); font-size: {r['taille']}pt; }}
        @page {{ margin-top: {haut:.1f}mm;
                 @top-left {{ content: none; }} @top-right {{ content: none; }}
                 @top-center {{ {boite} }}
                 @bottom-right {{ {numero} }} @bottom-center {{ {numero} }} }}
        @page :first {{ margin-top: {haut if r['premiere_page'] else 22:.1f}mm;
                 @top-center {{ {premiere} }} }}
    """)


class Cartouche:
    """Pour les gabarits : {% set cq = cartouche_rapport(audit, marges_mm=22) %} puis cq.actif, cq.css (dans <style>),
    cq.html (après <body>). marges_mm : marges gauche et droite de la page du gabarit (A4)."""
    def __init__(self, cid, audit=None, marges_mm=22):
        self.marges_mm = marges_mm
        self.cid = cid
        self.r = lire(cid)
        self.actif = actif(cid)
        self.audit = audit

    @property
    def css(self):
        return css(self.r) if self.actif else Markup('')

    @property
    def html(self):
        if not self.actif:
            return Markup('')
        return (Markup('<div class="eg-cartouche-courant">')
                + html(self.r, self.audit, self.cid, largeur_texte_mm=210 - 2 * self.marges_mm) + Markup('</div>'))


def cartouche_rapport(audit=None, cid=None, marges_mm=22):
    cid = cid or (audit.client_id if audit is not None else client_id_courant())
    return Cartouche(cid, audit, marges_mm)


# ================================================================ PDF ReportLab (export PDF, rapport complet PDF)
def _polices_rl(r):
    base = POLICES[r['police']][1]
    return base, {'Helvetica': 'Helvetica-Bold', 'Times-Roman': 'Times-Bold'}[base]


def dessiner_rl(c, r, page, total, x, haut, largeur, logo=None, audit=None):
    """Dessine le cartouche sur un canevas ReportLab : coin haut-gauche (x, haut), largeur en points."""
    from reportlab.lib.colors import HexColor
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.utils import ImageReader
    from reportlab.platypus import Paragraph
    police, gras = _polices_rl(r)
    co = contenu(r, audit)
    avec_logo = r['logo']
    lg, lt, lc = largeurs(r, avec_logo, largeur, audit)
    ws = [largeur * w / 100 for w in (([lg] if avec_logo else []) + [lt] + lc)]
    h = hauteur_mm(r) * MM
    h_lib = r['taille'] * 1.35 + 2.6 * MM
    bas = haut - h
    xs = [x]
    for w in ws:
        xs.append(xs[-1] + w)
    c.saveState()
    c.setStrokeColor(HexColor(r['couleur_trait']))
    c.setLineWidth(TRAITS[r['trait']])
    c.setFillColorRGB(1, 1, 1)
    c.rect(x, bas, largeur, h, stroke=1, fill=1)
    for xi in xs[1:-1]:
        c.line(xi, bas, xi, haut)
    i0 = 2 if avec_logo else 1                          # indice de la première case libre
    if lc:
        c.line(xs[i0], haut - h_lib, xs[-1], haut - h_lib)
    c.setFillColorRGB(0, 0, 0)
    if avec_logo and logo:
        try:
            img = ImageReader(io.BytesIO(logo))
            iw, ih = img.getSize()
            k = min((ws[0] - 6) / iw, (h - 6) / ih)
            c.drawImage(img, x + (ws[0] - iw * k) / 2, bas + (h - ih * k) / 2, iw * k, ih * k, mask='auto')
        except Exception as e:  # noqa: BLE001
            journal.info('Logo du cartouche illisible : %s', e)
    st = ParagraphStyle('cq', fontName=gras if r['titre_gras'] else police, fontSize=r['taille_titre'],
                        leading=r['taille_titre'] * 1.3, alignment=TA_CENTER)
    p = Paragraph('<br/>'.join(escape(l) for l in co['titre'].split('\n')), st)
    j = 1 if avec_logo else 0
    _, ph = p.wrap(ws[j] - 8, h)
    p.drawOn(c, xs[j] + 4, bas + (h - ph) / 2)
    cases = list(co['colonnes']) + ([(r['page_libelle'], None)] if co['page'] else [])
    for k, (lib, val) in enumerate(cases):
        a, b = xs[i0 + k], xs[i0 + k + 1]
        mil = (a + b) / 2
        c.setFont(gras if r['libelles_gras'] else police, r['taille'])
        c.drawCentredString(mil, haut - h_lib + (h_lib - r['taille'] * 0.72) / 2, lib)
        y_val = bas + (h - h_lib - r['taille'] * 0.72) / 2
        if val is not None:
            taille = r['taille']
            while taille > 6 and c.stringWidth(val, police, taille) > (b - a) - 4:
                taille -= 0.25
            c.setFont(police, taille)
            c.drawCentredString(mil, y_val, val)
        else:
            fmt = r['page_format']
            morceaux = {'n_de_N': ((str(page), gras), (' de ', police), (str(total), gras)),
                        'n_sur_N': ((str(page), gras), (' sur ', police), (str(total), gras)),
                        'n/N': ((str(page), gras), ('/', police), (str(total), gras)),
                        'page_n_sur_N': (('Page ', police), (str(page), gras), (' sur ', police), (str(total), gras))}[fmt]
            cx = mil - sum(c.stringWidth(t_, f_, r['taille']) for t_, f_ in morceaux) / 2
            for t_, f_ in morceaux:
                c.setFont(f_, r['taille'])
                c.drawString(cx, y_val, t_)
                cx += c.stringWidth(t_, f_, r['taille'])
    c.restoreState()
    return h


def document_pdf(buffer, cid, audit=None, reglage=None, **kw):
    """SimpleDocTemplate A4 portant le cartouche sur chaque page (s'il est activé), numéroté « n de N ».
    S'utilise comme d'habitude : doc = document_pdf(buffer, cid, audit); doc.build(story).
    Sans cartouche : A4 avec un numéro « Page n / N » discret en bas de page."""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen.canvas import Canvas
    from reportlab.platypus import SimpleDocTemplate
    r = reglage or lire(cid)
    on = bool(r.get('actif')) if reglage is not None else actif(cid)
    marge = 15 * MM
    kw.setdefault('leftMargin', marge)
    kw.setdefault('rightMargin', marge)
    kw.setdefault('bottomMargin', 16 * MM)
    kw.setdefault('topMargin', (9 + hauteur_mm(r) + 7) * MM if on else 18 * MM)
    doc = SimpleDocTemplate(buffer, pagesize=A4, **kw)
    logo = _logo(cid) if (on and r['logo']) else None
    largeur_texte = A4[0] - kw['leftMargin'] - kw['rightMargin']
    largeur = largeur_cartouche_mm(r, largeur_texte / MM) * MM
    x_cartouche = (A4[0] - largeur) / 2

    class CanevasNumerote(Canvas):
        """Garde les pages en mémoire pour connaître le total, puis pose cartouche / numéro sur chacune."""
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self._pages = []

        def showPage(self):
            self._pages.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            total = len(self._pages)
            for n, etat in enumerate(self._pages, start=1):
                self.__dict__.update(etat)
                if on and (n > 1 or r['premiere_page']):
                    dessiner_rl(self, r, n, total, x_cartouche, A4[1] - 9 * MM, largeur, logo, audit)
                if not on or r['page_format'] == 'aucune':
                    self.saveState()
                    self.setFont('Helvetica', 8)
                    self.setFillColorRGB(0.45, 0.45, 0.45)
                    self.drawRightString(A4[0] - kw['rightMargin'], 9 * MM, f'Page {n} / {total}')
                    self.restoreState()
                super().showPage()
            super().save()

    construire = doc.build

    def build(story, **k):
        k.setdefault('canvasmaker', CanevasNumerote)
        return construire(story, **k)
    doc.build = build
    return doc


# ================================================================ Word
def _run(p, texte, police, taille, gras=False):
    from docx.oxml.ns import qn
    from docx.shared import Pt
    run = p.add_run(texte)
    run.font.name = police
    run.font.size = Pt(taille)
    run.bold = gras
    fonts = run._r.get_or_add_rPr().find(qn('w:rFonts'))
    if fonts is not None:
        for att in ('w:ascii', 'w:hAnsi', 'w:cs', 'w:eastAsia'):
            fonts.set(qn(att), police)
    return run


def _champ(p, instruction, police, taille, gras):
    """Champ Word (PAGE / NUMPAGES) en runs séparés, chacun à la police du cartouche (sinon Word l'affiche
    dans la police par défaut)."""
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    def fld(t):
        e = OxmlElement('w:fldChar'); e.set(qn('w:fldCharType'), t); return e
    instr = OxmlElement('w:instrText'); instr.set(qn('xml:space'), 'preserve'); instr.text = f' {instruction} '
    texte = OxmlElement('w:t'); texte.text = '1'
    for el in (fld('begin'), instr, fld('separate'), texte, fld('end')):
        _run(p, '', police, taille, gras)._r.append(el)


def cartouche_word(doc, cid, audit=None):
    """Remplace l'en-tête de page du document Word par le cartouche (s'il est activé). Rend True s'il est posé."""
    if not actif(cid):
        return False
    try:
        from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT as V, WD_TABLE_ALIGNMENT
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.oxml import OxmlElement
        from docx.oxml.ns import qn
        from docx.shared import Cm, Pt
        r = lire(cid)
        co = contenu(r, audit)
        police = POLICES[r['police']][0]
        section = doc.sections[0]
        if not r['premiere_page']:
            section.different_first_page_header_footer = True
        entete = section.header
        entete.is_linked_to_previous = False
        for p in list(entete.paragraphs):
            p.text = ''
        largeur_texte = section.page_width - section.left_margin - section.right_margin
        largeur = Cm(largeur_cartouche_mm(r, largeur_texte / 36000) / 10)
        avec_logo = r['logo']
        lg, lt, lc = largeurs(r, avec_logo, largeur / 12700, audit)
        ws = ([lg] if avec_logo else []) + [lt] + lc
        n_cases = len(lc)
        t = entete.add_table(rows=2 if n_cases else 1, cols=len(ws), width=largeur)
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        t.autofit = False
        tblPr = t._tbl.tblPr
        bords = OxmlElement('w:tblBorders')
        for cote in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'):
            b = OxmlElement(f'w:{cote}')
            b.set(qn('w:val'), 'single'); b.set(qn('w:sz'), str(max(2, int(TRAITS[r['trait']] * 8))))
            b.set(qn('w:color'), r['couleur_trait'].lstrip('#'))
            bords.append(b)
        tblPr.append(bords)
        disposition = OxmlElement('w:tblLayout'); disposition.set(qn('w:type'), 'fixed')
        tblPr.append(disposition)
        marges = OxmlElement('w:tblCellMar')               # marges intérieures fines, comme un cartouche Word usuel
        for cote, v in (('left', 57), ('right', 57), ('top', 0), ('bottom', 0)):
            e = OxmlElement(f'w:{cote}'); e.set(qn('w:w'), str(v)); e.set(qn('w:type'), 'dxa'); marges.append(e)
        tblPr.append(marges)
        # tableau centré : plus large que le texte (« largeur de la page »), il déborde également des deux côtés
        grille = t._tbl.tblGrid
        for j, w in enumerate(ws):
            larg = int(largeur * w / 100)
            t.columns[j].width = larg
            grille.gridCol_lst[j].w = larg
            for i in range(len(t.rows)):
                t.cell(i, j).width = larg

        def ecrire(cellule, texte, gras=False, taille=None):
            p = cellule.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.space_before = p.paragraph_format.space_after = Pt(1)
            lignes = texte.split('\n')
            for k, ligne in enumerate(lignes):
                run = _run(p, ligne, police, taille or r['taille'], gras)
                if k < len(lignes) - 1:
                    run.add_break()
            cellule.vertical_alignment = V.CENTER

        j = 0
        if avec_logo:
            logo_c = t.cell(0, 0).merge(t.cell(1, 0)) if n_cases else t.cell(0, 0)
            logo_c.vertical_alignment = V.CENTER
            logo = _logo(cid)
            p = logo_c.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            if logo:
                try:
                    p.add_run().add_picture(io.BytesIO(logo), height=Cm(1.25))
                except Exception:  # noqa: BLE001
                    pass
            j = 1
        titre_c = t.cell(0, j).merge(t.cell(1, j)) if n_cases else t.cell(0, j)
        ecrire(titre_c, co['titre'], gras=r['titre_gras'], taille=r['taille_titre'])
        cases = list(co['colonnes']) + ([(r['page_libelle'], None)] if co['page'] else [])
        for k, (lib, val) in enumerate(cases, start=j + 1):
            ecrire(t.cell(0, k), lib, gras=r['libelles_gras'])
            if val is not None:
                ecrire(t.cell(1, k), val)
                continue
            cel = t.cell(1, k)
            cel.vertical_alignment = V.CENTER
            p = cel.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.space_before = p.paragraph_format.space_after = Pt(1)
            fmt = r['page_format']
            if fmt == 'page_n_sur_N':
                _run(p, 'Page ', police, r['taille'])
            _champ(p, 'PAGE', police, r['taille'], True)
            _run(p, {'n_de_N': ' de ', 'n_sur_N': ' sur ', 'n/N': '/', 'page_n_sur_N': ' sur '}[fmt], police, r['taille'])
            _champ(p, 'NUMPAGES', police, r['taille'], True)
        if co['page']:
            # la case PAGE numérote déjà : on retire le « Page X / Y » du pied (une seule numérotation, comme en PDF)
            for p in list(section.footer.paragraphs):
                if 'NUMPAGES' in p._p.xml:
                    if len(section.footer.paragraphs) > 1:
                        p._p.getparent().remove(p._p)
                    else:
                        for el in list(p._p):
                            if el.tag != qn('w:pPr'):
                                p._p.remove(el)
        entete._element.remove(t._tbl)
        entete.paragraphs[0]._p.addprevious(t._tbl)
        entete.paragraphs[0].paragraph_format.space_after = Pt(4)
        section.header_distance = Cm(0.9)
        section.top_margin = max(section.top_margin, Cm(0.9 + hauteur_mm(r) / 10 + 0.9))
        return True
    except Exception as e:  # noqa: BLE001 — un cartouche défectueux ne doit jamais bloquer le rapport
        journal.warning('Cartouche Word non appliqué : %s', e)
        return False


# ================================================================ pages
def _peut():
    try:
        from egalyx.identite import peut_regler
        return peut_regler()
    except Exception:  # noqa: BLE001
        return est_super_admin()


def _retour(cid):
    return redirect(url_for('identite.page', client_id=cid if est_super_admin() else None) + '#cartouche-qualite')


@bp.route('/', methods=['POST'])
@client_requis
def regler():
    if not _peut():
        abort(403)
    cid = client_id_courant()
    r = enregistrer_reglage(cid, request.form)
    journaliser('cartouche_qualite', {'actif': r['actif'], 'titre': r['titre'], 'colonnes': r['colonnes'],
                                      'page_format': r['page_format']}, client_id=cid)
    _m().db.session.commit()
    flash('Cartouche qualité ' + ('activé : il figure en haut de chaque page du rapport d\'audit (PDF et Word).'
                                   if r['actif'] else 'enregistré (désactivé).'), 'success')
    return _retour(cid)


@bp.route('/apercu')
@client_requis
def apercu():
    """PDF de démonstration (3 pages) avec le cartouche tel que saisi dans le formulaire, enregistré ou non."""
    if not _peut():
        abort(403)
    cid = client_id_courant()
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import PageBreak, Paragraph, Spacer
    r = dict(depuis_formulaire(request.args) if request.args.get('apercu') == '1' else lire(cid), actif=True)
    tampon = io.BytesIO()
    doc = document_pdf(tampon, cid, None, reglage=r, title='Aperçu du cartouche qualité')
    st = getSampleStyleSheet()
    story = []
    for n in range(1, 4):
        story += [Paragraph(f"Aperçu du rapport d'audit — page {n}", st['Heading2']), Spacer(1, 8),
                  Paragraph('Le contenu du rapport commence sous le cartouche, en pleine largeur, sans réduction. '
                            'La case PAGE est numérotée automatiquement sur chaque page.', st['Normal'])]
        if n < 3:
            story.append(PageBreak())
    doc.build(story)
    return send_file(io.BytesIO(tampon.getvalue()), mimetype='application/pdf', download_name='apercu_cartouche_qualite.pdf')


def enregistrer(app):
    if 'cartouche_qualite' not in app.blueprints:
        app.register_blueprint(bp)
    app.jinja_env.globals['cartouche_qualite'] = lire
    app.jinja_env.globals['cartouche_actif'] = actif
    app.jinja_env.globals['cartouche_rapport'] = cartouche_rapport
    app.jinja_env.globals['cartouche_html'] = html
    app.jinja_env.globals['cartouche_formats_page'] = FORMATS_PAGE
    app.jinja_env.globals['cartouche_champs'] = CHAMPS
    app.jinja_env.globals['cartouche_logo'] = _logo_uri
