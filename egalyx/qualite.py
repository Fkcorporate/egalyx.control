"""
egalyx/qualite.py — refonte du module Qualité (plans qualité, audits qualité, non-conformités, actions).

1. Droits cohérents (une seule grille, appliquée avant chaque page /qualite) :
   voir = « Voir la qualité » (nouvelle) ou une permission de gestion qualité ;
   plans (plans, non-conformités, actions, formations, réunions, documents) = « Gérer la qualité » ou « Gérer les plans qualité » ;
   audits (audits qualité, grilles, réponses) = « Gérer la qualité » ou « Gérer les audits qualité ».
   Le responsable d'une non-conformité ou d'une action peut la mettre à jour ; l'équipe d'un audit qualité peut y répondre.
   Avant : la plupart des pages acceptaient « Gérer les audits » (module Audit) et 12 pages (dont modifier un audit,
   y répondre, modifier une formation) s'ouvraient sans aucun droit qualité, opérateurs compris.
2. Validation du plan : brouillon → soumis → validé par le valideur désigné (ou un gestionnaire qualité).
   La case « Plan validé » du formulaire ne valide plus rien ; un plan ne devient « actif » qu'une fois validé ;
   modifier un plan validé retire la validation (à revalider).
3. Non-conformités : clôture seulement après vérification d'efficacité jugée « efficace » ; qui a vérifié est tracé ;
   « Créer une action » transforme la non-conformité en action d'amélioration suivie (lien conservé).
4. Revues de direction : une réunion « revue de direction » tenue met à jour la date de dernière revue et calcule la
   suivante selon la périodicité du plan.
5. « Ma semaine » : plans à valider, revues à tenir, non-conformités et actions confiées, audits qualité à mener.
"""
import os
from datetime import date, datetime, timedelta

from flask import Blueprint, abort, flash, g, has_request_context, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from egalyx.commun import a_permission, entier, est_admin_client, journaliser

bp = Blueprint('qualite_suivi', __name__, url_prefix='/qualite-suivi')

VOIR = ('can_view_quality', 'can_manage_quality', 'can_manage_quality_plans', 'can_manage_quality_audits')
PLANS = ('can_manage_quality', 'can_manage_quality_plans')
AUDITS = ('can_manage_quality', 'can_manage_quality_audits')
NIVEAUX = {'voir': VOIR, 'plans': PLANS, 'audits': AUDITS}
MOIS_REVUE = {'mensuelle': 1, 'trimestrielle': 3, 'semestrielle': 6, 'annuelle': 12}
CHAMPS_CONTENU = ('titre', 'description', 'date_debut', 'date_fin', 'procedures_applicables', 'controles_cles',
                  'documents_reference', 'objectifs_qualite', 'indicateurs_cles', 'pole_id', 'direction_id', 'service_id')

