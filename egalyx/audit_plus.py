"""
egalyx/audit_plus.py — compléments d'audit conformes aux pratiques de l'IIA.

1. Rapport provisoire puis définitif, avec la réponse de l'audité constat par constat
   (accord / accord partiel / désaccord, plan d'action, date d'engagement).
   - Rapport provisoire : au moins un constat, et toute l'équipe a signé sa déclaration d'indépendance.
   - Rapport définitif : chaque constat a une réponse, ou la date limite de réponse est dépassée.
     Une fois définitif, réponses et constats (5C) sont figés.
2. Constats « 5C » : critère (référentiel non respecté) et conséquence, en plus du constat et de la cause.
3. Temps passé par auditeur et par activité, comparé au budget de la mission.
4. Déclaration d'indépendance de chaque membre de l'équipe (conflit d'intérêts déclaré => visible).
5. Programme d'audit : approbation seulement depuis « en élaboration ». L'auteur peut approuver son propre
   programme (petites équipes) : c'est tracé « auto-approbation » dans le journal du programme.
   EGALYX_PROGRAMME_DOUBLE_REGARD=1 impose un second gestionnaire (sauf s'il n'y en a qu'un).
   Désapprobation motivée et tracée.
"""
import os
import re
from datetime import date, datetime, timedelta

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from egalyx.commun import a_permission, client_id_courant, decimal, entier, journaliser

bp = Blueprint('audit_plus', __name__, url_prefix='/audit-suivi')

POSITIONS = {'accord': "D'accord", 'partiel': 'Accord partiel', 'desaccord': 'En désaccord'}
ACTIVITES = {'preparation': 'Préparation', 'terrain': 'Travaux sur le terrain', 'rapport': 'Rédaction du rapport',
             'revue': 'Revue / supervision', 'suivi': 'Suivi des recommandations'}
ETATS_RAPPORT = {None: 'Brouillon', 'brouillon': 'Brouillon', 'provisoire': 'Rapport provisoire', 'definitif': 'Rapport définitif'}
DELAI_REPONSE_JOURS = 15
HEURES_PAR_JOUR = 7


def _m():
    import models
    return models


# ---------------------------------------------------------------- accès et équipe
def charger_audit(audit_id):
    m = _m()
    a = m.db.session.get(m.Audit, audit_id)
    if a is None:
        abort(404)
    if getattr(current_user, 'role', None) != 'super_admin':
        if a.client_id != client_id_courant() or not module_audit_actif():
            abort(404)          # autre organisation, ou module Audit interne non souscrit
    return a


def module_audit_actif():
    from egalyx.recommandations import module_actif
    return module_actif('audit')


def est_gestionnaire_audit(u=None):
    u = u or current_user
    return (getattr(u, 'role', None) == 'super_admin' or getattr(u, 'is_client_admin', False)
            or a_permission('can_manage_audit', u=u))


def _ids(texte):
    return {int(x) for x in re.findall(r'\d+', str(texte or ''))}


def equipe(audit):
    """Identifiants des membres de l'équipe d'audit (responsable compris)."""
    ids = _ids(audit.equipe_audit_ids)
    if audit.responsable_id:
        ids.add(audit.responsable_id)
    return ids


def audites(audit):
    """Personnes appelées à répondre : participants de l'audit et responsables des recommandations."""
    m = _m()
    ids = _ids(audit.participants_ids)
    for r in m.Recommandation.query.filter_by(audit_id=audit.id).all():
        if r.responsable_id:
            ids.add(r.responsable_id)
    return ids


def peut_repondre(audit, u=None):
    u = u or current_user
    return audit.etat_rapport == 'provisoire' and (u.id in audites(audit) or est_gestionnaire_audit(u))


def constats(audit):
    m = _m()
    return (m.Constatation.query.filter_by(audit_id=audit.id)
            .filter(m.db.or_(m.Constatation.is_archived == False, m.Constatation.is_archived.is_(None)))  # noqa: E712
            .order_by(m.Constatation.id).all())


def etat_independance(audit):
    m = _m()
    decl = {d.user_id: d for d in m.DeclarationIndependance.query.filter_by(audit_id=audit.id).all()}
    membres = []
    for uid in sorted(equipe(audit)):
        u = m.db.session.get(m.User, uid)
        if u is not None:
            membres.append({'user': u, 'declaration': decl.get(uid)})
    manquantes = [x for x in membres if x['declaration'] is None]
    conflits = [x for x in membres if x['declaration'] is not None and x['declaration'].conflit]
    return {'membres': membres, 'manquantes': manquantes, 'conflits': conflits}


