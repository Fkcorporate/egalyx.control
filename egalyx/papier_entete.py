"""
egalyx/papier_entete.py — papier à en-tête PDF du client pour ses rapports d'audit et ses lettres de mission.

Le client fournit son propre papier (PDF d'une page : logo, cartouche qualité, pied de page avec ses coordonnées…).
Le super admin le dépose dans « Heure, devise et lettres de mission » → réglages de l'organisation, un par type :
  - rapport_audit   : chaque page des rapports d'audit (export PDF, rapport complet, rapport élégant)
                      est posée sur ce papier, dans la zone libre (entre l'en-tête et le pied du papier) ;
  - lettre_mission  : la lettre est mise en page directement dans la zone libre, sans l'en-tête du modèle
                      (le logo et les coordonnées sont déjà sur le papier).

Zone libre : détectée automatiquement à l'envoi (on mesure où le papier est imprimé), modifiable à la main en mm.
Numérotation : si le papier contient « 1 de 1 » (cartouche qualité), ce texte devient « 2 de 5 »… sur chaque page.

Les fichiers sont rangés dans le disque persistant (/var/data sur Render, ou EGALYX_DONNEES), sinon dans instance/.
Sans papier déposé, rien ne change : les PDF sortent exactement comme avant.
"""
import io
import json
import logging
import os
import re
from datetime import datetime

from flask import Blueprint, abort, current_app, flash, redirect, request, send_file, url_for
from flask_login import current_user

from egalyx.commun import client_id_courant, journaliser, super_admin_requis

journal = logging.getLogger('egalyx.papier_entete')
bp = Blueprint('papier_entete', __name__)

TYPES = {
    'rapport_audit': "Rapport d'audit",
    'lettre_mission': 'Lettre de mission',
}
# routes dont le PDF est posé sur le papier « rapport d'audit » (fonctions de sections/audit.py)
ROUTES_RAPPORT = {'export_rapport_audit_pdf', 'export_rapport_audit_complet', 'rapport_audit_pdf_elegant'}
MM = 72 / 25.4
TAILLE_MAX = 5 * 1024 * 1024
ECART = 6          # mm laissés entre le papier imprimé et le contenu


def pypdf_present():
    """La bibliothèque pypdf (requirements.txt) est-elle installée sur le serveur ? Sans elle, le papier n'est pas appliqué."""
    try:
        import pypdf  # noqa: F401
        return True
    except ImportError:
        return False


# ------------------------------------------------------------------ rangement des fichiers
def _racine():
    base = os.environ.get('EGALYX_DONNEES')
    if not base and os.path.isdir('/var/data') and os.access('/var/data', os.W_OK):
        base = '/var/data'
    return os.path.join(base or current_app.instance_path, 'papiers_entete')


def _chemins(cid, type_):
    d = os.path.join(_racine(), str(int(cid)))
    return d, os.path.join(d, type_ + '.pdf'), os.path.join(d, type_ + '.json')


def reglage(cid, type_):
    """Réglage du papier {marges en mm, nom, date…} ou None s'il n'y a pas de papier pour ce type."""
    if not cid or type_ not in TYPES:
        return None
    _, pdf, js = _chemins(cid, type_)
    if not os.path.exists(pdf):
        return None
    try:
        with open(js, encoding='utf-8') as f:
            r = json.load(f)
    except Exception:  # noqa: BLE001
        r = {}
    r.setdefault('haut', 25); r.setdefault('bas', 20); r.setdefault('gauche', 18); r.setdefault('droite', 18)
    r.setdefault('actif', True)
    r['chemin'] = pdf
    return r if r.get('actif', True) else None


def tous(cid):
    out = {}
    for t in TYPES:
        _, pdf, js = _chemins(cid, t)
        if os.path.exists(pdf):
            try:
                with open(js, encoding='utf-8') as f:
                    out[t] = json.load(f)
            except Exception:  # noqa: BLE001
                out[t] = {}
    return out


# ------------------------------------------------------------------ lecture des PDF (pypdf)
def _mult(a, b):
    return [a[0] * b[0] + a[1] * b[2], a[0] * b[1] + a[1] * b[3], a[2] * b[0] + a[3] * b[2],
            a[2] * b[1] + a[3] * b[3], a[4] * b[0] + a[5] * b[2] + b[4], a[4] * b[1] + a[5] * b[3] + b[5]]


