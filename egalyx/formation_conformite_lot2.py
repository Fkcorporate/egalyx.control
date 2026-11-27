"""
egalyx/formation_conformite_lot2.py — Formation à la conformité, lot 2.

  - Bibliothèque Egalyx (super admin) : modules prêts à l'emploi, regroupés en parcours (contrôle interne, conformité),
    que le super admin modifie et publie ; contenu initial dans egalyx/formation_bibliotheque.py (copié une fois) ;
  - Côté client : importer un module ou tout un parcours (copie modifiable), être prévenu d'une nouvelle version et la
    reprendre en un clic, lancer un parcours en une fois (une campagne par module) ;
  - Attestation PDF nominative de chaque formation validée (avec un code de vérification) ;
  - Relances automatiques J-7, J-1, J+1 et J+7 (notification + e-mail à l'adresse du compte), une seule fois même
    avec plusieurs serveurs (réservation en base) ; désactivables campagne par campagne ;
  - KRI : une campagne peut alimenter un indicateur avec le % de personnes qui n'ont pas validé (chaque jour).
"""
import hashlib
import io
import logging
import os
from datetime import date, datetime, timedelta

from flask import abort, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required

from egalyx import formation_bibliotheque as fb
from egalyx import formation_conformite as fc
from egalyx.commun import est_super_admin, journaliser, nom_personne

bp = fc.bp
journal = logging.getLogger(__name__)
PROFILS = {'tous': 'Toutes organisations', 'uemoa': 'Côte d’Ivoire / UEMOA', 'france': 'France / UE'}
ETAPES = [('j7', -7, 'dans 7 jours'), ('j1', -1, 'demain'), ('retard1', 1, 'hier'), ('retard7', 7, 'il y a 7 jours')]


def _m():
    import models
    return models


def _exiger_super_admin():
    if not est_super_admin(current_user):
        abort(403)


# ====================================================================== bibliothèque : amorçage
def amorcer(app):
    """Copie dans la base les modules de formation_bibliotheque.py absents (par code). N'écrase jamais une modification."""
    m = _m()
    try:
        with app.app_context():
            m.ModuleBibliothequeFormation.__table__.create(m.db.engine, checkfirst=True)
            presents = {c for (c,) in m.db.session.query(m.ModuleBibliothequeFormation.code)}
            ajouts = 0
            for x in fb.MODULES:
                if x['code'] in presents:
                    continue
                m.db.session.add(m.ModuleBibliothequeFormation(
                    code=x['code'], titre=x['titre'], resume=x['resume'], contenu=x['contenu'], categorie=x['categorie'],
                    duree_minutes=x['duree_minutes'], score_min=x.get('score_min', 80), questions=x['questions'],
                    parcours=x['parcours'], ordre=x['ordre'], profil=x['profil'], version=1, statut='publie'))
                ajouts += 1
            if ajouts:
                m.db.session.commit()
    except Exception as e:  # noqa: BLE001
        journal.warning('Bibliothèque de formation : amorçage impossible (%r)', e)
        try:
            m.db.session.rollback()
        except Exception:  # noqa: BLE001
            pass


def _profil_client(cid):
    try:
        from egalyx import profil_reglementaire
        return profil_reglementaire.code_profil(cid)
    except Exception:  # noqa: BLE001
        return 'uemoa'


def vue_client(cid):
    """Bibliothèque vue par un client : parcours, modules publiés, état d'import (absent / à jour / nouvelle version)."""
    m = _m()
    profil = _profil_client(cid)
    biblio = m.ModuleBibliothequeFormation.query.filter_by(statut='publie').order_by(
        m.ModuleBibliothequeFormation.parcours, m.ModuleBibliothequeFormation.ordre, m.ModuleBibliothequeFormation.titre).all()
    importes = {}
    for mod in m.ModuleFormationConformite.query.filter(m.ModuleFormationConformite.client_id == cid,
                                                        m.ModuleFormationConformite.origine.isnot(None)):
        if mod.statut != 'archive' or mod.origine not in importes:
            importes[mod.origine] = mod
    parcours = []
    for code, (titre, desc) in fb.PARCOURS.items():
        lignes, autres = [], []
        for b in biblio:
            if b.parcours != code:
                continue
            mod = importes.get(b.code)
            etat = 'absent' if mod is None else ('maj' if (mod.origine_version or 0) < (b.version or 1) else 'ok')
            (lignes if b.profil in ('tous', profil) else autres).append({'b': b, 'mod': mod, 'etat': etat})
        if lignes or autres:
            parcours.append({'code': code, 'titre': titre, 'description': desc, 'lignes': lignes, 'autres': autres,
                             'a_importer': sum(1 for l in lignes if l['etat'] == 'absent'),
                             'maj': sum(1 for l in lignes + autres if l['etat'] == 'maj')})
    return {'parcours': parcours, 'profil': profil, 'profil_libelle': PROFILS.get(profil, profil)}


