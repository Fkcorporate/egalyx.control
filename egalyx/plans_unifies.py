"""
egalyx/plans_unifies.py — un seul registre des plans d'action : ceux des risques et ceux du contrôle interne N2.

Les deux modules gardent leurs fiches (un plan N2 naît d'une non-conformité, un plan de risque d'un risque ou d'un
dispositif), mais on les suit au même endroit : « Tous les plans d'action » (/plans-action/registre), avec les mêmes
colonnes (origine, rattachement, responsable, échéance, avancement, statut, retard) et les mêmes filtres.
Un plan N2 est rattaché au risque et aux dispositifs testés par son contrôle (référentiel N2 → cartographie) : il
apparaît donc aussi sur la fiche du dispositif et du risque concernés.
Chacun ne voit que ce que ses droits permettent (plans des risques, N2) ou ce dont il est responsable.
"""
from datetime import date

from flask import Blueprint, abort, render_template, request, url_for
from flask_login import current_user

bp = Blueprint('plans_unifies', __name__, url_prefix='/plans-action/registre')

TERMINES = {'termine', 'terminé', 'realise', 'réalisé', 'clos', 'cloture', 'clôturé', 'cloturé', 'complete', 'complété',
            'acheve', 'achevé', 'ferme', 'fermé', 'valide', 'validé', 'done'}
ANNULES = {'annule', 'annulé', 'abandonne', 'abandonné'}
EN_COURS = {'en_cours', 'en cours', 'demarre', 'démarré', 'in_progress', 'en_retard'}


def _m():
    import models
    return models


def _perm(*ps):
    try:
        return current_user.role == 'super_admin' or any(current_user.has_permission(p) for p in ps)
    except Exception:  # noqa: BLE001
        return False


def etat(statut):
    s = (statut or '').strip().lower()
    if s in TERMINES:
        return 'termine'
    if s in ANNULES:
        return 'annule'
    if s in EN_COURS:
        return 'en_cours'
    return 'a_faire'


LIBELLES_ETAT = {'a_faire': 'À faire', 'en_cours': 'En cours', 'termine': 'Terminé', 'annule': 'Annulé'}


def _rattachements_n2(client_id):
    """{non_conformite_id: (planification, référentiel)} pour relier un plan N2 à la cartographie."""
    m = _m()
    out = {}
    q = m.db.session.query(m.NonConformiteC2N.id, m.PlanificationControle) \
        .join(m.PlanificationControle, m.PlanificationControle.execution_id == m.NonConformiteC2N.execution_id)
    if client_id:
        q = q.filter(m.NonConformiteC2N.client_id == client_id)
    for nc_id, pl in q.all():
        out[nc_id] = pl
    return out


def plans_n2_lies(dispositif_id=None, risque_id=None, client_id=None):
    """Plans N2 dont le contrôle teste ce dispositif / couvre ce risque."""
    m = _m()
    q = m.PlanActionC2N.query.filter(m.PlanActionC2N.is_archived.isnot(True))
    if client_id:
        q = q.filter(m.PlanActionC2N.client_id == client_id)
    resultat = []
    liens = _rattachements_n2(client_id)
    for p in q.all():
        pl = liens.get(p.non_conformite_id)
        ref = pl.referentiel if pl is not None else None
        if ref is None:
            continue
        dms = {int(i) for i in (ref.dispositifs_ids or []) if str(i).isdigit()}
        rks = {int(i) for i in (ref.risques_ids or []) if str(i).isdigit()}
        if dispositif_id and dispositif_id in dms or risque_id and (risque_id in rks or any(
                getattr(m.db.session.get(m.DispositifMaitrise, d), 'risque_id', None) == risque_id for d in dms)):
            resultat.append({'plan': p, 'planification': pl, 'referentiel': ref})
    return resultat