DROITS = {
    # consultation
    'liste_plans_qualite': 'voir', 'detail_plan_qualite': 'plan', 'alertes_revues_qualite': 'voir',
    'detail_formation_qualite': 'voir', 'detail_reunion_qualite': 'voir', 'rapport_complet_plan_qualite': 'voir',
    'export_rapport_qualite_pdf': 'voir', 'voir_rapport_qualite': 'voir', 'liste_non_conformites_qualite': 'voir',
    'liste_audits_qualite': 'voir', 'detail_audit_qualite': 'audit_vue', 'rapport_audit_qualite': 'audit_vue',
    'liste_grilles_audit_qualite': 'voir', 'detail_grille_audit_qualite': 'voir', 'detail_non_conformite': 'voir',
    'export_audit_qualite_pdf': 'voir', 'liste_formations_qualite': 'voir', 'liste_reunions_qualite': 'voir',
    'cartographie_qualite': 'voir', 'liste_cartographie_risques': 'voir', 'export_all_cartographie_risques_excel': 'voir',
    'export_plan_qualite_pdf': 'voir', 'export_cartographie_risque_pdf': 'voir',
    'export_all_cartographie_risques_pdf': 'voir', 'liste_fichiers_plan_qualite': 'voir',
    'telecharger_fichier_plan_qualite': 'voir', 'api_analyser_plan_qualite': 'voir',
    # plans, non-conformités, actions, formations, réunions (création / modification : même en affichage)
    **{e: 'plans' for e in (
        'nouveau_plan_qualite', 'modifier_plan_qualite', 'archiver_plan_qualite', 'restaurer_plan_qualite',
        'nouvelle_formation_qualite', 'modifier_formation_qualite', 'supprimer_formation_qualite',
        'nouvelle_reunion_qualite', 'modifier_reunion_qualite', 'supprimer_reunion_qualite',
        'nouvelle_non_conformite', 'supprimer_non_conformite', 'nouvelle_action_amelioration',
        'supprimer_action_amelioration', 'upload_fichier_plan_qualite', 'supprimer_fichier_plan_qualite',
        'nouvelle_cartographie_risque', 'modifier_cartographie_risque', 'supprimer_cartographie_risque',
        'api_generer_objectifs_smart', 'api_suggerer_description_plan', 'api_generer_objectifs', 'api_generer_indicateurs',
        'api_suggerer_maturite', 'api_generer_amelioration', 'api_generer_plan_complet', 'api_suggerer_assurance')},
    # audits qualité
    'nouvel_audit_qualite': 'audits', 'modifier_audit_qualite': 'audits', 'supprimer_audit_qualite': 'audits',
    'repondre_audit_qualite': 'equipe_audit', 'nouvelle_grille_audit_qualite': 'audits',
    'modifier_grille_audit_qualite': 'audits', 'supprimer_grille_audit_qualite': 'audits',
    'activer_grille_audit_qualite': 'audits', 'desactiver_grille_audit_qualite': 'audits',
    'ajouter_non_conformite_qualite': 'equipe_audit',
    # responsables
    'modifier_non_conformite': 'nc', 'modifier_action_amelioration': 'action', 'changer_statut_action_qualite': 'action',
}


def _m():
    import models
    return models


# ---------------------------------------------------------------- droits
def peut(niveau, u=None):
    return a_permission(*NIVEAUX[niveau], u=u or current_user)


def _objet(modele, cle):
    m = _m()
    oid = (request.view_args or {}).get(cle)
    o = m.db.session.get(getattr(m, modele), oid) if oid else None
    return o if o is not None and getattr(o, 'client_id', None) in (None, current_user.client_id) else None


def droit(endpoint=None):
    """Utilisé par les pages d'app.py à la place de l'ancien « Gérer les audits ou la qualité »."""
    endpoint = endpoint or (request.endpoint if has_request_context() else None)
    niveau = DROITS.get(endpoint) or ('voir' if request.method in ('GET', 'HEAD') else 'plans')
    uid = getattr(current_user, 'id', None)
    if niveau == 'nc':
        nc = _objet('NonConformite', 'nc_id')
        return peut('plans') or bool(nc and nc.responsable_id == uid)
    if niveau == 'action':
        a = _objet('ActionAmeliorationQualite', 'action_id')
        return peut('plans') or bool(a and a.responsable_id == uid)
    if niveau == 'plan':          # la fiche : « Voir la qualité », ou valideur / responsable de ce plan
        p = _objet('PlanQualiteFonction', 'plan_id')
        return peut('voir') or bool(p and uid in (p.valideur_id, p.responsable_conformite_id, p.responsable_revue_id))
    if niveau in ('equipe_audit', 'audit_vue'):
        au = _objet('AuditQualite', 'audit_id')
        equipe = [str(x.get('id') if isinstance(x, dict) else x) for x in ((au.equipe_audit or []) if au else [])]
        membre = bool(au and (au.auditeur_principal_id == uid or str(uid) in equipe))
        return membre or peut('audits') or (niveau == 'audit_vue' and peut('voir'))
    return peut(niveau)


