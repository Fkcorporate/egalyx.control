"""
egalyx/cartouche_qualite.py — cartouche qualité en haut de chaque page du rapport d'audit.

Exigence qualité fréquente (ISO 9001, maîtrise documentaire) : chaque page porte un cartouche
  | logo | TITRE DU DOCUMENT | CODE | DATE | VERSION | PAGE |
  |      |                   | ENR 003/ PRG-AUDI | 1/03/2023 | 00 | 2 de 5 |

L'administrateur de l'organisation le règle lui-même (Identité de l'organisation > Cartouche qualité) :
titre, code, date et version du document, logo oui / non. La page « n de N » est calculée.

Où il apparaît :
  - rapports d'audit PDF (export PDF, rapport complet PDF, rapport élégant) : posé en haut de chaque page
    par egalyx/papier_entete.py, qui réduit légèrement le contenu pour le placer dessous et numérote les pages ;
  - rapports d'audit Word : en-tête de chaque page, numéros PAGE / NUMPAGES mis à jour par Word ;
  - rapport complet à l'écran / imprimé depuis le navigateur : en haut du document (sans la colonne PAGE,
    que le navigateur ne sait pas remplir).
Il remplace le papier à en-tête PDF déposé pour le rapport d'audit, s'il y en a un, tant qu'il est activé.

Stockage : ClientConfiguration.preferences['cartouche_qualite'] (base de données : survit aux redéploiements).
"""
import base64
import io
import logging
import re

from flask import Blueprint, abort, flash, g, has_request_context, redirect, request, send_file, url_for

from egalyx.commun import client_id_courant, client_requis, est_super_admin, journaliser

journal = logging.getLogger('egalyx.cartouche_qualite')
bp = Blueprint('cartouche_qualite', __name__, url_prefix='/organisation/cartouche-qualite')

CLE = 'cartouche_qualite'
DEFAUT = {'actif': False, 'titre': "RAPPORT D'AUDIT INTERNE", 'code': '', 'date': '', 'version': '', 'logo': True}
LONGUEURS = {'titre': 90, 'code': 40, 'date': 20, 'version': 12}
MM = 72 / 25.4

# Géométrie (points PDF, A4 595 x 842) relevée sur un cartouche qualité type
X0, HAUT = 40.5, 41.0                          # bord gauche, distance du haut de la page
COLS = (70.0, 157.0, 112.0, 65.0, 58.5, 62.0)  # logo, titre, code, date, version, page
H_ETIQ, H_VAL = 13.0, 30.0
ECART_MM = 6


def _m():
    import models
    return models


# ---------------------------------------------------------------- réglage
def lire(cid):
    if not cid:
        return dict(DEFAUT)
    cache = g.setdefault('_eg_cartouche', {}) if has_request_context() else {}
    if cid in cache:
        return cache[cid]
    r = dict(DEFAUT)
    try:
        conf = _m().ClientConfiguration.query.filter_by(client_id=cid).first()
        r.update(((conf.preferences or {}).get(CLE) if conf else None) or {})
    except Exception as e:  # noqa: BLE001
        journal.info('Cartouche illisible pour %s : %s', cid, e)
    cache[cid] = r
    return r


def actif(cid):
    r = lire(cid)
    return bool(r.get('actif')) and bool((r.get('titre') or '').strip())


def _nettoyer(v, n):
    return ' '.join(str(v or '').split())[:n]


def enregistrer_reglage(cid, form):
    m = _m()
    r = {cle: _nettoyer(form.get(cle), n) for cle, n in LONGUEURS.items()}
    r['titre'] = (form.get('titre') or '').strip()[:LONGUEURS['titre']] or DEFAUT['titre']
    r['actif'] = form.get('actif') == '1'
    r['logo'] = form.get('logo') == '1'
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


