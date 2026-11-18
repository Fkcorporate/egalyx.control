"""
egalyx/plans_suivi.py — progression et suites d'un plan d'action, appliquées quel que soit l'écran.

Avant, chaque écran (audit, risque, indépendant, espace de travail, opérateur…) recalculait à sa façon :
une sous-action à 100 % ne terminait pas toujours le plan, un plan terminé ne prévenait pas toujours sa
recommandation, et un écran d'audit fermait la recommandation directement, sans la validation prévue
dans le registre des recommandations.

Règles, appliquées au moment de l'enregistrement (avant chaque écriture en base) :

  Sous-action   progression 100 %  -> « terminée » (date de fin) ; entre 1 et 99 % -> « en cours » ;
                0 % -> « à faire » (une sous-action annulée ou en retard garde son statut).
                Statut mis à « terminée » -> 100 %.
  Plan          avec sous-actions : sa progression est la moyenne de ses sous-actions.
                Marqué « terminé » -> 100 %, et ses sous-actions restantes sont terminées.
                100 % -> « terminé » (date de fin) ; redescend sous 100 % -> rouvert (« en cours »).
  Recommandation liée (audit interne ou contrôle N2)
                avancement = moyenne de ses plans d'action ;
                tous ses plans terminés -> CLÔTURE DEMANDÉE (jamais clôturée d'office) : un gestionnaire
                la valide ou la refuse dans le registre des recommandations ; tracé et notifié ;
                un plan rouvert retire une demande de clôture encore en attente.
  Constatation  toutes ses recommandations clôturées -> « close » ; une recommandation rouverte -> « en action ».
"""
import logging
from datetime import date, datetime

from sqlalchemy import event, inspect

journal = logging.getLogger('egalyx.plans_suivi')
_INSTALLE = []


def _change(obj, attr):
    try:
        h = inspect(obj).attrs[attr].history
        return bool(h.added) or bool(h.deleted)
    except Exception:  # noqa: BLE001
        return False


def _avant(obj, attr):
    """Valeur avant modification (None si inconnue)."""
    try:
        h = inspect(obj).attrs[attr].history
        if h.deleted:
            return h.deleted[0]
        if h.unchanged:
            return h.unchanged[0]
    except Exception:  # noqa: BLE001
        pass
    return None


def _utilisateur():
    try:
        from flask_login import current_user
        if current_user and current_user.is_authenticated:
            return current_user.id, current_user.username
    except Exception:  # noqa: BLE001
        pass
    return None, None


# ------------------------------------------------------------------ sous-actions
def _regler_sous_action(sa):
    """Statut <-> progression d'une sous-action modifiée."""
    p = sa.pourcentage_realisation or 0
    if _change(sa, 'statut') and sa.statut == 'termine' and p < 100:
        sa.pourcentage_realisation = p = 100
    if not _change(sa, 'pourcentage_realisation') and not _change(sa, 'statut'):
        return
    if sa.statut in ('annule', 'annulee'):
        return
    if p >= 100:
        if sa.statut != 'termine':
            sa.statut = 'termine'
        if not sa.date_fin_reelle:
            sa.date_fin_reelle = date.today()
    elif _change(sa, 'pourcentage_realisation'):
        if sa.statut == 'termine' or (p > 0 and sa.statut in (None, '', 'a_faire')) or (p == 0 and sa.statut == 'en_cours'):
            sa.statut = 'en_cours' if p > 0 else 'a_faire'
        sa.date_fin_reelle = None


# ------------------------------------------------------------------ plans
def _regler_plan(session, plan, sous_actions_touchees):
    """Progression et statut d'un plan ; retourne (terminé_maintenant, rouvert)."""
    etait = _avant(plan, 'statut') if _change(plan, 'statut') else plan.statut
    vivantes = [s for s in (plan.sous_actions or []) if s not in session.deleted]
    marque_termine = _change(plan, 'statut') and plan.statut == 'termine' and etait != 'termine'
    if marque_termine:
        for s in vivantes:
            if s.statut not in ('annule', 'annulee') and (s.pourcentage_realisation or 0) < 100:
                s.pourcentage_realisation, s.statut = 100, 'termine'
                s.date_fin_reelle = s.date_fin_reelle or date.today()
        plan.pourcentage_realisation = 100
    elif vivantes:
        moy = round(sum(s.pourcentage_realisation or 0 for s in vivantes) / len(vivantes))
        if moy != (plan.pourcentage_realisation or 0):
            plan.pourcentage_realisation = moy
    p = plan.pourcentage_realisation or 0
    # le statut ne suit la progression que si elle vient de changer (pas lors d'une simple modification de texte)
    progression_bouge = _change(plan, 'pourcentage_realisation') or sous_actions_touchees
    if progression_bouge and plan.statut not in ('annule', 'suspendu'):
        if p >= 100 and plan.statut != 'termine':
            plan.statut = 'termine'
        elif p < 100 and plan.statut == 'termine' and not marque_termine:
            plan.statut = 'en_cours' if p > 0 else 'en_attente'
            plan.date_fin_reelle = None
        elif 0 < p < 100 and plan.statut in (None, '', 'en_attente', 'a_faire'):
            plan.statut = 'en_cours'
    if plan.statut == 'termine' and not plan.date_fin_reelle:
        plan.date_fin_reelle = date.today()
    maintenant = plan.statut
    return (maintenant == 'termine' and etait != 'termine'), (etait == 'termine' and maintenant != 'termine')