def _garde():
    ep = request.endpoint or ''
    if not (request.path.startswith('/qualite/') or request.path.startswith('/api/qualite')) or ep.startswith('qualite_suivi.'):
        return None
    if not getattr(current_user, 'is_authenticated', False) or getattr(current_user, 'role', None) == 'super_admin':
        return None
    if droit(ep):
        return None
    if request.path.startswith('/api/') or request.is_json:
        from flask import jsonify
        return jsonify({'success': False, 'error': 'permission_insuffisante'}), 403
    flash("Vous n'avez pas la permission nécessaire pour cette page qualité.", 'warning')
    return redirect(url_for('liste_plans_qualite') if peut('voir') and ep != 'liste_plans_qualite' else url_for('dashboard'))


def charger_plan(plan_id):
    m = _m()
    p = m.db.session.get(m.PlanQualiteFonction, plan_id)
    if p is None or (getattr(current_user, 'role', None) != 'super_admin' and p.client_id != current_user.client_id):
        abort(404)
    return p


def etat(p):
    if p.est_valide:
        return 'valide'
    if p.soumis_le and not p.motif_renvoi:
        return 'en_relecture'
    return 'brouillon'


ETATS = {'brouillon': 'Brouillon', 'en_relecture': 'Soumis à validation', 'valide': 'Validé'}


def peut_valider(p, u=None):
    u = u or current_user
    if etat(p) != 'en_relecture':
        return False
    if p.valideur_id:
        return p.valideur_id == u.id
    if not (peut('plans', u) or est_admin_client(u)):
        return False
    return not (os.environ.get('EGALYX_QUALITE_DOUBLE_REGARD') == '1' and p.soumis_par_id == u.id)


def _utilisateur(uid):
    m = _m()
    return m.db.session.get(m.User, uid) if uid else None


def _notifier(ids, titre, message, entite_type, entite_id, client_id, type_='qualite'):
    m = _m()
    for uid in {i for i in ids if i and i != getattr(current_user, 'id', None)}:
        m.db.session.add(m.Notification(destinataire_id=uid, type_notification=type_, titre=titre[:200], message=message,
                                        entite_type=entite_type, entite_id=entite_id, client_id=client_id))


def _gestionnaires(cid):
    m = _m()
    return [u.id for u in m.User.query.filter_by(client_id=cid, is_active=True).all()
            if a_permission(*PLANS, u=u) or est_admin_client(u)]


def _plus_mois(d, n):
    import calendar
    a, mo = d.year + (d.month - 1 + n) // 12, (d.month - 1 + n) % 12 + 1
    return date(a, mo, min(d.day, calendar.monthrange(a, mo)[1]))


def _circuit():
    g.egalyx_qualite_circuit = True


# ---------------------------------------------------------------- informations pour la fiche
def suivi(p):
    m = _m()
    cid = p.client_id
    ncs = m.NonConformite.query.filter_by(plan_qualite_id=p.id).all()
    actions = m.ActionAmeliorationQualite.query.filter_by(plan_qualite_id=p.id, is_archived=False).all()
    j = date.today()
    alertes = []
    if p.date_prochaine_revue and p.date_prochaine_revue < j:
        alertes.append(('danger', f"Revue de direction en retard (prévue le {p.date_prochaine_revue.strftime('%d/%m/%Y')})."))
    if p.date_fin and p.date_fin < j and (p.statut or '') == 'actif':
        alertes.append(('warning', f"Période du plan terminée le {p.date_fin.strftime('%d/%m/%Y')} : à clore ou prolonger."))
    ouvertes = [n for n in ncs if n.statut != 'close']
    en_retard = [a for a in actions if a.statut not in ('terminee',) and a.date_echeance and a.date_echeance < j]
    if en_retard:
        alertes.append(('warning', f"{len(en_retard)} action(s) d'amélioration en retard."))
    a_verifier = [n for n in ouvertes if n.statut in ('en_traitement', 'verifiee') and _actions_terminees(n, actions)]
    if a_verifier:
        alertes.append(('info', f"{len(a_verifier)} non-conformité(s) dont les actions sont terminées : vérifiez l'efficacité puis clôturez."))
    if etat(p) == 'brouillon' and p.motif_renvoi:
        alertes.append(('warning', f"Renvoyé : {p.motif_renvoi}"))
    valideurs = []
    if peut('plans'):
        valideurs = [u for u in m.User.query.filter_by(client_id=cid, is_active=True).order_by(m.User.username).all()
                     if not getattr(u, 'is_operateur', False)]
    return {'etat': etat(p), 'libelle': ETATS[etat(p)], 'valideur': _utilisateur(p.valideur_id),
            'valide_par': _utilisateur(p.valide_par_id), 'soumis_par': _utilisateur(p.soumis_par_id),
            'gerer': peut('plans'), 'peut_valider': peut_valider(p), 'valideurs': valideurs, 'alertes': alertes,
            'nb_nc_ouvertes': len(ouvertes), 'nb_actions': len(actions),
            'nb_actions_terminees': sum(1 for a in actions if a.statut == 'terminee')}


