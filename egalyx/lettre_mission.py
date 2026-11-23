"""
egalyx/lettre_mission.py — lettre de mission : en-têtes par organisation, aperçu, PDF et envoi aux bonnes personnes.

Avant : l'adresse était demandée dans une fenêtre du navigateur (une seule, saisie à la main) ; la route active
n'envoyait rien (envoi commenté) tout en répondant « Email envoyé » ; la lettre n'était relue que depuis le
navigateur (perdue sur un autre poste) et son enregistrement côté serveur n'était pas toujours pris en compte.

Désormais :
  - EN-TÊTES (super admin) : pour chaque organisation, un ou plusieurs modèles (logo, position, couleur, titre,
    lignes d'adresse, mention « confidentiel », pied de page, signature, objet et message de l'e-mail).
    /super-admin/client/<id>/reglages ; l'auditeur choisit le modèle de chaque lettre.
  - DESTINATAIRES : proposés depuis l'audit — audités (participants) et membres externes en « À », chef de
    mission et équipe d'audit en copie, observateurs au choix ; on peut ajouter d'autres adresses. Les réponses
    vont au chef de mission.
  - E-MAIL : mise en page soignée aux couleurs de l'en-tête (logo intégré), la lettre dans le corps du message
    et en PDF joint. Un envoi non parti (serveur d'e-mail absent ou en erreur) est signalé comme tel.
  - HISTORIQUE : chaque envoi (destinataires, copie, objet, modèle, auteur, date, simulé ou non) est conservé.
"""
import io
import logging
import os
import re
from datetime import datetime
from html import escape

from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required

from egalyx.commun import client_id_courant, est_admin_client, est_super_admin, journaliser, super_admin_requis

journal = logging.getLogger('egalyx.lettre_mission')
bp = Blueprint('lettre_mission', __name__)

COURRIEL = re.compile(r'^[^@\s<>,;"]+@[^@\s<>,;"]+\.[A-Za-z]{2,}$')
VARIABLES = ('reference', 'objet', 'audit', 'organisation', 'date_debut', 'date_fin', 'emetteur', 'destinataire')
OBJET_DEFAUT = 'Lettre de mission — {objet} ({reference})'
MESSAGE_DEFAUT = ("Bonjour,\n\nVeuillez trouver ci-dessous et en pièce jointe la lettre de mission relative à "
                  "« {objet} », prévue du {date_debut} au {date_fin}.\n\nNous restons à votre disposition pour "
                  "convenir d'une réunion de lancement.\n\nCordialement,\n{emetteur}")
POSITIONS = ('gauche', 'centre', 'droite', 'aucun')
PIED_POSITIONS = (('gauche', 'À gauche'), ('centre', 'Au centre'), ('droite', 'À droite'))


def _m():
    import models as M
    return M


# ------------------------------------------------------------------ modèles d'en-tête
def modeles(cid, actifs=True):
    M = _m()
    q = M.ModeleLettreMission.query.filter_by(client_id=cid)
    if actifs:
        q = q.filter(M.ModeleLettreMission.actif.isnot(False))
    return q.order_by(M.ModeleLettreMission.est_defaut.desc(), M.ModeleLettreMission.nom).all()


def modele_pour(cid, modele_id=None):
    M = _m()
    if modele_id:
        m = M.db.session.get(M.ModeleLettreMission, int(modele_id))
        if m is not None and m.client_id == cid:
            return m
    liste = modeles(cid)
    return liste[0] if liste else None


def _dossier_logos():
    from flask import current_app
    d = os.path.join(current_app.instance_path, 'lettres_mission')
    os.makedirs(d, exist_ok=True)
    return d


def _chemin_logo_modele(m):
    return os.path.join(_dossier_logos(), f'{m.client_id}_{m.id}.png')


def logo_octets(m, cid):
    """Logo du modèle (s'il en a un propre), sinon celui de l'organisation ; None si aucun."""
    if m is not None and (m.logo_position or 'gauche') == 'aucun':
        return None
    chemins = []
    if m is not None and m.logo_url == 'propre':
        chemins.append(_chemin_logo_modele(m))
    try:
        from egalyx.identite import _chemin_logo
        chemins.append(_chemin_logo(cid))
    except Exception:  # noqa: BLE001
        pass
    for p in chemins:
        if p and os.path.exists(p):
            with open(p, 'rb') as f:
                return f.read()
    return None


class _Variables(dict):
    def __missing__(self, cle):
        return '{' + cle + '}'


def remplir(texte, ctx):
    try:
        return (texte or '').format_map(_Variables(ctx))
    except (ValueError, IndexError):
        return texte or ''


def _date_fr(v):
    if not v:
        return 'à définir'
    try:
        return datetime.strptime(str(v)[:10], '%Y-%m-%d').strftime('%d/%m/%Y')
    except ValueError:
        return str(v)