def temps_resume(audit):
    m = _m()
    lignes = m.TempsAudit.query.filter_by(audit_id=audit.id).order_by(m.TempsAudit.date.desc()).all()
    total = round(sum(l.heures or 0 for l in lignes), 2)
    par_user, par_activite = {}, {}
    for l in lignes:
        par_user[l.user.username if l.user else '?'] = par_user.get(l.user.username if l.user else '?', 0) + (l.heures or 0)
        par_activite[l.activite] = par_activite.get(l.activite, 0) + (l.heures or 0)
    mission = m.MissionAudit.query.filter_by(audit_id=audit.id).first()
    budget = getattr(mission, 'budget_estime', None) if mission else None
    return {'lignes': lignes, 'total': total, 'jours': round(total / HEURES_PAR_JOUR, 1), 'par_user': par_user,
            'par_activite': par_activite, 'budget': budget, 'mission': mission}


def suivi_audit(audit):
    """Résumé affiché sur la fiche de l'audit."""
    try:
        if getattr(current_user, 'role', None) != 'super_admin' and not module_audit_actif():
            return None
        cs = constats(audit)
        repondus = [c for c in cs if c.reponse_audite]
        ind = etat_independance(audit)
        tps = temps_resume(audit)
        return {'etat': audit.etat_rapport, 'libelle': ETATS_RAPPORT.get(audit.etat_rapport, 'Brouillon'),
                'constats': len(cs), 'repondus': len(repondus), 'date_limite': audit.date_limite_reponses,
                'independance': ind, 'temps': tps, 'gestionnaire': est_gestionnaire_audit(),
                'peut_repondre': peut_repondre(audit), 'membre': current_user.id in equipe(audit),
                'a_declare': any(x['user'].id == current_user.id and x['declaration'] for x in ind['membres'])}
    except Exception as e:  # la fiche de l'audit ne doit jamais casser à cause de ce bloc
        from flask import current_app
        current_app.logger.warning('Suivi audit %s : %s', getattr(audit, 'id', '?'), e)
        return None


def _notifier(ids, titre, message, audit):
    m = _m()
    for uid in {i for i in ids if i and i != current_user.id}:
        m.db.session.add(m.Notification(destinataire_id=uid, type_notification='audit_rapport', titre=titre[:200],
                                        message=message[:500], entite_type='audit', entite_id=audit.id,
                                        client_id=audit.client_id))


# ---------------------------------------------------------------- rapport provisoire / définitif
@bp.route('/<int:audit_id>/rapport/provisoire', methods=['POST'])
@login_required
def rapport_provisoire(audit_id):
    m = _m()
    a = charger_audit(audit_id)
    if not est_gestionnaire_audit():
        abort(403)
    retour = redirect(url_for('audit_plus.reponses', audit_id=a.id))
    if a.etat_rapport in ('provisoire', 'definitif'):
        flash('Le rapport provisoire a déjà été émis.', 'info')
        return retour
    if not constats(a):
        flash("Aucun constat : il n'y a rien à soumettre aux audités.", 'warning')
        return retour
    ind = etat_independance(a)
    if ind['manquantes']:
        noms = ', '.join(x['user'].username for x in ind['manquantes'])
        flash(f"Déclarations d'indépendance manquantes : {noms}. Chaque membre de l'équipe doit la signer avant l'émission du rapport.", 'warning')
        return retour
    limite = None
    try:
        limite = datetime.strptime(request.form.get('date_limite') or '', '%Y-%m-%d').date()
    except ValueError:
        pass
    a.etat_rapport = 'provisoire'
    a.rapport_provisoire_le, a.rapport_provisoire_par_id = datetime.utcnow(), current_user.id
    a.date_limite_reponses = limite if limite and limite >= date.today() else date.today() + timedelta(days=DELAI_REPONSE_JOURS)
    _notifier(audites(a), f'Rapport provisoire : {a.reference}',
              f"Merci de répondre aux constats de l'audit « {a.titre} » avant le {a.date_limite_reponses.strftime('%d/%m/%Y')}.", a)
    m.db.session.commit()
    journaliser('audit_rapport_provisoire', {'audit_id': a.id})
    flash(f"Rapport provisoire émis : les audités ont jusqu'au {a.date_limite_reponses.strftime('%d/%m/%Y')} pour répondre.", 'success')
    return retour