def _pt(m, x, y):
    return m[0] * x + m[2] * y + m[4], m[1] * x + m[3] * y + m[5]


def _encre(page):
    """Points où la page est réellement imprimée : textes, images, traits et rectangles (repère PDF, origine en bas).
    Renvoie (points, textes) — textes = [(texte, x, y)] pour repérer « 1 de 1 »."""
    points, textes = [], []
    pile, ctm = [], [1, 0, 0, 1, 0, 0]
    etat = {'ctm': ctm}

    def avant(op, args, cm, tm):
        try:
            if op == b'q':
                pile.append(list(etat['ctm']))
            elif op == b'Q' and pile:
                etat['ctm'] = pile.pop()
            elif op == b'cm' and len(args) == 6:
                etat['ctm'] = _mult([float(a) for a in args], etat['ctm'])
            elif op == b'Do':
                for x, y in ((0, 0), (1, 0), (0, 1), (1, 1)):
                    points.append(_pt(etat['ctm'], x, y))
            elif op == b're' and len(args) == 4:
                x, y, w, h = (float(a) for a in args)
                if abs(w) < 590 or abs(h) < 830:                     # un fond pleine page n'est pas de l'« encre »
                    for px, py in ((x, y), (x + w, y + h)):
                        points.append(_pt(etat['ctm'], px, py))
            elif op in (b'm', b'l') and len(args) == 2:
                points.append(_pt(etat['ctm'], float(args[0]), float(args[1])))
        except Exception:  # noqa: BLE001
            pass

    def texte(t, cm, tm, *_):
        if t and t.strip():
            x, y = _pt(_mult(tm, cm), 0, 0)
            points.append((x, y)); points.append((x, y + 8))
            textes.append((t, x, y))

    try:
        page.extract_text(visitor_operand_before=avant, visitor_text=texte)
    except Exception as e:  # noqa: BLE001
        journal.info('Lecture du contenu impossible : %s', e)
    l, b, r, h = (float(v) for v in page.mediabox)
    points = [(x, y) for x, y in points if l - 5 <= x <= r + 5 and b - 5 <= y <= h + 5]
    return points, textes


def analyser(octets):
    """Vérifie le papier et propose la zone libre (mm) : sous l'en-tête imprimé, au-dessus du pied imprimé."""
    from pypdf import PdfReader
    r = PdfReader(io.BytesIO(octets))
    if not r.pages:
        raise ValueError('Le PDF ne contient aucune page.')
    page = r.pages[0]
    l, b, rr, hh = (float(v) for v in page.mediabox)
    W, H = rr - l, hh - b
    pts, textes = _encre(page)
    haut_pts = [y for x, y in pts if y - b > H / 2]
    bas_pts = [y for x, y in pts if y - b <= H / 2]
    haut = (hh - min(haut_pts)) / MM + ECART if haut_pts else 20
    bas = (max(bas_pts) - b) / MM + ECART if bas_pts else 18
    gauche = droite = 18
    numero = _position_numero(textes)
    return {'largeur_mm': round(W / MM), 'hauteur_mm': round(H / MM), 'pages': len(r.pages),
            'haut': round(min(max(haut, 10), H / MM / 2 - 20)), 'bas': round(min(max(bas, 10), H / MM / 2 - 20)),
            'gauche': gauche, 'droite': droite, 'numero': numero}


def _position_numero(textes):
    """Emplacement de « 1 de 1 » (cartouche qualité) : on le réécrira « n de N » sur chaque page.
    On s'appuie sur le « de » central : le lecteur PDF donne parfois une position nulle au morceau qui suit
    un changement de police (le « 1 » en gras)."""
    propres = [(t.strip(), x, y) for t, x, y in textes]
    for i, (t, x, y) in enumerate(propres):
        avant = propres[i - 1][0] if i > 0 else ''
        apres = propres[i + 1][0] if i + 1 < len(propres) else ''
        seul = re.match(r'^1\s*de\s*1$', t)
        if not seul and not (t == 'de' and avant == '1' and apres == '1'):
            continue
        if seul:
            return {'x': round(x, 1), 'y': round(y, 1), 'x_fin': round(x + 30, 1)}
        xa, ya = propres[i - 1][1], propres[i - 1][2]
        debut = xa if abs(ya - y) < 2 and 0 < x - xa < 20 else x - 8.5
        xf, yf = propres[i + 1][1], propres[i + 1][2]
        fin = xf + 6 if abs(yf - y) < 2 and xf > x else x + 20
        return {'x': round(debut, 1), 'y': round(y, 1), 'x_fin': round(fin, 1)}
    return None