def contexte(lettre, audit, cid):
    M = _m()
    org = ''
    try:
        from egalyx.identite import nom_affiche
        org = nom_affiche(cid) or ''
    except Exception:  # noqa: BLE001
        c = M.db.session.get(M.Client, cid)
        org = c.nom if c else ''
    return {'reference': lettre.get('reference') or (audit.reference if audit else ''),
            'objet': lettre.get('objet') or (audit.titre if audit else 'Mission d\'audit'),
            'audit': audit.titre if audit else '', 'organisation': org,
            'date_debut': _date_fr(lettre.get('date_debut') or (audit.date_debut_prevue if audit else None)),
            'date_fin': _date_fr(lettre.get('date_fin') or (audit.date_fin_prevue if audit else None)),
            'emetteur': lettre.get('emetteur') or (current_user.nom_affiche if getattr(current_user, 'is_authenticated', False) and hasattr(current_user, 'nom_affiche') else ''),
            'destinataire': lettre.get('destinataire') or ''}


# ------------------------------------------------------------------ document
def html_lettre(lettre, m, cid, audit, logo_src=None, complet=True):
    """La lettre mise en page (aperçu, impression, corps de l'e-mail). logo_src : URL, data URI ou cid:…"""
    ctx = contexte(lettre, audit, cid)
    return render_template('egalyx/lettre_mission_document.html', l=lettre, m=m, ctx=ctx, logo_src=logo_src,
                           complet=complet, couleur=(m.couleur if m and m.couleur else '#1A3C6B'),
                           lignes=[x.strip() for x in ((m.lignes_entete if m else '') or '').splitlines() if x.strip()],
                           date_lettre=_date_fr(lettre.get('date')) if lettre.get('date') else datetime.utcnow().strftime('%d/%m/%Y'))


SECTIONS = (('introduction', 'Contexte'), ('objectifs', 'Objectifs de la mission'), ('perimetre', 'Périmètre'),
            ('equipe', 'Équipe d\'audit'), ('modalites', 'Modalités pratiques'), ('livrables', 'Livrables'))