# ---------------------------------------------------------------- PDF : le « papier » du cartouche
def pdf_papier(r, logo=None):
    """Page A4 portant le cartouche (case PAGE vide : remplie « n de N » par papier_entete)."""
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas as rl
    from reportlab.platypus import Paragraph
    W, H = 595.0, 842.0
    tampon = io.BytesIO()
    c = rl.Canvas(tampon, pagesize=(W, H))
    haut = H - HAUT
    bas = haut - H_ETIQ - H_VAL
    xs = [X0]
    for w in COLS:
        xs.append(xs[-1] + w)
    c.setLineWidth(0.6)
    c.setStrokeColorRGB(0, 0, 0)
    c.rect(X0, bas, xs[-1] - X0, haut - bas)
    for x in xs[1:-1]:
        c.line(x, bas, x, haut)
    c.line(xs[2], haut - H_ETIQ, xs[-1], haut - H_ETIQ)          # sous les intitulés CODE / DATE…
    # logo
    if logo and r.get('logo', True):
        try:
            img = ImageReader(io.BytesIO(logo))
            iw, ih = img.getSize()
            k = min((COLS[0] - 10) / iw, (haut - bas - 8) / ih)
            w, h = iw * k, ih * k
            c.drawImage(img, X0 + (COLS[0] - w) / 2, bas + (haut - bas - h) / 2, w, h, mask='auto')
        except Exception as e:  # noqa: BLE001
            journal.info('Logo du cartouche illisible : %s', e)
    # titre (centré, sur plusieurs lignes si besoin)
    st = ParagraphStyle('t', fontName='Helvetica', fontSize=8.5, leading=10.5, alignment=TA_CENTER)
    from xml.sax.saxutils import escape
    p = Paragraph(escape(r.get('titre') or ''), st)
    _, ph = p.wrap(COLS[1] - 10, haut - bas)
    p.drawOn(c, xs[1] + 5, bas + (haut - bas - ph) / 2)
    # intitulés et valeurs
    c.setFillColorRGB(0, 0, 0)
    for i, (lib, cle) in enumerate((('CODE', 'code'), ('DATE', 'date'), ('VERSION', 'version'), ('PAGE', None))):
        x_mil = (xs[2 + i] + xs[3 + i]) / 2
        c.setFont('Helvetica', 8)
        c.drawCentredString(x_mil, haut - H_ETIQ + 4, lib)
        if cle:
            v = r.get(cle) or ''
            taille = 8
            while taille > 6 and c.stringWidth(v, 'Helvetica', taille) > COLS[2 + i] - 6:
                taille -= 0.5
            c.setFont('Helvetica', taille)
            c.drawCentredString(x_mil, bas + H_VAL / 2 - 3, v)
    c.showPage()
    c.save()
    numero = {'x': xs[5] + 1.5, 'x_fin': xs[6] - 1.5, 'y': bas + H_VAL / 2 - 3, 'centre': (xs[5] + xs[6]) / 2}
    reglage = {'haut': round((HAUT + H_ETIQ + H_VAL) / MM + ECART_MM), 'bas': 12, 'gauche': 14, 'droite': 14,
               'numero': numero, 'numeroter': True, 'actif': True}
    return tampon.getvalue(), reglage


def reglage_papier(cid):
    """Pour egalyx/papier_entete.py : le cartouche, sous forme de papier (octets + zone libre), ou None."""
    if not actif(cid):
        return None
    cache = g.setdefault('_eg_cartouche_pdf', {}) if has_request_context() else {}
    if cid not in cache:
        r = lire(cid)
        octets, reglage = pdf_papier(r, _logo(cid) if r.get('logo', True) else None)
        reglage['octets'] = octets
        reglage['chemin'] = None
        reglage['nom'] = 'Cartouche qualité'
        cache[cid] = reglage
    return cache[cid]