def _copier(b, mod, cid):
    mod.titre, mod.resume, mod.contenu, mod.video_url = b.titre, b.resume, b.contenu, b.video_url
    mod.categorie, mod.duree_minutes, mod.score_min = b.categorie, b.duree_minutes, b.score_min
    mod.questions = list(b.questions or [])
    mod.origine, mod.origine_version = b.code, b.version or 1


def importer(cid, b):
    """Copie un module de la bibliothèque chez le client (publié, prêt à lancer). Renvoie le module (existant si déjà là)."""
    m = _m()
    deja = m.ModuleFormationConformite.query.filter(m.ModuleFormationConformite.client_id == cid,
                                                    m.ModuleFormationConformite.origine == b.code,
                                                    m.ModuleFormationConformite.statut != 'archive').first()
    if deja:
        return deja, False
    mod = m.ModuleFormationConformite(client_id=cid, statut='publie', version=1, created_by=current_user.id)
    _copier(b, mod, cid)
    m.db.session.add(mod)
    m.db.session.flush()
    return mod, True


def _modules_parcours(cid, code_parcours):
    m = _m()
    profil = _profil_client(cid)
    return [b for b in m.ModuleBibliothequeFormation.query.filter_by(statut='publie', parcours=code_parcours)
            .order_by(m.ModuleBibliothequeFormation.ordre).all() if b.profil in ('tous', profil)]


# ====================================================================== bibliothèque : client
def _bib(code):
    m = _m()
    b = m.ModuleBibliothequeFormation.query.filter_by(code=code, statut='publie').first()
    if b is None:
        abort(404)
    return b


@bp.route('/bibliotheque/<code>/importer', methods=['POST'])
@login_required
def bib_importer(code):
    cid = fc._exiger_gestion()
    m = _m()
    b = _bib(code)
    mod, nouveau = importer(cid, b)
    if nouveau:
        journaliser('formation_bibliotheque_import', {'code': b.code, 'module_id': mod.id, 'version': b.version}, client_id=cid)
    m.db.session.commit()
    flash(f'« {b.titre} » importé : il est publié et prêt à être lancé. Vous pouvez l’adapter.' if nouveau else 'Ce module est déjà importé.',
          'success')
    return redirect(request.form.get('retour') or url_for('formation_conformite.accueil') + '#bibliotheque')


@bp.route('/bibliotheque/parcours/<code>/importer', methods=['POST'])
@login_required
def bib_importer_parcours(code):
    cid = fc._exiger_gestion()
    m = _m()
    if code not in fb.PARCOURS:
        abort(404)
    n = 0
    for b in _modules_parcours(cid, code):
        mod, nouveau = importer(cid, b)
        n += nouveau
    journaliser('formation_bibliotheque_import_parcours', {'parcours': code, 'importes': n}, client_id=cid)
    m.db.session.commit()
    flash(f'{n} module(s) importé(s) : « {fb.PARCOURS[code][0]} » est prêt à être lancé.' if n else 'Tous les modules de ce parcours sont déjà importés.',
          'success')
    return redirect(url_for('formation_conformite.accueil') + '#bibliotheque')


@bp.route('/module/<int:mid>/mettre-a-jour', methods=['POST'])
@login_required
def module_mettre_a_jour(mid):
    cid = fc._exiger_gestion()
    m = _m()
    mod = fc._module(cid, mid)
    b = m.ModuleBibliothequeFormation.query.filter_by(code=mod.origine, statut='publie').first() if mod.origine else None
    if b is None:
        abort(404)
    if (mod.origine_version or 0) >= (b.version or 1):
        flash('Ce module est déjà à jour.', 'success')
    else:
        _copier(b, mod, cid)
        if mod.statut == 'publie':
            mod.version = (mod.version or 1) + 1
        journaliser('formation_module_mis_a_jour', {'module_id': mod.id, 'code': b.code, 'version_bibliotheque': b.version}, client_id=cid)
        m.db.session.commit()
        flash('Module mis à jour depuis la bibliothèque Egalyx (vos modifications précédentes sont remplacées). '
              'Les validations déjà obtenues sont conservées.', 'success')
    return redirect(url_for('formation_conformite.module_form', mid=mod.id))