def _actions_terminees(nc, actions):
    liees = [a for a in actions if a.non_conformite_id == nc.id]
    return bool(liees) and all(a.statut == 'terminee' for a in liees)


def nc_suivi(nc):
    m = _m()
    actions = m.ActionAmeliorationQualite.query.filter_by(non_conformite_id=nc.id, is_archived=False).all()
    return {'actions': actions, 'gerer': peut('plans'), 'verifie_par': _utilisateur(nc.verifie_par_id),
            'peut_creer_action': (peut('plans') or nc.responsable_id == current_user.id) and nc.statut != 'close'}


# ---------------------------------------------------------------- circuit de validation du plan
@bp.route('/plan/<int:plan_id>/valideur', methods=['POST'])
@login_required
def choisir_valideur(plan_id):
    m = _m()
    p = charger_plan(plan_id)
    if not peut('plans'):
        abort(403)
    vid = entier(request.form.get('valideur_id'))
    u = m.db.session.get(m.User, vid) if vid else None
    p.valideur_id = u.id if u is not None and u.client_id == p.client_id and u.is_active else None
    m.db.session.commit()
    flash('Valideur enregistré.' if p.valideur_id else 'Aucun valideur désigné : un gestionnaire qualité validera.', 'success')
    return redirect(url_for('detail_plan_qualite', plan_id=p.id))


@bp.route('/plan/<int:plan_id>/soumettre', methods=['POST'])
@login_required
def soumettre(plan_id):
    p = charger_plan(plan_id)
    if not peut('plans'):
        abort(403)
    if etat(p) != 'brouillon':
        flash('Ce plan est déjà soumis ou validé.', 'info')
        return redirect(url_for('detail_plan_qualite', plan_id=p.id))
    manque = [n for n, ok in (('responsable conformité', p.responsable_conformite_id), ('objectifs qualité', p.objectifs_qualite),
                              ('période', p.date_debut and p.date_fin)) if not ok]
    if manque:
        flash('Avant de soumettre, complétez : ' + ', '.join(manque) + '.', 'warning')
        return redirect(url_for('detail_plan_qualite', plan_id=p.id))
    _circuit()
    p.soumis_le, p.soumis_par_id, p.motif_renvoi = datetime.utcnow(), current_user.id, None
    _notifier([p.valideur_id] if p.valideur_id else _gestionnaires(p.client_id), f'Plan qualité à valider : {p.reference}',
              f'{current_user.username} soumet « {p.titre} » à validation.', 'plan_qualite', p.id, p.client_id,
              'qualite_a_valider')
    journaliser('qualite_plan_soumis', {'plan_id': p.id})
    _m().db.session.commit()
    flash('Plan soumis à validation.', 'success')
    return redirect(url_for('detail_plan_qualite', plan_id=p.id))