# ---------------------------------------------------------------- Word
def cartouche_word(doc, cid):
    """Remplace l'en-tête de page du document Word par le cartouche (s'il est activé)."""
    if not actif(cid):
        return False
    try:
        from docx.enum.table import WD_TABLE_ALIGNMENT
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.oxml import OxmlElement
        from docx.oxml.ns import qn
        from docx.shared import Cm, Pt
        from egalyx.rapport_word import _champ
        r = lire(cid)
        section = doc.sections[0]
        entete = section.header
        entete.is_linked_to_previous = False
        for p in list(entete.paragraphs):
            p.text = ''
        largeur = section.page_width - section.left_margin - section.right_margin
        total = sum(COLS)
        t = entete.add_table(rows=2, cols=6, width=largeur)
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        t.autofit = False
        # bordures fines noires
        tblPr = t._tbl.tblPr
        bords = OxmlElement('w:tblBorders')
        for cote in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'):
            b = OxmlElement(f'w:{cote}')
            b.set(qn('w:val'), 'single'); b.set(qn('w:sz'), '4'); b.set(qn('w:color'), '000000')
            bords.append(b)
        tblPr.append(bords)
        disposition = OxmlElement('w:tblLayout'); disposition.set(qn('w:type'), 'fixed')
        tblPr.append(disposition)
        grille = t._tbl.tblGrid
        for j, w in enumerate(COLS):
            larg = int(largeur * w / total)
            t.columns[j].width = larg
            grille.gridCol_lst[j].w = larg
            for i in range(2):
                t.cell(i, j).width = larg
        logo_c = t.cell(0, 0).merge(t.cell(1, 0))
        titre_c = t.cell(0, 1).merge(t.cell(1, 1))

        def ecrire(cellule, texte, gras=False, taille=8):
            p = cellule.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.space_before = p.paragraph_format.space_after = Pt(1)
            run = p.add_run(texte)
            run.font.size = Pt(taille); run.bold = gras; run.font.name = 'Arial'
            return p

        from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT as V
        for cell in (logo_c, titre_c):
            cell.vertical_alignment = V.CENTER
        logo = _logo(cid) if r.get('logo', True) else None
        if logo:
            p = logo_c.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            try:
                p.add_run().add_picture(io.BytesIO(logo), height=Cm(1.2))
            except Exception:  # noqa: BLE001
                pass
        ecrire(titre_c, r.get('titre') or '', taille=8.5)
        for j, (lib, cle) in enumerate((('CODE', 'code'), ('DATE', 'date'), ('VERSION', 'version'), ('PAGE', None)), start=2):
            ecrire(t.cell(0, j), lib)
            t.cell(1, j).vertical_alignment = V.CENTER
            if cle:
                ecrire(t.cell(1, j), r.get(cle) or '')
            else:
                p = t.cell(1, j).paragraphs[0]
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                for morceau, gras in (('PAGE', True), (' de ', False), ('NUMPAGES', True)):
                    run = _champ(p, morceau) if morceau in ('PAGE', 'NUMPAGES') else p.add_run(morceau)
                    run.font.size = Pt(8); run.bold = gras; run.font.name = 'Arial'
        # place le tableau en tête de l'en-tête, puis un petit espace
        entete._element.remove(t._tbl)
        entete.paragraphs[0]._p.addprevious(t._tbl)
        entete.paragraphs[0].paragraph_format.space_after = Pt(4)
        section.header_distance = Cm(0.8)
        return True
    except Exception as e:  # noqa: BLE001 — un cartouche défectueux ne doit jamais bloquer le rapport
        journal.warning('Cartouche Word non appliqué : %s', e)
        return False


# ---------------------------------------------------------------- pages
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
    _m().db.session.commit()
    journaliser('cartouche_qualite', {k: r[k] for k in ('actif', 'titre', 'code', 'date', 'version')}, client_id=cid)
    flash('Cartouche qualité ' + ('activé : il figure désormais en haut de chaque page du rapport d\'audit.'
                                   if r['actif'] else 'enregistré (désactivé).'), 'success')
    return _retour(cid)


@bp.route('/apercu')
@client_requis
def apercu():
    if not _peut():
        abort(403)
    cid = client_id_courant()
    from egalyx.papier_entete import page_exemple, poser
    r = dict(lire(cid), actif=True)
    for cle, n in LONGUEURS.items():                 # valeurs du formulaire pas encore enregistrées
        if cle in request.args:
            r[cle] = _nettoyer(request.args.get(cle), n) or r[cle]
    if request.args.get('apercu') == '1':
        r['logo'] = request.args.get('logo') == '1'
    octets, reglage = pdf_papier(r, _logo(cid) if r.get('logo', True) else None)
    reglage.update(octets=octets, chemin=None)
    pdf = poser(page_exemple("Aperçu — rapport d'audit"), cid, 'rapport_audit', reglage_force=reglage)
    return send_file(io.BytesIO(pdf), mimetype='application/pdf', download_name='apercu_cartouche_qualite.pdf')


def enregistrer(app):
    if 'cartouche_qualite' not in app.blueprints:
        app.register_blueprint(bp)
    app.jinja_env.globals['cartouche_qualite'] = lire
    app.jinja_env.globals['cartouche_actif'] = actif

    def _logo_uri(cid):
        try:
            from egalyx.identite import logo_data_uri
            return logo_data_uri(cid)
        except Exception:  # noqa: BLE001
            return None
    app.jinja_env.globals['cartouche_logo'] = _logo_uri