def pdf_lettre(lettre, m, cid, audit):
    """PDF de la lettre (ReportLab) : en-tête du modèle, sections, signature, pied de page sur chaque page."""
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import HRFlowable, Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    ctx = contexte(lettre, audit, cid)
    couleur = colors.HexColor(m.couleur) if m and m.couleur and re.match(r'^#[0-9A-Fa-f]{6}$', m.couleur) else colors.HexColor('#1A3C6B')
    st = getSampleStyleSheet()
    normal = ParagraphStyle('n', parent=st['Normal'], fontName='Helvetica', fontSize=10, leading=14, alignment=TA_JUSTIFY)
    petit = ParagraphStyle('p', parent=normal, fontSize=8.5, leading=11, textColor=colors.HexColor('#475569'), alignment=0)
    titre_sec = ParagraphStyle('t', parent=normal, fontName='Helvetica-Bold', fontSize=11, textColor=couleur, spaceBefore=8, spaceAfter=3)
    entete_titre = ParagraphStyle('e', parent=normal, fontName='Helvetica-Bold', fontSize=13, textColor=couleur, alignment=0)

    def p(texte, style=normal):
        return Paragraph(escape(texte or '').replace('\n', '<br/>'), style)

    # papier à en-tête PDF du client (egalyx/papier_entete.py) : logo et coordonnées sont déjà imprimés dessus
    try:
        from egalyx.papier_entete import reglage as _papier
        papier = _papier(cid, 'lettre_mission')
    except Exception:  # noqa: BLE001
        papier = None

    elements = []
    logo = None if papier else logo_octets(m, cid)
    position = (m.logo_position if m else 'gauche') or 'gauche'
    bloc = [p(m.titre_entete if m and m.titre_entete else ctx['organisation'], entete_titre)]
    for ligne in ((m.lignes_entete if m else '') or '').splitlines():
        if ligne.strip():
            bloc.append(p(ligne.strip(), petit))
    img = None
    if logo:
        try:
            from reportlab.lib.utils import ImageReader
            lr = ImageReader(io.BytesIO(logo)); w, h = lr.getSize()
            hauteur = 16 * mm; largeur = min(55 * mm, hauteur * w / h)
            img = Image(io.BytesIO(logo), width=largeur, height=largeur * h / w)
        except Exception as e:  # noqa: BLE001
            journal.info('Logo illisible pour le PDF : %s', e)
    if papier:
        bloc = []                                   # pas de titre ni d'adresse : le papier les porte déjà
    if img is not None and position == 'centre':
        img.hAlign = 'CENTER'
        elements += [img, Spacer(1, 3 * mm)]
        for b in bloc:
            b.style = ParagraphStyle('c', parent=b.style, alignment=TA_CENTER)
        elements += bloc
    elif img is not None and position in ('gauche', 'droite'):
        cellules = [[img, bloc]] if position == 'gauche' else [[bloc, img]]
        t = Table(cellules, colWidths=[60 * mm, 110 * mm] if position == 'gauche' else [110 * mm, 60 * mm])
        t.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('ALIGN', (-1, 0), (-1, 0), 'RIGHT' if position == 'droite' else 'LEFT')]))
        elements.append(t)
    else:
        elements += bloc
    if not papier:
        elements += [Spacer(1, 2 * mm), HRFlowable(width='100%', thickness=1.2, color=couleur), Spacer(1, 4 * mm)]
    if m and m.mention_haut:
        elements.append(p(m.mention_haut.upper(), ParagraphStyle('m', parent=petit, fontName='Helvetica-Bold', textColor=colors.HexColor('#b91c1c'), alignment=TA_RIGHT)))
    date_l = _date_fr(lettre.get('date')) if lettre.get('date') else datetime.utcnow().strftime('%d/%m/%Y')
    elements.append(p(f"Réf. : {ctx['reference']}    —    le {date_l}", ParagraphStyle('r', parent=petit, alignment=TA_RIGHT)))
    elements.append(Spacer(1, 4 * mm))
    dest = lettre.get('destinataire') or ''
    if dest or lettre.get('societe'):
        elements.append(p('À l\'attention de :', petit))
        elements.append(p('\n'.join(x for x in (dest, lettre.get('societe') or '') if x), ParagraphStyle('d', parent=normal, fontName='Helvetica-Bold')))
        elements.append(Spacer(1, 4 * mm))
    elements.append(p(f"Objet : {ctx['objet']}", ParagraphStyle('o', parent=normal, fontName='Helvetica-Bold')))
    elements.append(Spacer(1, 3 * mm))
    for cle, titre in SECTIONS:
        if (lettre.get(cle) or '').strip():
            elements += [p(titre, titre_sec), p(lettre.get(cle))]
        if cle == 'perimetre':
            elements += [p('Calendrier', titre_sec),
                         p(f"Du {ctx['date_debut']} au {ctx['date_fin']}" + (f" — durée estimée : {lettre['duree']}" if lettre.get('duree') else ''))]
    if lettre.get('confidentialite') is not False and (lettre.get('confidentialite_texte') or '').strip():
        elements += [p('Confidentialité', titre_sec), p(lettre.get('confidentialite_texte'))]
    elements.append(Spacer(1, 10 * mm))
    signature = (m.signature if m and m.signature else '') or ctx['emetteur']
    elements.append(p(remplir(signature, ctx), ParagraphStyle('s', parent=normal, fontName='Helvetica-Bold', alignment=TA_RIGHT)))

    pied = remplir((m.pied_page if m else '') or '', ctx)

    cote = getattr(m, 'pied_position', None) or 'centre'
    cote = cote if cote in dict(PIED_POSITIONS) else 'centre'

    def ecrire(canvas, x_g, x_d, y, texte, ou):
        if ou == 'gauche':
            canvas.drawString(x_g, y, texte)
        elif ou == 'droite':
            canvas.drawRightString(x_d, y, texte)
        else:
            canvas.drawCentredString((x_g + x_d) / 2, y, texte)

    def pied_de_page(canvas, doc):
        # le numéro de page va du côté opposé au pied (à droite si le pied est centré ou à gauche)
        cote_num = 'gauche' if cote == 'droite' else 'droite'
        texte = pied.replace('\n', ' — ')[:180] if pied else ''
        canvas.saveState(); canvas.setFont('Helvetica', 7.5); canvas.setFillColor(colors.HexColor('#64748b'))
        if papier:
            # le pied du client est imprimé sur le papier : on écrit juste au-dessus, dans la marge laissée libre
            x_g, x_d, y = papier['gauche'] * mm, A4[0] - papier['droite'] * mm, (papier['bas'] - 4) * mm
            if texte:
                ecrire(canvas, x_g, x_d, y, texte, cote)
            ecrire(canvas, x_g, x_d, y if not texte or cote != cote_num else y - 9, f'Page {doc.page}', cote_num if texte else cote)
            canvas.restoreState(); return
        x_g, x_d = 18 * mm, A4[0] - 18 * mm
        canvas.setStrokeColor(couleur); canvas.setLineWidth(0.6)
        canvas.line(x_g, 15 * mm, x_d, 15 * mm)
        canvas.setFillColor(colors.HexColor('#64748b'))
        if texte:
            ecrire(canvas, x_g, x_d, 10.5 * mm, texte, cote)
        ecrire(canvas, x_g, x_d, 6.5 * mm, f'Page {doc.page}', cote_num if texte else cote)
        canvas.restoreState()

    tampon = io.BytesIO()
    marges = (dict(leftMargin=papier['gauche'] * mm, rightMargin=papier['droite'] * mm, topMargin=papier['haut'] * mm,
                   bottomMargin=papier['bas'] * mm) if papier else
              dict(leftMargin=20 * mm, rightMargin=20 * mm, topMargin=16 * mm, bottomMargin=22 * mm))
    doc = SimpleDocTemplate(tampon, pagesize=A4, title=f"Lettre de mission {ctx['reference']}", author=ctx['organisation'], **marges)
    doc.build(elements, onFirstPage=pied_de_page, onLaterPages=pied_de_page)
    if papier:
        from egalyx.papier_entete import poser
        return poser(tampon.getvalue(), cid, 'lettre_mission', natif=True)
    return tampon.getvalue()


def _papier_lettre(cid):
    try:
        from egalyx.papier_entete import reglage
        return reglage(cid, 'lettre_mission')
    except Exception:  # noqa: BLE001
        return None