# ====================================================================== bibliothèque : super admin
@bp.route('/bibliotheque-egalyx')
@login_required
def bib_admin():
    _exiger_super_admin()
    m = _m()
    biblio = m.ModuleBibliothequeFormation.query.order_by(m.ModuleBibliothequeFormation.parcours,
                                                          m.ModuleBibliothequeFormation.ordre, m.ModuleBibliothequeFormation.titre).all()
    imports = dict(m.db.session.query(m.ModuleFormationConformite.origine, m.db.func.count(m.db.distinct(m.ModuleFormationConformite.client_id)))
                   .filter(m.ModuleFormationConformite.origine.isnot(None)).group_by(m.ModuleFormationConformite.origine).all())
    groupes = [(code, titre, [b for b in biblio if b.parcours == code]) for code, (titre, _d) in fb.PARCOURS.items()]
    autres = [b for b in biblio if b.parcours not in fb.PARCOURS]
    if autres:
        groupes.append(('autre', 'Hors parcours', autres))
    return render_template('egalyx/formation_bib_admin.html', groupes=groupes, imports=imports, PROFILS=PROFILS,
                           CATEGORIE=fc.CATEGORIE)


@bp.route('/bibliotheque-egalyx/module/nouveau', methods=['GET', 'POST'])
@bp.route('/bibliotheque-egalyx/module/<int:bid>', methods=['GET', 'POST'])
@login_required
def bib_form(bid=None):
    _exiger_super_admin()
    m = _m()
    b = m.db.session.get(m.ModuleBibliothequeFormation, bid) if bid else None
    if bid and b is None:
        abort(404)
    if request.method == 'POST':
        import json
        import re
        f = request.form
        erreur = None
        try:
            questions = fc.lire_questions(f.get('questions_json'))
        except ValueError as e:
            questions, erreur = None, str(e)
        titre = (f.get('titre') or '').strip()[:200]
        code = b.code if b else re.sub(r'[^a-z0-9_]+', '_', (f.get('code') or '').strip().lower())[:60].strip('_')
        video = (f.get('video_url') or '').strip()[:500]
        if not erreur and not titre:
            erreur = 'Donnez un titre au module.'
        if not erreur and not code:
            erreur = 'Donnez un code au module (lettres, chiffres et _).'
        if not erreur and not b and m.ModuleBibliothequeFormation.query.filter_by(code=code).first():
            erreur = 'Ce code existe déjà.'
        if not erreur and video and not video.startswith('https://'):
            erreur = 'Le lien de la vidéo doit commencer par https://'
        if erreur:
            flash(erreur, 'danger')
            return render_template('egalyx/formation_module_form.html', mod=b, bib=True, saisie=f,
                                   questions=f.get('questions_json') or '[]', CATEGORIES=fc.CATEGORIES, PARCOURS=fb.PARCOURS, PROFILS=PROFILS)
        nouveau = b is None
        if nouveau:
            b = m.ModuleBibliothequeFormation(code=code, version=1, statut='brouillon')
            m.db.session.add(b)
        avant = None if nouveau else (b.contenu, b.questions, b.titre, b.video_url, b.score_min)
        b.titre, b.resume = titre, (f.get('resume') or '').strip()[:2000]
        b.contenu, b.video_url = (f.get('contenu') or '').strip()[:100000], video or None
        b.categorie = f.get('categorie') if f.get('categorie') in fc.CATEGORIE else 'autre'
        b.duree_minutes = max(1, min(600, f.get('duree_minutes', type=int) or 15))
        b.score_min = max(0, min(100, f.get('score_min', type=int) if f.get('score_min') not in (None, '') else 80))
        b.questions = questions
        b.parcours = f.get('parcours') if f.get('parcours') in fb.PARCOURS else None
        b.ordre = max(1, min(99, f.get('ordre', type=int) or 1))
        b.profil = f.get('profil') if f.get('profil') in PROFILS else 'tous'
        b.updated_by = current_user.id
        if not nouveau and b.statut == 'publie' and avant != (b.contenu, b.questions, b.titre, b.video_url, b.score_min):
            b.version = (b.version or 1) + 1
        if f.get('action') == 'publier':
            b.statut = 'publie'
        m.db.session.flush()
        journaliser('formation_bibliotheque_enregistre', {'code': b.code, 'version': b.version, 'statut': b.statut})
        m.db.session.commit()
        flash(('Module publié : visible par tous les clients qui ont l’e-learning.' if f.get('action') == 'publier'
               else 'Module enregistré.') + (f' Version {b.version} : les clients qui l’ont importé verront « nouvelle version ».'
                                              if not nouveau and b.version > 1 and avant and b.statut == 'publie' else ''), 'success')
        return redirect(url_for('formation_conformite.bib_form', bid=b.id))
    return render_template('egalyx/formation_module_form.html', mod=b, bib=True, saisie=None,
                           questions=json_dumps(b.questions if b else []), CATEGORIES=fc.CATEGORIES, PARCOURS=fb.PARCOURS, PROFILS=PROFILS)