@bp.route('/<int:audit_id>/rapport/definitif', methods=['POST'])
@login_required
def rapport_definitif(audit_id):
    m = _m()
    a = charger_audit(audit_id)
    if not est_gestionnaire_audit():
        abort(403)
    retour = redirect(url_for('audit_plus.reponses', audit_id=a.id))
    if a.etat_rapport != 'provisoire':
        flash("Émettez d'abord le rapport provisoire : les audités doivent pouvoir répondre.", 'warning')
        return retour
    sans_reponse = [c for c in constats(a) if not c.reponse_audite]
    if sans_reponse and a.date_limite_reponses and date.today() <= a.date_limite_reponses:
        flash(f"{len(sans_reponse)} constat(s) sans réponse et la date limite ({a.date_limite_reponses.strftime('%d/%m/%Y')}) "
              "n'est pas passée : attendez les réponses ou la date limite.", 'warning')
        return retour
    a.etat_rapport = 'definitif'
    a.rapport_definitif_le, a.rapport_definitif_par_id = datetime.utcnow(), current_user.id
    _notifier(audites(a) | equipe(a), f'Rapport définitif : {a.reference}',
              f"Le rapport de l'audit « {a.titre} » est définitif." +
              (f" {len(sans_reponse)} constat(s) sans réponse à la date limite." if sans_reponse else ''), a)
    m.db.session.commit()
    journaliser('audit_rapport_definitif', {'audit_id': a.id, 'sans_reponse': len(sans_reponse)})
    flash('Rapport définitif émis. Les réponses et les constats sont désormais figés.', 'success')
    return retour


@bp.route('/<int:audit_id>/reponses', methods=['GET', 'POST'])
@login_required
def reponses(audit_id):
    m = _m()
    a = charger_audit(audit_id)
    gest = est_gestionnaire_audit()
    if not (gest or current_user.id in audites(a) or current_user.id in equipe(a)):
        abort(403)
    if request.method == 'POST':
        c = m.db.session.get(m.Constatation, entier(request.form.get('constatation_id')))
        if c is None or c.audit_id != a.id:
            abort(404)
        if a.etat_rapport == 'definitif':
            flash('Le rapport est définitif : plus aucune modification.', 'warning')
            return redirect(url_for('audit_plus.reponses', audit_id=a.id))
        quoi = request.form.get('quoi')
        if quoi == '5c':
            if not gest:
                abort(403)
            c.critere = (request.form.get('critere') or '').strip() or None
            c.consequence = (request.form.get('consequence') or '').strip() or None
            c.cause_racine = (request.form.get('cause_racine') or '').strip() or c.cause_racine
            flash('Constat complété.', 'success')
        elif quoi == 'reponse':
            if not peut_repondre(a):
                flash("Les réponses sont ouvertes pendant la phase de rapport provisoire, aux audités désignés.", 'warning')
                return redirect(url_for('audit_plus.reponses', audit_id=a.id))
            position = request.form.get('position')
            texte = (request.form.get('reponse') or '').strip()
            if position not in POSITIONS or len(texte) < 5:
                flash('Indiquez votre position et une réponse (5 caractères au moins).', 'warning')
                return redirect(url_for('audit_plus.reponses', audit_id=a.id) + f'#constat-{c.id}')
            if position in ('accord', 'partiel') and not (request.form.get('plan') or '').strip():
                flash("En cas d'accord, décrivez le plan d'action que vous engagez.", 'warning')
                return redirect(url_for('audit_plus.reponses', audit_id=a.id) + f'#constat-{c.id}')
            c.position_audite, c.reponse_audite = position, texte
            c.plan_audite = (request.form.get('plan') or '').strip() or None
            try:
                c.date_engagement = datetime.strptime(request.form.get('date_engagement') or '', '%Y-%m-%d').date()
            except ValueError:
                c.date_engagement = None
            c.reponse_par_id, c.reponse_le = current_user.id, datetime.utcnow()
            _notifier(equipe(a), f'Réponse reçue : {a.reference}', f"{current_user.username} a répondu au constat {c.reference}.", a)
            flash('Réponse enregistrée.', 'success')
        else:
            abort(400)
        m.db.session.commit()
        return redirect(url_for('audit_plus.reponses', audit_id=a.id) + f'#constat-{c.id}')
    utilisateurs = {u.id: u for u in m.User.query.filter_by(client_id=a.client_id).all()}
    return render_template('egalyx/audit_reponses.html', a=a, constats=constats(a), positions=POSITIONS,
                           etats=ETATS_RAPPORT, gest=gest, peut_repondre=peut_repondre(a), suivi=suivi_audit(a),
                           utilisateurs=utilisateurs, aujourd_hui=date.today(),
                           defaut_limite=date.today() + timedelta(days=DELAI_REPONSE_JOURS))