def apercu_pdf_html(pdf):
    """Page HTML qui affiche un PDF (aperçus en iframe « srcdoc ») : la lettre telle qu'elle sera imprimée."""
    import base64
    donnees = base64.b64encode(pdf).decode()
    return ('<!doctype html><html lang="fr"><head><meta charset="utf-8"><style>html,body{margin:0;height:100%;background:#525659}'
            'iframe{border:0;width:100%;height:100%;display:block}p{font:14px sans-serif;color:#fff;padding:1rem}a{color:#9cc3ff}</style></head>'
            '<body><iframe id="pdf" title="Lettre de mission (PDF)"></iframe>'
            '<p id="secours" hidden>Votre navigateur n\'affiche pas le PDF ici : <a id="lien" download="apercu_lettre_mission.pdf">téléchargez l\'aperçu</a>.</p>'
            '<script>(function(){var b=atob("' + donnees + '"),t=new Uint8Array(b.length);for(var i=0;i<b.length;i++)t[i]=b.charCodeAt(i);'
            'var u=URL.createObjectURL(new Blob([t],{type:"application/pdf"}));document.getElementById("lien").href=u;'
            'try{document.getElementById("pdf").src=u+"#view=FitH";}catch(e){document.getElementById("secours").hidden=false;}'
            'if(!navigator.pdfViewerEnabled&&navigator.pdfViewerEnabled!==undefined){document.getElementById("secours").hidden=false;}})();</script>'
            '</body></html>')


# ------------------------------------------------------------------ destinataires
def _ids(texte):
    return [int(x) for x in re.findall(r'\d+', texte or '')]


def destinataires(audit):
    """Personnes proposées : [{nom, email, role, place: 'a'|'cc'|'', coche}]"""
    M = _m()
    vus, out = set(), []

    def ajouter(u, role, place, coche):
        if u is None or not getattr(u, 'email', None) or u.email.lower() in vus or not getattr(u, 'is_active', True):
            return
        if u.client_id != audit.client_id:
            return
        vus.add(u.email.lower())
        nom = getattr(u, 'nom_affiche', None) or u.username
        out.append({'nom': nom, 'email': u.email, 'role': role, 'place': place, 'coche': coche,
                    'fonction': getattr(u, 'fonction', None) or ''})

    for i in _ids(audit.participants_ids):
        ajouter(M.db.session.get(M.User, i), 'Audité (participant)', 'a', True)
    for x in (audit.membres_externes or []):
        if isinstance(x, dict) and COURRIEL.match((x.get('email') or '').strip()) and x['email'].lower() not in vus:
            vus.add(x['email'].lower())
            nom = ' '.join(v for v in (x.get('prenom'), x.get('nom')) if v) or x['email']
            out.append({'nom': nom, 'email': x['email'].strip(), 'role': 'Membre externe', 'place': 'a', 'coche': True,
                        'fonction': x.get('fonction') or ''})
    ajouter(M.db.session.get(M.User, audit.responsable_id) if audit.responsable_id else None, 'Chef de mission', 'cc', True)
    for i in _ids(audit.equipe_audit_ids):
        ajouter(M.db.session.get(M.User, i), 'Équipe d\'audit', 'cc', True)
    for i in _ids(audit.observateurs_ids):
        ajouter(M.db.session.get(M.User, i), 'Observateur', 'cc', False)
    return out


def peut_envoyer(audit):
    u = current_user
    if est_super_admin() or est_admin_client():
        return True
    try:
        if u.has_permission('can_manage_audit'):
            return True
    except Exception:  # noqa: BLE001
        pass
    return u.id == audit.responsable_id or u.id in _ids(audit.equipe_audit_ids)


# ------------------------------------------------------------------ accès feuille / audit
def _feuille(feuille_id):
    M = _m()
    f = M.db.session.get(M.FeuilleTravail, feuille_id)
    if f is None:
        abort(404)
    cid = client_id_courant()
    if not est_super_admin() and f.client_id != getattr(current_user, 'client_id', None):
        abort(404)
    audit = M.db.session.get(M.Audit, f.audit_id) if f.audit_id else None
    return f, audit, (f.client_id or (audit.client_id if audit else cid))


def _lettre(f):
    return dict((f.contenu or {}).get('lettre_mission') or {})


def _historique(f):
    M = _m()
    out = []
    for e in reversed(list((f.contenu or {}).get('lettre_mission_envoyee') or [])):
        u = M.db.session.get(M.User, e.get('par')) if e.get('par') else None
        x = dict(e)
        x['envoye_par'] = (getattr(u, 'nom_affiche', None) or u.username) if u else 'Système'
        out.append(x)
    return out


@bp.route('/api/feuille-travail/<int:feuille_id>/lettre-mission/donnees')
@login_required
def donnees(feuille_id):
    f, audit, cid = _feuille(feuille_id)
    return jsonify({'lettre': _lettre(f),
                    'modeles': [{'id': m.id, 'nom': m.nom, 'defaut': bool(m.est_defaut)} for m in modeles(cid)],
                    'destinataires': destinataires(audit) if audit else [],
                    'peut_envoyer': bool(audit and peut_envoyer(audit)),
                    'historique': _historique(f)})