def json_dumps(x):
    import json
    return json.dumps(x or [], ensure_ascii=False)


@bp.route('/bibliotheque-egalyx/module/<int:bid>/etat', methods=['POST'])
@login_required
def bib_etat(bid):
    _exiger_super_admin()
    m = _m()
    b = m.db.session.get(m.ModuleBibliothequeFormation, bid)
    if b is None:
        abort(404)
    action = request.form.get('action')
    if action == 'retirer':
        b.statut = 'brouillon'
        flash('Module retiré de la bibliothèque : les clients ne le voient plus (les copies déjà importées restent).', 'success')
    elif action == 'publier':
        b.statut = 'publie'
        flash('Module publié.', 'success')
    elif action == 'supprimer':
        if m.ModuleFormationConformite.query.filter_by(origine=b.code).count():
            flash('Des clients ont importé ce module : retirez-le plutôt (leurs copies restent).', 'warning')
            return redirect(url_for('formation_conformite.bib_form', bid=b.id))
        journaliser('formation_bibliotheque_supprime', {'code': b.code})
        m.db.session.delete(b)
        m.db.session.commit()
        flash('Module supprimé de la bibliothèque.', 'success')
        return redirect(url_for('formation_conformite.bib_admin'))
    else:
        abort(400)
    journaliser('formation_bibliotheque_' + action, {'code': b.code})
    m.db.session.commit()
    return redirect(url_for('formation_conformite.bib_form', bid=b.id))


# ====================================================================== attestation PDF
def code_verification(a, mod, u):
    base = f'{a.id}|{a.user_id}|{a.campagne_id}|{a.reussi_le.isoformat() if a.reussi_le else ""}|{a.version_module}|{mod.titre}|{getattr(u, "email", "")}'
    return hashlib.sha256(base.encode('utf-8')).hexdigest()[:12].upper()


@bp.route('/attestation/<int:aid>.pdf')
@login_required
def attestation(aid):
    m = _m()
    a = m.db.session.get(m.AffectationFormationConformite, aid)
    if a is None or a.statut != 'reussi':
        abort(404)
    proprietaire = a.user_id == current_user.id and a.client_id == current_user.client_id and fc.peut_suivre()
    if not proprietaire:
        from egalyx.commun import client_id_courant
        if client_id_courant() != a.client_id or not fc.peut_voir_suivi(cid=a.client_id):
            abort(404)
    c = m.db.session.get(m.CampagneFormationConformite, a.campagne_id)
    mod = m.db.session.get(m.ModuleFormationConformite, c.module_id)
    u = m.db.session.get(m.User, a.user_id)
    client = m.db.session.get(m.Client, a.client_id)
    pdf = _pdf_attestation(a, c, mod, u, client)
    journaliser('formation_attestation', {'affectation_id': a.id}, client_id=a.client_id, valider=True)
    nom = ''.join(ch if ch.isalnum() else '_' for ch in (nom_personne(u) or 'attestation'))[:40]
    return send_file(io.BytesIO(pdf), as_attachment=True, download_name=f'attestation_{nom}_{a.id}.pdf', mimetype='application/pdf')