def lignes(client_id, filtre_source=None, filtre_etat=None, moi=False, retard=False):
    m = _m()
    voir_risques = _perm('can_view_action_plans', 'can_manage_action_plans', 'can_manage_risks')
    voir_n2 = _perm('can_view_controle_interne_n2', 'can_manage_controle_interne_n2')
    uid = current_user.id
    aujourd_hui = date.today()
    out = []
    noms = {}

    def nom(u_id):
        if not u_id:
            return ''
        if u_id not in noms:
            u = m.db.session.get(m.User, u_id)
            noms[u_id] = u.username if u else ''
        return noms[u_id]

    if filtre_source in (None, '', 'risques'):
        q = m.PlanAction.query.filter(m.PlanAction.is_archived.isnot(True))
        if client_id:
            q = q.filter(m.PlanAction.client_id == client_id)
        for p in q.all():
            if not (voir_risques or p.responsable_id == uid):
                continue
            if p.risque_id:
                r = m.db.session.get(m.Risque, p.risque_id)
                rat = f'Risque {r.reference}' if r else 'Risque'
                lien = url_for('detail_plan_action_risque', plan_id=p.id)
            else:
                rat = 'Plan indépendant' if not p.audit_id else 'Audit'
                lien = url_for('detail_plan_action_risque', plan_id=p.id)
            ech = p.date_fin_prevue
            out.append({'source': 'risques', 'source_libelle': 'Risques', 'reference': p.reference or f'PA-{p.id}',
                        'titre': p.nom or (p.description or '')[:120], 'rattachement': rat,
                        'responsable_id': p.responsable_id, 'responsable': nom(p.responsable_id), 'echeance': ech,
                        'avancement': p.pourcentage_realisation or 0, 'etat': etat(p.statut), 'lien': lien})
    if filtre_source in (None, '', 'n2'):
        liens = _rattachements_n2(client_id)
        q = m.PlanActionC2N.query.filter(m.PlanActionC2N.is_archived.isnot(True))
        if client_id:
            q = q.filter(m.PlanActionC2N.client_id == client_id)
        for p in q.all():
            if not (voir_n2 or p.responsable_id == uid):
                continue
            pl = liens.get(p.non_conformite_id)
            ref = pl.referentiel if pl is not None else None
            rat = f'Contrôle {ref.code_controle}' if ref is not None and ref.code_controle else 'Contrôle N2'
            if ref is not None and ref.dispositifs_ids:
                rat += f' · {len(ref.dispositifs_ids)} dispositif(s)'
            ech = p.date_echeance
            out.append({'source': 'n2', 'source_libelle': 'Contrôle N2', 'reference': p.reference or f'PAC2N-{p.id}',
                        'titre': (p.action_corrective or p.description or '')[:160], 'rattachement': rat,
                        'responsable_id': p.responsable_id, 'responsable': nom(p.responsable_id), 'echeance': ech,
                        'avancement': p.taux_avancement or 0, 'etat': etat(p.statut),
                        'lien': url_for('c2n_detail_plan_action', id=p.id)})
    for l in out:
        e = l['echeance']
        if e is not None and hasattr(e, 'date'):
            e = e.date()
        l['echeance'] = e
        l['en_retard'] = bool(e and e < aujourd_hui and l['etat'] in ('a_faire', 'en_cours'))
    if filtre_etat:
        out = [l for l in out if l['etat'] == filtre_etat]
    if moi:
        out = [l for l in out if l['responsable_id'] == uid]
    if retard:
        out = [l for l in out if l['en_retard']]
    out.sort(key=lambda l: (l['etat'] in ('termine', 'annule'), not l['en_retard'], l['echeance'] or date.max))
    return out


@bp.route('/')
def page():
    from egalyx.commun import client_id_courant
    if not getattr(current_user, 'is_authenticated', False):
        abort(401)
    cid = client_id_courant()
    source = request.args.get('source') or ''
    etat_f = request.args.get('etat') or ''
    moi = request.args.get('moi') == '1'
    retard = request.args.get('retard') == '1'
    tout = lignes(cid)
    filtres = lignes(cid, source or None, etat_f or None, moi, retard) if (source or etat_f or moi or retard) else tout
    stats = {'total': len(tout), 'ouverts': sum(1 for l in tout if l['etat'] in ('a_faire', 'en_cours')),
             'retard': sum(1 for l in tout if l['en_retard']),
             'risques': sum(1 for l in tout if l['source'] == 'risques'), 'n2': sum(1 for l in tout if l['source'] == 'n2')}
    return render_template('egalyx/plans_registre.html', lignes=filtres, stats=stats, source=source, etat=etat_f,
                           moi=moi, retard=retard, libelles=LIBELLES_ETAT)


def enregistrer(app):
    from egalyx.commun import exempter_controle_ancien
    app.register_blueprint(bp)
    exempter_controle_ancien(app, {'plans_unifies.page'})
    app.jinja_env.globals['plans_n2_lies'] = plans_n2_lies