@bp.route('/api/feuille-travail/<int:feuille_id>/lettre-mission', methods=['POST'])
@login_required
def enregistrer_lettre(feuille_id):
    """Remplace l'ancien enregistrement (la modification du JSON n'était pas toujours prise en compte)."""
    from sqlalchemy.orm.attributes import flag_modified
    M = _m()
    f, _audit, _cid = _feuille(feuille_id)
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({'success': False, 'error': 'Données manquantes'}), 400
    contenu = dict(f.contenu or {})
    contenu['lettre_mission'] = {k: v for k, v in data.items() if isinstance(k, str) and len(k) < 60}
    contenu['lettre_mission_updated_at'] = datetime.utcnow().isoformat()
    contenu['lettre_mission_updated_by'] = current_user.id
    f.contenu = contenu
    flag_modified(f, 'contenu')
    M.db.session.commit()
    return jsonify({'success': True, 'message': 'Lettre de mission enregistrée', 'updated_at': contenu['lettre_mission_updated_at']})


@bp.route('/api/feuille-travail/<int:feuille_id>/lettre-mission/apercu')
@login_required
def apercu(feuille_id):
    f, audit, cid = _feuille(feuille_id)
    m = modele_pour(cid, request.args.get('modele_id') or _lettre(f).get('modele_id'))
    if _papier_lettre(cid):
        return apercu_pdf_html(pdf_lettre(_lettre(f), m, cid, audit))
    import base64
    logo = logo_octets(m, cid)
    src = 'data:image/png;base64,' + base64.b64encode(logo).decode() if logo else None
    return html_lettre(_lettre(f), m, cid, audit, logo_src=src, complet=True)


@bp.route('/api/feuille-travail/<int:feuille_id>/lettre-mission/pdf')
@login_required
def telecharger_pdf(feuille_id):
    f, audit, cid = _feuille(feuille_id)
    lettre = _lettre(f)
    m = modele_pour(cid, request.args.get('modele_id') or lettre.get('modele_id'))
    ref = re.sub(r'[^\w-]+', '_', lettre.get('reference') or (audit.reference if audit else 'audit'))
    return send_file(io.BytesIO(pdf_lettre(lettre, m, cid, audit)), mimetype='application/pdf',
                     as_attachment=True, download_name=f'lettre_mission_{ref}.pdf')


def _adresses(valeur):
    if isinstance(valeur, str):
        valeur = re.split(r'[,;\s]+', valeur)
    out, refusees = [], []
    for a in valeur or []:
        a = (a or '').strip()
        if not a:
            continue
        (out if COURRIEL.match(a) else refusees).append(a)
    vus, propres = set(), []
    for a in out:
        if a.lower() not in vus:
            vus.add(a.lower()); propres.append(a)
    return propres, refusees


def envoyer(f, audit, cid, a, cc, objet, message, modele_id=None):
    """Envoie la lettre ; retourne (réponse JSON, code HTTP)."""
    from sqlalchemy.orm.attributes import flag_modified
    M = _m()
    if audit is None:
        return {'success': False, 'error': 'Cette feuille n\'est rattachée à aucun audit.'}, 400
    if not peut_envoyer(audit):
        return {'success': False, 'error': 'Seuls le chef de mission, l\'équipe d\'audit et les responsables de l\'audit peuvent envoyer la lettre.'}, 403
    lettre = _lettre(f)
    if not lettre:
        return {'success': False, 'error': 'Enregistrez d\'abord la lettre de mission.'}, 400
    a, refus_a = _adresses(a)
    cc, refus_cc = _adresses(cc)
    if refus_a or refus_cc:
        return {'success': False, 'error': 'Adresse(s) invalide(s) : ' + ', '.join(refus_a + refus_cc)}, 400
    if not a:
        return {'success': False, 'error': 'Choisissez au moins un destinataire principal.'}, 400
    cc = [x for x in cc if x.lower() not in {y.lower() for y in a}]
    m = modele_pour(cid, modele_id or lettre.get('modele_id'))
    ctx = contexte(lettre, audit, cid)
    objet = (objet or '').strip() or remplir((m.objet_email if m and m.objet_email else OBJET_DEFAUT), ctx)
    message = (message or '').strip() or remplir((m.message_email if m and m.message_email else MESSAGE_DEFAUT), ctx)
    logo = logo_octets(m, cid)
    corps_lettre = html_lettre(lettre, m, cid, audit, logo_src='cid:logo' if logo else None, complet=False)
    html = render_template('egalyx/lettre_mission_email.html', message=message, lettre_html=corps_lettre, ctx=ctx,
                           couleur=(m.couleur if m and m.couleur else '#1A3C6B'))
    texte = message + '\n\n— Lettre de mission en pièce jointe (PDF).'
    try:
        pdf = pdf_lettre(lettre, m, cid, audit)
    except Exception as e:  # noqa: BLE001
        journal.warning('PDF de la lettre non généré : %s', e, exc_info=True)
        return {'success': False, 'error': 'Le PDF de la lettre n\'a pas pu être généré.'}, 500
    chef = M.db.session.get(M.User, audit.responsable_id) if audit.responsable_id else None
    reponse_a = chef.email if chef and chef.email else (current_user.email or None)
    from services.email_service import email_service
    simulation = bool(getattr(email_service, 'is_local', False) or getattr(email_service, 'simulation_mode', False))
    ref = re.sub(r'[^\w-]+', '_', ctx['reference'] or 'audit')
    ok = email_service.send_email(a, objet, texte, html_body=html, cc=cc or None, reply_to=reponse_a,
                                  attachments=[(f'lettre_mission_{ref}.pdf', pdf, 'application/pdf')],
                                  inline_images=[('logo', logo, 'png')] if logo else None)
    if not ok:
        return {'success': False, 'error': 'Le serveur d\'e-mail a refusé l\'envoi. Réessayez plus tard ou prévenez votre administrateur.'}, 502
    contenu = dict(f.contenu or {})
    envois = list(contenu.get('lettre_mission_envoyee') or [])
    envois.append({'destinataire': ', '.join(a), 'a': a, 'cc': cc, 'objet': objet, 'modele': m.nom if m else None,
                   'date': datetime.utcnow().isoformat(), 'par': current_user.id, 'simulation': simulation})
    contenu['lettre_mission_envoyee'] = envois
    f.contenu = contenu
    flag_modified(f, 'contenu')
    journaliser('lettre_mission_envoyee', {'audit': audit.reference, 'a': a, 'cc': cc}, client_id=cid)
    M.db.session.commit()
    texte_ok = f"Lettre envoyée à {', '.join(a)}" + (f" (copie : {', '.join(cc)})" if cc else '')
    if simulation:
        texte_ok = ("Serveur d'e-mail non configuré : l'envoi a été SIMULÉ, rien n'est parti. "
                    "Configurez l'adresse d'envoi (HOSTINGER_EMAIL_PASSWORD) pour l'envoi réel.")
    return {'success': True, 'message': texte_ok, 'simulation': simulation}, 200