# ------------------------------------------------------------------ pose du contenu sur le papier
def _rectangle_contenu(reader):
    """Rectangle (repère PDF) qui contient le contenu de TOUTES les pages : même placement sur chaque page."""
    xs, ys = [], []
    for p in reader.pages:
        pts, _ = _encre(p)
        xs += [x for x, _ in pts]; ys += [y for _, y in pts]
    p0 = reader.pages[0]
    l, b, r, h = (float(v) for v in p0.mediabox)
    if len(xs) < 2:
        return l, b, r, h
    marge = 10
    gauche = max(l, min(xs) - marge)
    # le texte n'est connu que par le début de ses lignes : la marge de droite est prise égale à celle de gauche
    droite = min(r, max(max(xs) + marge + 40, (l + r) - gauche))
    return (gauche, max(b, min(ys) - marge - 4), droite, min(h, max(ys) + marge + 4))


def _decouper(page, x0, y0, x1, y1):
    """Ne garde que le rectangle (le reste du contenu ne doit jamais déborder sur l'en-tête du papier)."""
    from pypdf.generic import ContentStream, NameObject
    contenu = page.get_contents()
    if contenu is None:
        return page
    donnees = contenu.get_data()
    debut = f'q {x0:.2f} {y0:.2f} {x1 - x0:.2f} {y1 - y0:.2f} re W n\n'.encode()
    cs = ContentStream(None, None)
    cs.set_data(debut + donnees + b'\nQ\n')
    page[NameObject('/Contents')] = cs
    return page


def _numeros(W, H, numero, total):
    """Calques « n de N » posés sur l'emplacement de « 1 de 1 »."""
    from reportlab.pdfgen import canvas as rl
    from pypdf import PdfReader
    tampon = io.BytesIO()
    c = rl.Canvas(tampon, pagesize=(W, H))
    for n in range(1, total + 1):
        x, y, xf = numero['x'], numero['y'], numero['x_fin']
        c.setFillColorRGB(1, 1, 1); c.rect(x - 2, y - 2.5, max(xf - x, 30) + 4, 10.5, stroke=0, fill=1)
        c.setFillColorRGB(0, 0, 0)
        morceaux = ((str(n), 'Helvetica-Bold'), (' de ', 'Helvetica'), (str(total), 'Helvetica-Bold'))   # « 2 de 5 »
        cx = x
        for texte, police in morceaux:
            c.setFont(police, 8); c.drawString(cx, y, texte); cx += c.stringWidth(texte, police, 8)
        c.showPage()
    c.save()
    return PdfReader(io.BytesIO(tampon.getvalue()))


def poser(octets_pdf, cid, type_, natif=False):
    """Pose chaque page du PDF sur le papier à en-tête du client. Sans papier (ou en cas d'erreur) : PDF inchangé.
    natif=True : le PDF a déjà été mis en page dans la zone libre (lettre de mission) → pas de réduction."""
    r = reglage(cid, type_)
    if not r:
        return octets_pdf
    try:
        from pypdf import PdfReader, PdfWriter, Transformation
        papier = PdfReader(r['chemin']).pages[0]
        l, b, rr, hh = (float(v) for v in papier.mediabox)
        W, H = rr - l, hh - b
        src = PdfReader(io.BytesIO(octets_pdf))
        total = len(src.pages)
        # zone libre du papier (repère PDF)
        zx0, zx1 = l + r['gauche'] * MM, rr - r['droite'] * MM
        zy0, zy1 = b + r['bas'] * MM, hh - r['haut'] * MM
        if natif:
            t = Transformation()
            boite = None
        else:
            x0, y0, x1, y1 = _rectangle_contenu(src)
            k = min(1.0, (zx1 - zx0) / max(x1 - x0, 1), (zy1 - zy0) / max(y1 - y0, 1))
            dx = zx0 + ((zx1 - zx0) - (x1 - x0) * k) / 2          # centré en largeur
            dy = zy1 - (y1 - y0) * k                                 # collé sous l'en-tête
            t = Transformation().translate(-x0, -y0).scale(k, k).translate(dx, dy)
            boite = (x0, y0, x1, y1)
        num = _numeros(W, H, r['numero'], total) if r.get('numero') and r.get('numeroter', True) else None
        sortie = PdfWriter()
        for i, page in enumerate(src.pages):
            fond = PdfReader(r['chemin']).pages[0]               # une copie neuve du papier pour chaque page
            if boite:
                page = _decouper(page, *boite)
            fond.merge_transformed_page(page, t)
            if num is not None:
                fond.merge_page(num.pages[i])
            sortie.add_page(fond)
        try:
            sortie.add_metadata({k2: str(v) for k2, v in (src.metadata or {}).items() if isinstance(k2, str)})
        except Exception:  # noqa: BLE001
            pass
        tampon = io.BytesIO(); sortie.write(tampon)
        return tampon.getvalue()
    except Exception as e:  # noqa: BLE001 — un papier défectueux ne doit jamais bloquer un rapport
        journal.warning('Papier à en-tête %s du client %s non appliqué : %s', type_, cid, e)
        return octets_pdf