def _regler_plan_n2(plan):
    """Plan d'action du contrôle N2 : 100 % <-> « terminée » ; retourne (terminé_maintenant, rouvert)."""
    etait = _avant(plan, 'statut') if _change(plan, 'statut') else plan.statut
    fini_avant = etait in ('terminee', 'termine')
    if _change(plan, 'statut') and plan.statut in ('terminee', 'termine') and not fini_avant:
        plan.taux_avancement = 100
    elif _change(plan, 'taux_avancement'):
        t = plan.taux_avancement or 0
        if t >= 100 and plan.statut not in ('terminee', 'termine', 'annulee', 'annule'):
            plan.statut = 'terminee'
        elif t < 100 and plan.statut in ('terminee', 'termine'):
            plan.statut = 'en_cours'
            plan.date_fin_reelle = None
    fini = plan.statut in ('terminee', 'termine')
    if fini and not plan.date_fin_reelle:
        plan.date_fin_reelle = date.today()
    return (fini and not fini_avant), (fini_avant and not fini)


# ------------------------------------------------------------------ recommandations
def _etat(p):
    """(progression, terminé) d'un plan d'action, quel que soit son modèle."""
    if hasattr(p, 'taux_avancement') and not hasattr(p, 'pourcentage_realisation'):      # PlanActionC2N
        return (p.taux_avancement or 0), p.statut in ('terminee', 'termine')
    return (p.pourcentage_realisation or 0), p.statut == 'termine'


def _plans_de(session, M, champ, valeur, plan_courant):
    plans = {('pa', p.id): p for p in M.PlanAction.query.filter(getattr(M.PlanAction, champ) == valeur).all()}
    if champ == 'recommandation_c2n_id' and hasattr(M, 'PlanActionC2N'):
        plans.update({('n2', p.id): p for p in M.PlanActionC2N.query.filter_by(recommandation_id=valeur).all()})
    cle = ('n2' if not hasattr(plan_courant, 'pourcentage_realisation') else 'pa', plan_courant.id or id(plan_courant))
    plans[cle] = plan_courant
    return [p for p in plans.values() if p not in session.deleted and not getattr(p, 'is_archived', False)]


def _suivre_reco(session, M, plan, termine, rouvert):
    uid, nom = _utilisateur()
    if not hasattr(plan, 'pourcentage_realisation'):          # plan d'action du contrôle N2
        liens = (('c2n', 'recommandation_id', 'recommandation', 'RecommandationC2N'),)
    else:
        liens = (('audit', 'recommandation_id', 'recommandation', 'Recommandation'),
                 ('c2n', 'recommandation_c2n_id', 'recommandation_c2n', 'RecommandationC2N'))
    for source, champ, attr_rel, modele in liens:
        rid = getattr(plan, champ, None)
        if not rid:
            continue
        r = getattr(plan, attr_rel, None) or session.get(getattr(M, modele), rid)
        if r is None:
            continue
        cloturee = (r.statut == 'termine') if source == 'audit' else (r.statut in ('realisee', 'rejetee'))
        if cloturee:
            continue
        champ_liste = 'recommandation_c2n_id' if source == 'c2n' else champ
        plans = _plans_de(session, M, champ_liste, rid, plan)
        moy = round(sum(_etat(p)[0] for p in plans) / len(plans)) if plans else 0
        if source == 'audit':
            if (r.taux_avancement or 0) != moy:
                r.taux_avancement = moy
            if moy > 0 and (r.statut or 'a_traiter') == 'a_traiter':
                r.statut = 'en_cours'
        else:
            if (r.progression or 0) != moy:
                r.progression = moy
            if moy > 0 and (r.statut or 'proposee') == 'proposee':
                r.statut = 'en_cours'
        cid = getattr(r, 'client_id', None) or plan.client_id
        ref = r.reference if source == 'audit' else f'N2-REC-{r.id}'
        if all(_etat(p)[1] for p in plans) and termine and not r.demande_cloture_le:
            r.demande_cloture_le = datetime.utcnow()
            r.demande_cloture_par_id = uid or plan.responsable_id
            r.motif_refus_cloture = None
            texte = f"Demande automatique : plan d'action {plan.reference} terminé" + (f' (par {nom})' if nom else '')
            if source == 'c2n' and (r.statut or 'proposee') == 'proposee':
                r.statut = 'en_cours'
            if cid:
                session.add(M.SuiviRecommandation(client_id=cid, source=source, recommandation_id=r.id, action='demande_cloture',
                                                  progression=100, commentaire=texte, user_id=uid))
                try:
                    from egalyx.recommandations import _gestionnaires, _notifier
                    _notifier([g for g in _gestionnaires(cid, source) if g != uid], f'Clôture à valider : {ref}',
                              f"Tous les plans d'action de cette recommandation sont terminés ({plan.reference}).", r.id, cid)
                except Exception as e:  # noqa: BLE001
                    journal.warning('Notification de clôture non envoyée (%s) : %s', ref, e)
        elif rouvert and r.demande_cloture_le:
            r.demande_cloture_le = r.demande_cloture_par_id = None
            if cid:
                session.add(M.SuiviRecommandation(client_id=cid, source=source, recommandation_id=r.id, action='avancement',
                                                  progression=moy, user_id=uid,
                                                  commentaire=f"Demande de clôture retirée : plan d'action {plan.reference} rouvert"))