@bp.route('/api/feuille-travail/<int:feuille_id>/lettre-mission/envoyer', methods=['POST'])
@login_required
def route_envoyer(feuille_id):
    f, audit, cid = _feuille(feuille_id)
    d = request.get_json(silent=True) or {}
    rep, code = envoyer(f, audit, cid, d.get('a') or [], d.get('cc') or [], d.get('objet'), d.get('message'), d.get('modele_id'))
    return jsonify(rep), code


def _ancien_envoi(feuille_id):
    """Anciennes adresses (/envoyer-lettre : {email, message}) : même envoi, destinataire unique."""
    f, audit, cid = _feuille(feuille_id)
    d = request.get_json(silent=True) or {}
    rep, code = envoyer(f, audit, cid, [d.get('email') or ''], [], None, d.get('message'), None)
    return jsonify(rep), code


# ------------------------------------------------------------------ super admin : réglages d'une organisation
def _formulaire_modele(m, form):
    m.nom = (form.get('nom') or '').strip()[:120] or 'Modèle'
    pos = form.get('logo_position') or 'gauche'
    m.logo_position = pos if pos in POSITIONS else 'gauche'
    pied = form.get('pied_position') or 'centre'
    m.pied_position = pied if pied in dict(PIED_POSITIONS) else 'centre'
    couleur = (form.get('couleur') or '').strip()
    m.couleur = couleur if re.match(r'^#[0-9A-Fa-f]{6}$', couleur) else '#1A3C6B'
    for champ, n in (('titre_entete', 200), ('mention_haut', 200), ('objet_email', 250)):
        setattr(m, champ, (form.get(champ) or '').strip()[:n] or None)
    for champ in ('lignes_entete', 'pied_page', 'signature', 'message_email'):
        setattr(m, champ, (form.get(champ) or '').strip()[:4000] or None)
    valeurs = form.getlist('actif') if hasattr(form, 'getlist') else [form.get('actif', '1')]
    m.actif = (not valeurs) or '1' in valeurs        # case + champ caché « 0 » : la case cochée l'emporte
    m.modifie_par_id = current_user.id
    m.updated_at = datetime.utcnow()


def _definir_defaut(m):
    M = _m()
    for x in M.ModeleLettreMission.query.filter_by(client_id=m.client_id).all():
        x.est_defaut = (x.id == m.id)


def _client(client_id):
    M = _m()
    c = M.db.session.get(M.Client, client_id)
    if c is None:
        abort(404)
    return c


@bp.route('/super-admin/organisations/reglages')
@super_admin_requis
def vue_ensemble():
    M = _m()
    from egalyx.localisation import DEVISES, reglages
    clients = M.Client.query.order_by(M.Client.nom).all()
    lignes = []
    for c in clients:
        fuseau, code = reglages(c.id)
        lignes.append({'c': c, 'fuseau': fuseau, 'devise': code, 'devise_choisie': bool(c.devise),
                       'nb_modeles': M.ModeleLettreMission.query.filter_by(client_id=c.id).count()})
    return render_template('egalyx/reglages_organisations.html', lignes=lignes, DEVISES=DEVISES)