# ---------------------------------------------------------------- indépendance
@bp.route('/<int:audit_id>/independance', methods=['GET', 'POST'])
@login_required
def independance(audit_id):
    m = _m()
    a = charger_audit(audit_id)
    membre = current_user.id in equipe(a)
    if not (membre or est_gestionnaire_audit()):
        abort(403)
    d = m.DeclarationIndependance.query.filter_by(audit_id=a.id, user_id=current_user.id).first()
    if request.method == 'POST':
        if not membre:
            flash("Seuls les membres de l'équipe d'audit signent une déclaration.", 'warning')
            return redirect(url_for('audit_plus.independance', audit_id=a.id))
        if request.form.get('atteste') != '1':
            flash('Cochez la case pour signer la déclaration.', 'warning')
            return redirect(url_for('audit_plus.independance', audit_id=a.id))
        conflit = request.form.get('conflit') == '1'
        details = (request.form.get('details') or '').strip()
        if conflit and len(details) < 10:
            flash("Décrivez le conflit d'intérêts (10 caractères au moins).", 'warning')
            return redirect(url_for('audit_plus.independance', audit_id=a.id))
        if d is None:
            d = m.DeclarationIndependance(audit_id=a.id, user_id=current_user.id, client_id=a.client_id)
            m.db.session.add(d)
        d.conflit, d.details, d.signe_le = conflit, details or None, datetime.utcnow()
        if conflit:
            _notifier({u for u in [a.responsable_id] if u}, f"Conflit d'intérêts déclaré : {a.reference}",
                      f"{current_user.username} déclare un conflit d'intérêts : {details[:300]}", a)
        m.db.session.commit()
        journaliser('audit_independance', {'audit_id': a.id, 'conflit': conflit})
        flash('Déclaration signée.' + (" Le responsable de l'audit est prévenu du conflit déclaré." if conflit else ''), 'success')
        return redirect(url_for('audit_plus.reponses', audit_id=a.id))
    return render_template('egalyx/audit_independance.html', a=a, d=d, membre=membre, ind=etat_independance(a))


# ---------------------------------------------------------------- temps passé
@bp.route('/<int:audit_id>/temps', methods=['GET', 'POST'])
@login_required
def temps(audit_id):
    m = _m()
    a = charger_audit(audit_id)
    membre = current_user.id in equipe(a)
    gest = est_gestionnaire_audit()
    if not (membre or gest):
        abort(403)
    if request.method == 'POST':
        if request.form.get('supprimer'):
            t = m.db.session.get(m.TempsAudit, entier(request.form.get('supprimer')))
            if t is None or t.audit_id != a.id or not (t.user_id == current_user.id or gest):
                abort(404)
            m.db.session.delete(t)
            m.db.session.commit()
            flash('Saisie supprimée.', 'info')
            return redirect(url_for('audit_plus.temps', audit_id=a.id))
        heures = decimal(request.form.get('heures'))
        try:
            jour = datetime.strptime(request.form.get('date') or '', '%Y-%m-%d').date()
        except ValueError:
            jour = None
        activite = request.form.get('activite') if request.form.get('activite') in ACTIVITES else 'terrain'
        if not jour or heures is None or not (0 < heures <= 24) or jour > date.today():
            flash('Indiquez une date passée ou du jour et un nombre d\'heures entre 0 et 24.', 'warning')
            return redirect(url_for('audit_plus.temps', audit_id=a.id))
        if not membre and not gest:
            abort(403)
        m.db.session.add(m.TempsAudit(audit_id=a.id, client_id=a.client_id, user_id=current_user.id, date=jour,
                                      heures=round(heures, 2), activite=activite,
                                      commentaire=(request.form.get('commentaire') or '').strip()[:300] or None))
        m.db.session.commit()
        flash('Temps enregistré.', 'success')
        return redirect(url_for('audit_plus.temps', audit_id=a.id))
    return render_template('egalyx/audit_temps.html', a=a, tps=temps_resume(a), activites=ACTIVITES, membre=membre,
                           gest=gest, aujourd_hui=date.today(), heures_jour=HEURES_PAR_JOUR)