# ------------------------------------------------------------------ rapports d'audit : au moment de l'envoi
def _apres_requete(reponse):
    try:
        if request.endpoint not in ROUTES_RAPPORT or reponse.status_code != 200 or reponse.mimetype != 'application/pdf':
            return reponse
        cid = client_id_courant()
        if not reglage(cid, 'rapport_audit'):
            return reponse
        reponse.direct_passthrough = False
        nouveau = poser(reponse.get_data(), cid, 'rapport_audit')
        reponse.set_data(nouveau)
        reponse.headers['Content-Length'] = str(len(nouveau))
    except Exception as e:  # noqa: BLE001
        journal.warning('Papier à en-tête du rapport non appliqué : %s', e)
    return reponse


# ------------------------------------------------------------------ super admin : dépôt, réglage, aperçu, retrait
def _client(client_id):
    import models as M
    c = M.db.session.get(M.Client, client_id)
    if c is None:
        abort(404)
    return c


def _mm(valeur, defaut, mini=0, maxi=150):
    try:
        return max(mini, min(maxi, round(float(str(valeur).replace(',', '.')))))
    except (TypeError, ValueError):
        return defaut


@bp.route('/super-admin/client/<int:client_id>/papier-entete/<type_>', methods=['POST'])
@super_admin_requis
def deposer(client_id, type_):
    if type_ not in TYPES:
        abort(404)
    c = _client(client_id)
    d, pdf, js = _chemins(c.id, type_)
    retour = redirect(url_for('lettre_mission.reglages_client', client_id=c.id) + '#papiers-entete')
    fichier = request.files.get('fichier')
    if fichier and fichier.filename:
        octets = fichier.read(TAILLE_MAX + 1)
        if len(octets) > TAILLE_MAX:
            flash('Le papier à en-tête dépasse 5 Mo.', 'danger'); return retour
        if not octets.startswith(b'%PDF'):
            flash('Le papier à en-tête doit être un fichier PDF.', 'danger'); return retour
        if not pypdf_present():
            flash("Le serveur n'a pas la bibliothèque pypdf : redéployez avec le requirements.txt fourni (ligne « pypdf »), "
                  "puis déposez à nouveau le papier.", 'danger')
            return retour
        try:
            infos = analyser(octets)
        except Exception as e:  # noqa: BLE001
            flash(f'PDF illisible : {e}', 'danger'); return retour
        os.makedirs(d, exist_ok=True)
        with open(pdf, 'wb') as f:
            f.write(octets)
        infos.update(nom=fichier.filename[:120], depose_le=datetime.now().strftime('%d/%m/%Y %H:%M'),
                     depose_par=getattr(current_user, 'username', ''), actif=True, numeroter=True)
        with open(js, 'w', encoding='utf-8') as f:
            json.dump(infos, f, ensure_ascii=False)
        msg = f'Papier à en-tête « {TYPES[type_]} » enregistré. Zone libre détectée : {infos["haut"]} mm en haut, {infos["bas"]} mm en bas.'
        if infos.get('numero'):
            msg += ' La mention « 1 de 1 » sera numérotée sur chaque page.'
        if infos['largeur_mm'] not in range(205, 216) or infos['hauteur_mm'] not in range(292, 302):
            msg += f" Attention : le papier fait {infos['largeur_mm']} × {infos['hauteur_mm']} mm (A4 attendu)."
        flash(msg, 'success')
        journaliser('papier_entete_depot', f'{TYPES[type_]} — {c.nom}')
        return retour
    if not os.path.exists(pdf):
        flash('Choisissez d\'abord un fichier PDF.', 'warning'); return retour
    # simple réglage des marges / de la numérotation
    try:
        with open(js, encoding='utf-8') as f:
            infos = json.load(f)
    except Exception:  # noqa: BLE001
        infos = {}
    for cle, defaut in (('haut', 25), ('bas', 20), ('gauche', 18), ('droite', 18)):
        infos[cle] = _mm(request.form.get(cle), infos.get(cle, defaut), 5, 140)
    infos['numeroter'] = bool(request.form.get('numeroter'))
    infos['actif'] = bool(request.form.get('actif'))
    with open(js, 'w', encoding='utf-8') as f:
        json.dump(infos, f, ensure_ascii=False)
    flash(f'Réglage du papier « {TYPES[type_]} » enregistré.', 'success')
    return retour