@bp.route('/super-admin/client/<int:client_id>/reglages', methods=['GET', 'POST'])
@super_admin_requis
def reglages_client(client_id):
    c = _client(client_id)
    if request.method == 'POST':
        erreur = appliquer_localisation(c, request.form)
        if erreur:
            flash(erreur, 'warning')
        else:
            journaliser('localisation_organisation', {'fuseau': c.fuseau_horaire, 'devise': c.devise}, client_id=c.id)
            _m().db.session.commit()
            flash('Heure et devise enregistrées.', 'success')
        return redirect(url_for('.reglages_client', client_id=c.id))
    return render_template('egalyx/reglages_organisation.html', client=c, modeles=modeles(c.id, actifs=False),
                           **_apercu_localisation(c.id))


def appliquer_localisation(c, form):
    from egalyx.localisation import DEVISES, fuseau_valide
    fuseau = (form.get('fuseau_horaire') or '').strip()
    devise = (form.get('devise') or '').strip().upper()
    if not fuseau_valide(fuseau):
        return f'Fuseau horaire inconnu : « {fuseau} ».'
    if devise and devise not in DEVISES:
        return f'Devise non prise en charge : « {devise} ».'
    c.fuseau_horaire = fuseau
    c.devise = devise or None
    from flask import g
    for cle in [k for k in vars(g) if k.startswith('_eg_loc_')]:
        delattr(g, cle)
    return None


def _apercu_localisation(cid):
    from egalyx.localisation import DEVISES, FUSEAUX_COURANTS, maintenant, montant, reglages
    fuseau, code = reglages(cid)
    return {'fuseau': fuseau, 'devise_code': code, 'heure_locale': maintenant(cid).strftime('%d/%m/%Y à %H:%M'),
            'exemple_montant': montant(1500000.5, cid), 'DEVISES': DEVISES, 'FUSEAUX_COURANTS': FUSEAUX_COURANTS}


@bp.route('/super-admin/client/<int:client_id>/lettres-mission/nouveau', methods=['GET', 'POST'])
@bp.route('/super-admin/client/<int:client_id>/lettres-mission/<int:modele_id>', methods=['GET', 'POST'])
@super_admin_requis
def modele_editer(client_id, modele_id=None):
    M = _m()
    c = _client(client_id)
    m = None
    if modele_id:
        m = M.db.session.get(M.ModeleLettreMission, modele_id)
        if m is None or m.client_id != c.id:
            abort(404)
    if request.method == 'POST':
        nouveau = m is None
        if nouveau:
            m = M.ModeleLettreMission(client_id=c.id, created_at=datetime.utcnow())
            M.db.session.add(m)
        _formulaire_modele(m, request.form)
        M.db.session.flush()
        fichier = request.files.get('logo')
        if fichier and fichier.filename:
            try:
                from egalyx.identite import TAILLE_MAX, preparer_logo
                octets = preparer_logo(fichier.read(TAILLE_MAX + 1))
                with open(_chemin_logo_modele(m), 'wb') as sortie:
                    sortie.write(octets)
                m.logo_url = 'propre'
            except ValueError as e:
                M.db.session.rollback()
                flash(str(e), 'warning')
                return redirect(request.url)
        elif request.form.get('logo_source') == 'organisation':
            m.logo_url = None
        if request.form.get('est_defaut') == '1' or not M.ModeleLettreMission.query.filter(
                M.ModeleLettreMission.client_id == c.id, M.ModeleLettreMission.est_defaut.is_(True), M.ModeleLettreMission.id != m.id).count():
            _definir_defaut(m)
        journaliser('modele_lettre_mission', {'modele': m.nom, 'nouveau': nouveau}, client_id=c.id)
        M.db.session.commit()
        flash('Modèle de lettre de mission enregistré.', 'success')
        return redirect(url_for('.reglages_client', client_id=c.id) + '#lettres')
    exemple = {'reference': 'AUD-2026-014', 'objet': 'Audit du processus achats', 'date': datetime.utcnow().strftime('%Y-%m-%d'),
               'destinataire': 'Mme la Directrice des Achats', 'societe': c.nom,
               'introduction': 'Dans le cadre du plan d\'audit annuel, la Direction de l\'Audit Interne conduira une mission…',
               'objectifs': 'Évaluer la maîtrise des risques du processus achats.', 'date_debut': '2026-12-01', 'date_fin': '2026-12-19',
               'emetteur': 'Le Directeur de l\'Audit Interne'}
    return render_template('egalyx/modele_lettre_form.html', client=c, m=m, exemple=exemple, POSITIONS=POSITIONS,
                           PIED_POSITIONS=PIED_POSITIONS, papier=_papier_lettre(c.id),
                           VARIABLES=VARIABLES, OBJET_DEFAUT=OBJET_DEFAUT, MESSAGE_DEFAUT=MESSAGE_DEFAUT)