def _pdf_attestation(a, c, mod, u, client):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas
    largeur, hauteur = landscape(A4)
    tampon = io.BytesIO()
    cv = canvas.Canvas(tampon, pagesize=(largeur, hauteur))
    cv.setTitle(f'Attestation de formation — {nom_personne(u)}')
    bleu = colors.HexColor('#1F4E79')
    cv.setStrokeColor(bleu); cv.setLineWidth(2.5); cv.rect(12 * mm, 12 * mm, largeur - 24 * mm, hauteur - 24 * mm)
    cv.setLineWidth(.6); cv.rect(15 * mm, 15 * mm, largeur - 30 * mm, hauteur - 30 * mm)
    x = largeur / 2
    cv.setFillColor(colors.HexColor('#5B6B7F')); cv.setFont('Helvetica', 11)
    cv.drawCentredString(x, hauteur - 35 * mm, (getattr(client, 'nom', '') or '').upper()[:90])
    cv.setFillColor(bleu); cv.setFont('Helvetica-Bold', 30)
    cv.drawCentredString(x, hauteur - 55 * mm, 'Attestation de formation')
    cv.setFillColor(colors.black); cv.setFont('Helvetica', 13)
    cv.drawCentredString(x, hauteur - 75 * mm, 'Nous attestons que')
    cv.setFont('Helvetica-Bold', 22)
    cv.drawCentredString(x, hauteur - 89 * mm, (nom_personne(u) or '')[:70])
    if getattr(u, 'fonction', None):
        cv.setFont('Helvetica', 11); cv.setFillColor(colors.HexColor('#5B6B7F'))
        cv.drawCentredString(x, hauteur - 97 * mm, u.fonction[:90]); cv.setFillColor(colors.black)
    cv.setFont('Helvetica', 13)
    cv.drawCentredString(x, hauteur - 111 * mm, 'a suivi et validé la formation')
    cv.setFont('Helvetica-Bold', 16)
    titre = mod.titre or ''
    if len(titre) > 80:
        coupe = titre[:80].rfind(' ')
        cv.drawCentredString(x, hauteur - 123 * mm, titre[:coupe]); cv.drawCentredString(x, hauteur - 131 * mm, titre[coupe + 1:][:80])
        y = hauteur - 145 * mm
    else:
        cv.drawCentredString(x, hauteur - 123 * mm, titre); y = hauteur - 137 * mm
    cv.setFont('Helvetica', 11)
    lignes = [f'Validée le {a.reussi_le.strftime("%d/%m/%Y à %H:%M")} (heure UTC)' if a.reussi_le else '',
              (f'Score obtenu : {a.meilleur_score} % (minimum requis : {mod.score_min} %)' if mod.questions else 'Validation par lecture du module'),
              f'Campagne : {c.titre}  —  version du module : {a.version_module or mod.version}']
    for l in lignes:
        if l:
            cv.drawCentredString(x, y, l[:120]); y -= 7 * mm
    cv.setFont('Helvetica', 8.5); cv.setFillColor(colors.HexColor('#5B6B7F'))
    cv.drawString(22 * mm, 22 * mm, f'Référence : FC-{a.id:06d}   Code de vérification : {code_verification(a, mod, u)}')
    cv.drawRightString(largeur - 22 * mm, 22 * mm, f'Document généré par Egalyx Control le {datetime.now().strftime("%d/%m/%Y")}')
    cv.showPage(); cv.save()
    return tampon.getvalue()


# ====================================================================== relances automatiques et KRI
def _reserver(cid_campagne, cle):
    """Réserve l'envoi « cle » pour une campagne : True pour un seul serveur, même s'ils sont plusieurs."""
    m = _m()
    t = m.CampagneFormationConformite.__table__
    r = m.db.session.execute(t.update().where(t.c.id == cid_campagne)
                             .where((t.c.derniere_relance_auto.is_(None)) | (t.c.derniere_relance_auto != cle))
                             .values(derniere_relance_auto=cle))
    m.db.session.commit()
    return r.rowcount == 1


def _courriel(u, sujet, texte):
    try:
        from egalyx import courriel
        if getattr(u, 'email', None):
            return courriel.envoyer(u.email, sujet, texte)
    except Exception as e:  # noqa: BLE001
        journal.warning('Formation : e-mail de relance non envoyé (%r)', e)
    return False