@bp.route('/plan/<int:plan_id>/valider', methods=['POST'])
@login_required
def valider(plan_id):
    p = charger_plan(plan_id)
    if not peut_valider(p):
        flash('Vous ne pouvez pas valider ce plan (seul le valideur désigné le peut).', 'warning')
        return redirect(url_for('detail_plan_qualite', plan_id=p.id))
    _circuit()
    p.est_valide, p.date_validation, p.valide_par_id, p.motif_renvoi = True, datetime.utcnow(), current_user.id, None
    if (p.statut or 'brouillon') == 'brouillon':
        p.statut = 'actif'
    if not p.date_prochaine_revue:
        p.date_prochaine_revue = _plus_mois(date.today(), MOIS_REVUE.get(p.periode_revue or 'annuelle', 12))
    _notifier([p.soumis_par_id, p.responsable_conformite_id], f'Plan qualité validé : {p.reference}',
              f'{current_user.username} a validé « {p.titre} ».', 'plan_qualite', p.id, p.client_id, 'qualite_valide')
    journaliser('qualite_plan_valide', {'plan_id': p.id, 'auto_validation': p.soumis_par_id == current_user.id})
    _m().db.session.commit()
    flash('Plan validé : il est actif.', 'success')
    return redirect(url_for('detail_plan_qualite', plan_id=p.id))


@bp.route('/plan/<int:plan_id>/renvoyer', methods=['POST'])
@login_required
def renvoyer(plan_id):
    p = charger_plan(plan_id)
    if not peut_valider(p):
        abort(403)
    motif = (request.form.get('motif') or '').strip()
    if not motif:
        flash("Indiquez ce qu'il faut revoir.", 'warning')
        return redirect(url_for('detail_plan_qualite', plan_id=p.id))
    _circuit()
    p.motif_renvoi = motif
    _notifier([p.soumis_par_id, p.responsable_conformite_id], f'Plan qualité à revoir : {p.reference}',
              f'{current_user.username} : {motif}', 'plan_qualite', p.id, p.client_id, 'qualite_a_revoir')
    journaliser('qualite_plan_renvoye', {'plan_id': p.id, 'motif': motif})
    _m().db.session.commit()
    flash('Plan renvoyé en brouillon.', 'info')
    return redirect(url_for('detail_plan_qualite', plan_id=p.id))


# ---------------------------------------------------------------- non-conformité → action
@bp.route('/non-conformite/<int:nc_id>/action', methods=['POST'])
@login_required
def nc_vers_action(nc_id):
    m = _m()
    nc = m.db.session.get(m.NonConformite, nc_id)
    if nc is None or (current_user.role != 'super_admin' and nc.client_id not in (None, current_user.client_id)):
        abort(404)
    p = charger_plan(nc.plan_qualite_id)
    if not (peut('plans') or nc.responsable_id == current_user.id):
        abort(403)
    intitule = (request.form.get('intitule') or nc.action_corrective or nc.titre or '').strip()[:200]
    try:
        echeance = datetime.strptime(request.form.get('echeance') or '', '%Y-%m-%d').date()
    except ValueError:
        echeance = nc.echeance_traitement or _plus_mois(date.today(), 1)
    n = m.ActionAmeliorationQualite.query.filter_by(plan_qualite_id=p.id).count()
    a = m.ActionAmeliorationQualite(
        reference=f'{p.reference}-AC{n + 1:02d}', intitule=intitule or f'Traiter {nc.reference}',
        description=f"Action issue de la non-conformité {nc.reference} : {nc.titre}", plan_qualite_id=p.id,
        date_echeance=echeance, priorite='haute' if nc.gravite in ('majeure', 'critique') else 'moyenne',
        statut='a_faire', responsable_id=entier(request.form.get('responsable_id')) or nc.responsable_id,
        non_conformite_id=nc.id, created_by=current_user.id, client_id=p.client_id)
    m.db.session.add(a)
    if nc.statut == 'ouverte':
        nc.statut = 'en_traitement'
    m.db.session.flush()
    _notifier([a.responsable_id], f'Action qualité confiée : {a.reference}', f'{a.intitule} (échéance {echeance.strftime("%d/%m/%Y")})',
              'action_qualite', a.id, p.client_id, 'qualite_action')
    m.db.session.commit()
    flash(f'Action {a.reference} créée et rattachée à la non-conformité.', 'success')
    return redirect(url_for('detail_non_conformite', nc_id=nc.id))