@bp.route('/super-admin/client/<int:client_id>/lettres-mission/<int:modele_id>/apercu', methods=['GET', 'POST'])
@super_admin_requis
def modele_apercu(client_id, modele_id):
    """Aperçu (le formulaire en cours d'édition est appliqué sans être enregistré)."""
    M = _m()
    c = _client(client_id)
    if modele_id:
        m = M.db.session.get(M.ModeleLettreMission, modele_id)
        if m is None or m.client_id != c.id:
            abort(404)
    else:
        m = M.ModeleLettreMission(client_id=c.id)
    if request.method == 'POST':
        with M.db.session.no_autoflush:
            temp = M.ModeleLettreMission(client_id=c.id, logo_url=m.logo_url, id=m.id)
            _formulaire_modele(temp, request.form)
            if request.form.get('logo_source') == 'organisation':
                temp.logo_url = None
            m = temp
            if m in M.db.session:
                M.db.session.expunge(m)
    import base64
    logo = logo_octets(m, c.id)
    lettre = {'reference': 'AUD-2026-014', 'objet': 'Audit du processus achats', 'destinataire': 'Mme la Directrice des Achats',
              'societe': c.nom, 'introduction': 'Dans le cadre du plan d\'audit annuel, la Direction de l\'Audit Interne conduira une mission sur le processus achats.',
              'objectifs': 'Évaluer la maîtrise des risques du processus achats et la conformité aux procédures.',
              'perimetre': 'Achats de biens et services de l\'exercice en cours.', 'date_debut': '2026-12-01', 'date_fin': '2026-12-19',
              'emetteur': 'Le Directeur de l\'Audit Interne', 'confidentialite': True,
              'confidentialite_texte': 'Les informations recueillies resteront strictement confidentielles.'}
    if _papier_lettre(c.id):
        return apercu_pdf_html(pdf_lettre(lettre, m, c.id, None))
    return html_lettre(lettre, m, c.id, None, logo_src='data:image/png;base64,' + base64.b64encode(logo).decode() if logo else None)


@bp.route('/super-admin/client/<int:client_id>/lettres-mission/<int:modele_id>/<action>', methods=['POST'])
@super_admin_requis
def modele_action(client_id, modele_id, action):
    M = _m()
    c = _client(client_id)
    m = M.db.session.get(M.ModeleLettreMission, modele_id)
    if m is None or m.client_id != c.id:
        abort(404)
    if action == 'defaut':
        _definir_defaut(m)
        flash(f'« {m.nom} » est désormais le modèle par défaut.', 'success')
    elif action == 'dupliquer':
        copie = M.ModeleLettreMission(client_id=c.id, created_at=datetime.utcnow(), est_defaut=False)
        for col in ('logo_position', 'couleur', 'titre_entete', 'lignes_entete', 'mention_haut', 'pied_page', 'signature',
                    'objet_email', 'message_email', 'actif'):
            setattr(copie, col, getattr(m, col))
        copie.nom = (m.nom + ' (copie)')[:120]
        copie.logo_url = None
        M.db.session.add(copie)
        flash('Modèle dupliqué.', 'success')
    elif action == 'supprimer':
        etait_defaut = m.est_defaut
        try:
            os.remove(_chemin_logo_modele(m))
        except OSError:
            pass
        M.db.session.delete(m)
        M.db.session.flush()
        if etait_defaut:
            reste = M.ModeleLettreMission.query.filter_by(client_id=c.id).order_by(M.ModeleLettreMission.id).first()
            if reste:
                reste.est_defaut = True
        flash('Modèle supprimé.', 'success')
    else:
        abort(404)
    journaliser('modele_lettre_mission_' + action, {'modele': m.nom}, client_id=c.id)
    M.db.session.commit()
    return redirect(url_for('.reglages_client', client_id=c.id) + '#lettres')


# ------------------------------------------------------------------ administrateur de l'organisation : heure et devise
@bp.route('/organisation/heure-devise', methods=['GET', 'POST'])
@login_required
def heure_devise():
    if not (est_admin_client() or est_super_admin()):
        abort(403)
    cid = client_id_courant()
    if not cid:
        flash("Sélectionnez d'abord une organisation à consulter.", 'warning')
        return redirect(url_for('dashboard'))
    c = _client(cid)
    if request.method == 'POST':
        erreur = appliquer_localisation(c, request.form)
        if erreur:
            flash(erreur, 'warning')
        else:
            journaliser('localisation_organisation', {'fuseau': c.fuseau_horaire, 'devise': c.devise}, client_id=c.id)
            _m().db.session.commit()
            flash('Heure et devise enregistrées.', 'success')
        return redirect(url_for('.heure_devise', client_id=cid if est_super_admin() else None))
    return render_template('egalyx/heure_devise.html', client=c, **_apercu_localisation(cid))


def enregistrer(app):
    if 'lettre_mission' not in app.blueprints:
        app.register_blueprint(bp)
    # anciennes adresses de la page d'édition de la feuille de travail
    from flask import current_app  # noqa: F401
    for endpoint in ('api_envoyer_lettre_mission', 'api_envoyer_lettre_mission_email'):
        if endpoint in app.view_functions:
            app.view_functions[endpoint] = login_required(_ancien_envoi)
    if 'api_sauvegarder_lettre_mission' in app.view_functions:
        app.view_functions['api_sauvegarder_lettre_mission'] = login_required(enregistrer_lettre)