def _suivre_constatation(session, M, reco):
    """Recommandation d'audit clôturée / rouverte -> statut de sa constatation."""
    cid_ = getattr(reco, 'constatation_id', None)
    if not cid_:
        return
    c = getattr(reco, 'constatation', None) or session.get(M.Constatation, cid_)
    if c is None:
        return
    recos = [x for x in M.Recommandation.query.filter_by(constatation_id=c.id).all() if x not in session.deleted]
    if reco not in recos:
        recos.append(reco)
    if all(x.statut == 'termine' for x in recos):
        if c.statut != 'clos':
            c.statut = 'clos'
    elif c.statut == 'clos':
        c.statut = 'en_action'


# ------------------------------------------------------------------ branchement
def _avant_ecriture(session, _contexte, _instances):
    import models as M
    try:
        with session.no_autoflush:
            plans, touches = {}, set()
            for obj in list(session.new) + list(session.dirty):
                if isinstance(obj, M.SousAction):
                    if obj in session.new or _change(obj, 'pourcentage_realisation') or _change(obj, 'statut'):
                        _regler_sous_action(obj)
                        plan = obj.plan_action or (session.get(M.PlanAction, obj.plan_action_id) if obj.plan_action_id else None)
                        if plan is not None:
                            plans[id(plan)] = plan; touches.add(id(plan))
                elif isinstance(obj, M.PlanAction):
                    if _change(obj, 'pourcentage_realisation') or _change(obj, 'statut'):
                        plans[id(obj)] = obj
                elif hasattr(M, 'PlanActionC2N') and isinstance(obj, M.PlanActionC2N):
                    if _change(obj, 'taux_avancement') or _change(obj, 'statut'):
                        termine, rouvert = _regler_plan_n2(obj)
                        if obj.recommandation_id:
                            _suivre_reco(session, M, obj, termine, rouvert)
            for obj in list(session.deleted):
                if isinstance(obj, M.SousAction) and obj.plan_action is not None and obj.plan_action not in session.deleted:
                    plans[id(obj.plan_action)] = obj.plan_action; touches.add(id(obj.plan_action))
            for k, plan in plans.items():
                termine, rouvert = _regler_plan(session, plan, k in touches)
                if plan.recommandation_id or getattr(plan, 'recommandation_c2n_id', None):
                    _suivre_reco(session, M, plan, termine, rouvert)
            for obj in list(session.dirty):
                if isinstance(obj, M.Recommandation) and _change(obj, 'statut'):
                    if (obj.statut == 'termine') != (_avant(obj, 'statut') == 'termine'):
                        _suivre_constatation(session, M, obj)
    except Exception as e:  # noqa: BLE001  — une règle de suivi ne doit jamais empêcher l'enregistrement
        journal.warning('Suivi des plans d\'action non appliqué : %s', e, exc_info=True)


def _proteger(app, endpoint):
    """Ces deux actions n'exigeaient que d'être connecté : on exige le droit de modifier le plan,
    comme pour la progression (current_user.can_edit_plan)."""
    vue = app.view_functions.get(endpoint)
    if vue is None or getattr(vue, '_egalyx_droit_plan', False):
        return
    from functools import wraps

    @wraps(vue)
    def protegee(sous_action_id, *a, **k):
        import models as M
        from flask import abort, jsonify, request
        from flask_login import current_user
        sa = M.db.session.get(M.SousAction, sous_action_id)
        if sa is None:
            abort(404)
        plan = sa.plan_action
        try:
            permis = plan is not None and current_user.can_edit_plan(plan)
        except Exception:  # noqa: BLE001
            permis = False
        if not permis:
            if request.headers.get('X-Requested-With') or request.is_json:
                return jsonify({'success': False, 'error': 'Permission refusée'}), 403
            abort(403)
        return vue(sous_action_id, *a, **k)
    protegee._egalyx_droit_plan = True
    app.view_functions[endpoint] = protegee


def enregistrer(app):
    for endpoint in ('modifier_statut_sous_action', 'supprimer_sous_action'):
        _proteger(app, endpoint)
    if _INSTALLE:
        return
    from sqlalchemy.orm import Session
    event.listen(Session, 'before_flush', _avant_ecriture)
    _INSTALLE.append(True)