# ---------------------------------------------------------------- règles à l'enregistrement
def _signaler(message):
    try:
        flash(message, 'info')
    except RuntimeError:
        pass


def _avant_flush(session, _ctx, _inst):
    m = _m()
    from sqlalchemy import inspect as sa_inspect
    try:
        circuit = bool(getattr(g, 'egalyx_qualite_circuit', False))
        uid = getattr(current_user, 'id', None) if getattr(current_user, 'is_authenticated', False) else None
    except RuntimeError:
        return                                  # hors requête : pas de contrôle
    for o in list(session.new) + list(session.dirty):
        if isinstance(o, m.PlanQualiteFonction):
            _regles_plan(o, session, circuit)
        elif isinstance(o, m.NonConformite):
            _regles_nc(o, session, uid)
        elif isinstance(o, m.ReunionQualite):
            _regles_reunion(o, session)


def _regles_plan(p, session, circuit):
    from sqlalchemy import inspect as sa_inspect
    if circuit:
        return
    if p in session.new:
        if p.est_valide:
            p.est_valide, p.date_validation, p.valide_par_id = False, None, None
            _signaler('La validation se fait par le circuit (bouton « Soumettre à validation » de la fiche).')
        if (p.statut or 'brouillon') == 'actif':
            p.statut = 'brouillon'
        return
    insp = sa_inspect(p)
    h = insp.attrs.est_valide.history
    if h.added and h.added[0] and not (h.deleted and h.deleted[0]):
        p.est_valide = False
        for c in ('date_validation', 'valide_par_id'):
            hh = insp.attrs[c].history
            setattr(p, c, hh.deleted[0] if hh.deleted else None)
        _signaler('La case « Plan validé » ne valide plus le plan : utilisez « Soumettre à validation ».')
    hs = insp.attrs.statut.history
    if hs.added and hs.added[0] == 'actif' and not p.est_valide:
        p.statut = hs.deleted[0] if hs.deleted else 'brouillon'
        _signaler('Le plan devient « actif » à sa validation.')
    if p.est_valide:
        def change(c):
            hh = insp.attrs[c].history
            return hh.has_changes() and (hh.deleted or [None])[0] != (hh.added or [None])[0]
        if any(change(c) for c in CHAMPS_CONTENU if c in insp.attrs):
            p.est_valide, p.soumis_le = False, None
            _signaler('Plan modifié après validation : il doit être revalidé.')


def _regles_nc(nc, session, uid):
    from sqlalchemy import inspect as sa_inspect
    insp = sa_inspect(nc)
    hv = insp.attrs.verification_efficacite.history
    if hv.added and hv.added[0] and (not hv.deleted or hv.deleted[0] != hv.added[0]):
        nc.verifie_par_id = uid
    if nc.statut == 'close':
        hs = insp.attrs.statut.history
        vient_de_clore = nc in session.new or (hs.added and hs.added[0] == 'close' and (not hs.deleted or hs.deleted[0] != 'close'))
        if vient_de_clore and not (nc.verification_efficacite and nc.efficace):
            nc.statut = (hs.deleted[0] if hs.deleted and hs.deleted[0] != 'close' else 'en_traitement')
            nc.date_cloture = None
            _signaler("Clôture refusée : renseignez la vérification d'efficacité et indiquez que l'action est efficace.")
        elif vient_de_clore and not nc.date_cloture:
            nc.date_cloture = datetime.utcnow()


def _regles_reunion(r, session):
    from sqlalchemy import inspect as sa_inspect
    if (r.type_reunion or '') != 'revue_direction' or (r.statut or '') not in ('tenue', 'realisee', 'terminee'):
        return
    hs = sa_inspect(r).attrs.statut.history
    if r not in session.new and not (hs.added and (not hs.deleted or hs.deleted[0] != hs.added[0])):
        return
    m = _m()
    p = session.get(m.PlanQualiteFonction, r.plan_qualite_id)
    if p is None:
        return
    jour = r.date_reunion.date() if isinstance(r.date_reunion, datetime) else (r.date_reunion or date.today())
    if not p.date_derniere_revue or jour >= p.date_derniere_revue:
        p.date_derniere_revue = jour
        p.date_prochaine_revue = _plus_mois(jour, MOIS_REVUE.get(p.periode_revue or 'annuelle', 12))