@bp.route('/super-admin/client/<int:client_id>/papier-entete/<type_>/supprimer', methods=['POST'])
@super_admin_requis
def supprimer(client_id, type_):
    if type_ not in TYPES:
        abort(404)
    c = _client(client_id)
    _, pdf, js = _chemins(c.id, type_)
    for p in (pdf, js):
        if os.path.exists(p):
            os.remove(p)
    journaliser('papier_entete_retrait', f'{TYPES[type_]} — {c.nom}')
    flash(f'Papier à en-tête « {TYPES[type_]} » retiré : les documents reprennent leur mise en page habituelle.', 'info')
    return redirect(url_for('lettre_mission.reglages_client', client_id=c.id) + '#papiers-entete')


@bp.route('/super-admin/client/<int:client_id>/papier-entete/<type_>/original')
@super_admin_requis
def original(client_id, type_):
    if type_ not in TYPES:
        abort(404)
    _, pdf, _ = _chemins(_client(client_id).id, type_)
    if not os.path.exists(pdf):
        abort(404)
    return send_file(pdf, mimetype='application/pdf', download_name=f'papier_{type_}.pdf')


def page_exemple(titre, natif=False, r=None):
    """PDF d'essai : un texte de plusieurs pages, pour voir où tombe le contenu sur le papier."""
    from reportlab.lib.pagesizes import A4, letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
    st = getSampleStyleSheet()
    tampon = io.BytesIO()
    if natif and r:
        doc = SimpleDocTemplate(tampon, pagesize=A4, leftMargin=r['gauche'] * MM, rightMargin=r['droite'] * MM,
                                topMargin=r['haut'] * MM, bottomMargin=r['bas'] * MM)
    else:
        doc = SimpleDocTemplate(tampon, pagesize=letter)
    texte = ("Ce paragraphe d'essai montre où le contenu du document est placé sur votre papier à en-tête. "
             "Il ne doit jamais recouvrir le logo, le cartouche ni le pied de page. ") * 4
    el = [Paragraph(titre, st['Title']), Spacer(1, 8)]
    for i in range(1, 15):
        el += [Paragraph(f'{i}. Constat d\'exemple', st['Heading2']), Paragraph(texte, st['BodyText'])]
    doc.build(el)
    return tampon.getvalue()


@bp.route('/super-admin/client/<int:client_id>/papier-entete/<type_>/apercu')
@super_admin_requis
def apercu(client_id, type_):
    if type_ not in TYPES:
        abort(404)
    c = _client(client_id)
    r = reglage(c.id, type_)
    if not r:
        abort(404)
    natif = type_ == 'lettre_mission'
    pdf = poser(page_exemple(f'Aperçu — {TYPES[type_]}', natif=natif, r=r), c.id, type_, natif=natif)
    return send_file(io.BytesIO(pdf), mimetype='application/pdf', download_name=f'apercu_papier_{type_}.pdf')


def enregistrer(app):
    if 'papier_entete' not in app.blueprints:
        app.register_blueprint(bp)
    app.after_request(_apres_requete)
    app.jinja_env.globals['papiers_entete'] = tous
    app.jinja_env.globals['PAPIER_TYPES'] = TYPES
    app.jinja_env.globals['papier_pypdf_present'] = pypdf_present