# ---------------------------------------------------------------- programme d'audit
def _seul_gestionnaire_programme(prog):
    m = _m()
    n = 0
    for u in m.User.query.filter_by(client_id=prog.client_id, is_active=True).all():
        if getattr(u, 'is_operateur', False):
            continue
        try:
            if u.is_client_admin or u.has_permission('can_manage_audit_program'):
                n += 1
        except Exception:
            continue
    return n <= 1


def _envelopper_programme(app):
    m = _m()

    def approuver(original):
        def vue(id):
            if not getattr(current_user, 'is_authenticated', False):
                return original(id)
            prog = m.db.session.get(m.ProgrammeAudit, id)
            if prog is not None and getattr(current_user, 'role', None) != 'super_admin':
                if (prog.statut or 'en_elaboration') not in ('en_elaboration', 'brouillon', 'en_validation'):
                    flash("Seul un programme en élaboration peut être approuvé.", 'warning')
                    return redirect(request.referrer or url_for('liste_programmes_audit'))
                if (prog.created_by == current_user.id and os.environ.get('EGALYX_PROGRAMME_DOUBLE_REGARD', '0') == '1'
                        and not _seul_gestionnaire_programme(prog)):
                    flash("Vous avez préparé ce programme : un autre gestionnaire doit l'approuver.", 'warning')
                    return redirect(request.referrer or url_for('liste_programmes_audit'))
            rep = original(id)
            prog = m.db.session.get(m.ProgrammeAudit, id)
            if prog is not None and prog.statut == 'actif' and prog.approuve_par_id != current_user.id:
                prog.approuve_par_id = current_user.id
                auto = prog.created_by == current_user.id
                m.db.session.add(m.JournalAuditProgramme(
                    programme_id=id, action='auto_approbation' if auto else 'approbation', user_id=current_user.id,
                    details=(f'Approuvé par son auteur ({current_user.username})' if auto
                             else f'Approuvé par {current_user.username}')))
                m.db.session.commit()
            return rep
        return vue

    def desapprouver(original):
        def vue(id):
            if not getattr(current_user, 'is_authenticated', False):
                return original(id)
            prog = m.db.session.get(m.ProgrammeAudit, id)
            raison = (request.form.get('raison') or '').strip()
            if prog is not None:
                if prog.statut != 'actif':
                    flash("Seul un programme approuvé peut être désapprouvé.", 'warning')
                    return redirect(url_for('liste_programmes_audit'))
                if len(raison) < 10:
                    flash('Indiquez le motif de la désapprobation (10 caractères au moins).', 'warning')
                    return redirect(request.referrer or url_for('liste_programmes_audit'))
            ancien_motif_archivage = prog.archive_reason if prog is not None else None
            rep = original(id)
            prog = m.db.session.get(m.ProgrammeAudit, id)
            if prog is not None and prog.statut == 'en_elaboration':
                prog.archive_reason = ancien_motif_archivage   # l'ancienne version y écrivait le motif
                prog.motif_desapprobation = raison
                prog.approuve_par_id = None
                m.db.session.add(m.JournalAuditProgramme(programme_id=id, action='desapprobation', user_id=current_user.id,
                                                         details=raison[:2000]))
                m.db.session.commit()
            return rep
        return vue

    for nom, fabrique in (('approuver_programme_audit', approuver), ('desapprouver_programme_audit', desapprouver)):
        if nom in app.view_functions and not getattr(app.view_functions[nom], '_egalyx', False):
            v = fabrique(app.view_functions[nom])
            v._egalyx = True
            v.__name__ = nom
            app.view_functions[nom] = v


def enregistrer(app):
    app.register_blueprint(bp)
    app.jinja_env.globals['suivi_audit'] = suivi_audit
    app.jinja_env.globals['positions_audite'] = POSITIONS
    _envelopper_programme(app)