# ---------------------------------------------------------------- « Ma semaine »
def taches(u, ajout, horizon, aujourd_hui, lien):
    m = _m()
    if not u.client_id:
        return
    gerer = a_permission(*PLANS, u=u)
    for p in m.PlanQualiteFonction.query.filter_by(client_id=u.client_id).all():
        if getattr(p, 'is_archived', False):
            continue
        url = lien('detail_plan_qualite', plan_id=p.id)
        if etat(p) == 'en_relecture' and peut_valider(p, u):
            ajout('Plan qualité à valider', p.titre, p.reference, p.soumis_le, url, 1)
        if (gerer or u.id in (p.responsable_revue_id, p.responsable_conformite_id)) and p.est_valide \
                and p.date_prochaine_revue and p.date_prochaine_revue <= horizon:
            ajout('Revue de direction', p.titre, f'{p.reference} · revue qualité', p.date_prochaine_revue, url)
    for nc in m.NonConformite.query.filter(m.NonConformite.responsable_id == u.id, m.NonConformite.statut != 'close').all():
        ajout('Non-conformité', nc.titre, f'{nc.reference} · {nc.gravite or ""}', nc.echeance_traitement or nc.date_ouverture,
              lien('detail_non_conformite', nc_id=nc.id), 1 if nc.gravite in ('majeure', 'critique') else 2)
    for a in m.ActionAmeliorationQualite.query.filter(m.ActionAmeliorationQualite.responsable_id == u.id,
                                                      m.ActionAmeliorationQualite.statut != 'terminee',
                                                      m.ActionAmeliorationQualite.is_archived == False).all():  # noqa: E712
        ajout('Action qualité', a.intitule, a.reference, a.date_echeance, lien('modifier_action_amelioration', action_id=a.id))
    for au in m.AuditQualite.query.filter(m.AuditQualite.auditeur_principal_id == u.id,
                                          m.AuditQualite.statut.in_(('planifie', 'en_cours'))).all():
        if au.date_prevue and au.date_prevue <= horizon:
            ajout('Audit qualité', au.titre, au.reference, au.date_prevue, lien('detail_audit_qualite', audit_id=au.id))


def _migrer_permissions(app):
    """Une seule fois : ceux qui géraient la qualité grâce à « Gérer les audits » la gardent (Gérer la qualité)."""
    from egalyx.ia import reglages, ecrire_reglage
    with app.app_context():
        try:
            if reglages().get('migration_permissions_qualite'):
                return
            m = _m()
            for u in m.User.query.filter(m.User.client_id.isnot(None)).all():
                p = dict(u.permissions or {})
                if p.get('can_manage_audit') and not any(p.get(k) for k in VOIR):
                    p['can_manage_quality'] = True
                    p['can_view_quality'] = True
                    u.permissions = p
                elif any(p.get(k) for k in VOIR[1:]) and not p.get('can_view_quality'):
                    p['can_view_quality'] = True
                    u.permissions = p
            m.db.session.commit()
            ecrire_reglage('migration_permissions_qualite', True)
        except Exception as e:
            try:
                _m().db.session.rollback()
            except Exception:
                pass
            app.logger.warning('Migration des permissions qualité reportée : %s', e)


def enregistrer(app):
    from egalyx.commun import exempter_controle_ancien
    exempter_controle_ancien(app, DROITS)
    import models as m
    from sqlalchemy import event
    from sqlalchemy.orm import Session
    app.register_blueprint(bp)
    app.before_request(_garde)
    if not getattr(m, '_egalyx_qualite_flush', False):
        event.listen(Session, 'before_flush', _avant_flush)
        m._egalyx_qualite_flush = True
    app.jinja_env.globals['qualite_suivi'] = suivi
    app.jinja_env.globals['qualite_nc_suivi'] = nc_suivi
    _migrer_permissions(app)