def relancer_automatiquement(aujourd_hui=None):
    """Envoie les rappels du jour (J-7, J-1, J+1, J+7) et met à jour les KRI reliés. Renvoie un résumé."""
    m = _m()
    jour = aujourd_hui or date.today()
    resume = {'relances': 0, 'personnes': 0, 'kri': 0}
    for c in m.CampagneFormationConformite.query.filter_by(statut='active').all():
        if not fc.module_actif(c.client_id):
            continue
        # --- KRI : une mesure par jour
        if c.kri_id and c.derniere_mesure_kri != jour:
            kri = m.db.session.get(m.KRI, c.kri_id)
            if kri is not None and kri.client_id == c.client_id:
                st = fc.chiffres(c, aujourd_hui=jour)
                if st['total']:
                    t = m.CampagneFormationConformite.__table__
                    r = m.db.session.execute(t.update().where(t.c.id == c.id)
                                             .where((t.c.derniere_mesure_kri.is_(None)) | (t.c.derniere_mesure_kri != jour))
                                             .values(derniere_mesure_kri=jour))
                    if r.rowcount == 1:
                        m.db.session.add(m.MesureKRI(kri_id=kri.id, valeur=float(100 - st['taux']), date_mesure=datetime.utcnow(),
                                                     client_id=c.client_id, created_by=c.created_by,
                                                     commentaire=f'Formation « {c.titre} » : {st["total"] - st["reussi"]} personne(s) '
                                                                 f'sur {st["total"]} n’ont pas validé ({st["en_retard"]} en retard)'))
                        resume['kri'] += 1
                    m.db.session.commit()
        # --- relances
        if c.relances_auto is False or not c.date_limite:
            continue
        ecart = (jour - c.date_limite).days
        etape = next((e for e in ETAPES if e[1] == ecart), None)
        if etape is None:
            continue
        cle = f'{etape[0]}:{jour.isoformat()}'
        if not _reserver(c.id, cle):
            continue
        aff = m.AffectationFormationConformite.query.filter_by(campagne_id=c.id).all()
        cibles = [a.user_id for a in aff if a.statut != 'reussi']
        if not cibles:
            continue
        en_retard = ecart > 0
        limite = c.date_limite.strftime('%d/%m/%Y')
        titre = (f'Formation en retard : {c.titre}' if en_retard else f'Rappel : formation à valider avant le {limite}')[:200]
        message = (f'La date limite ({limite}) est dépassée : merci de valider votre formation « {c.titre} » dès que possible '
                   f'dans « Mes formations ».' if en_retard else
                   f'Votre formation « {c.titre} » est à valider avant le {limite} ({etape[2]}). Retrouvez-la dans « Mes formations ».')
        with _contexte_url():
            fc._notifier(c.client_id, cibles, titre, message, c.id, urgence='important' if en_retard else 'normal')
            journaliser('formation_relance_auto', {'campagne_id': c.id, 'etape': etape[0], 'personnes': len(cibles)}, client_id=c.client_id)
        c.derniere_relance = datetime.utcnow()
        m.db.session.commit()
        users = m.User.query.filter(m.User.id.in_(cibles)).all()
        for u in users:
            _courriel(u, titre, f'Bonjour {nom_personne(u)},\n\n{message}\n\nCe message est envoyé automatiquement par Egalyx Control.')
        resume['relances'] += 1
        resume['personnes'] += len(cibles)
    return resume


class _contexte_url:
    """url_for hors requête (planificateur) : ouvre un contexte de requête si besoin."""
    def __enter__(self):
        from flask import current_app, has_request_context
        self.ctx = None
        if not has_request_context():
            self.ctx = current_app.test_request_context('/')
            self.ctx.push()
        return self

    def __exit__(self, *exc):
        if self.ctx is not None:
            self.ctx.pop()
        return False


def _demarrer(app):
    if os.environ.get('EGALYX_COLLECTE_AUTO', '1') == '0' or app.config.get('TESTING') or getattr(app, '_egalyx_formation_relances', False):
        return
    try:
        from apscheduler.schedulers.background import BackgroundScheduler

        def tache():
            with app.app_context():
                try:
                    relancer_automatiquement()
                except Exception as e:  # noqa: BLE001
                    journal.warning('Formation : relances automatiques en échec (%r)', e)
                    _m().db.session.rollback()

        sch = BackgroundScheduler(daemon=True)
        sch.add_job(tache, 'interval', hours=1, id='egalyx_formation_relances', replace_existing=True, max_instances=1,
                    coalesce=True, next_run_time=datetime.now() + timedelta(minutes=5))
        sch.start()
        app._egalyx_formation_relances = True
    except Exception as e:  # noqa: BLE001
        journal.warning('Formation : planificateur non démarré (%r)', e)


def enregistrer(app):
    amorcer(app)
    app.jinja_env.globals['formation_bib_admin_visible'] = lambda: est_super_admin(current_user) if current_user.is_authenticated else False
    _demarrer(app)
