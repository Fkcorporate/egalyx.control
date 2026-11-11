"""
egalyx/maitrise.py — dispositifs de maîtrise (DMR) et plans d'action des risques.

1. Droits identiques sur toutes les pages (avant : deux permissions inexistantes, « can_manage_plans » et
   « can_manage_controls », impossibles à accorder ; seul le CRÉATEUR pouvait modifier un plan ou un dispositif ;
   et n'importe quel membre, opérateurs compris, lisait dispositifs, plans et statistiques) :
     dispositifs   voir  = droits de la cartographie (gérer / valider / confirmer les risques), ou responsable
                           ou créateur du dispositif
                   tester = gérer les risques, ou responsable du dispositif (vérifications, documents)
                   gérer  = « Gérer les risques » (créer, modifier, évaluer l'efficacité, statut, archiver, liens)
     plans risque  voir  = voir / gérer les plans d'action, ou gérer les risques, ou responsable / créateur du plan
                   suivre = gérer les plans d'action ou les risques, ou responsable / créateur (statut, avancement,
                           sous-actions, terminer)
                   gérer  = « Gérer les plans d'action » ou « Gérer les risques » (modifier, réattribuer, archiver,
                           supprimer)
2. Vérification d'un dispositif : « Non conforme » baisse l'efficacité de 2 points, « À corriger » ou « À améliorer »
   d'1 point (minimum 1), avec historique ; le niveau de maîtrise suggéré des évaluations en cours du risque est
   recalculé, ce qui déclenche l'alerte d'écart. Prochaine vérification selon la fréquence du dispositif (au lieu
   de 6 mois pour tous) ; 30 jours après une vérification défavorable.
3. « Ma semaine » : dispositifs à vérifier (responsable, ou gestionnaires des risques pour ceux sans responsable).
"""
import sys
from datetime import date, datetime, timedelta

from flask import flash, has_request_context, jsonify, redirect, request, url_for
from flask_login import current_user

from egalyx.commun import a_permission, est_admin_client

CARTO = ('can_manage_risks', 'can_validate_risks', 'can_confirm_evaluations')
RISQUES = ('can_manage_risks',)
PLANS_VOIR = ('can_view_action_plans', 'can_manage_action_plans', 'can_manage_risks')
PLANS_GERER = ('can_manage_action_plans', 'can_manage_risks')

DROITS = {
    # dispositifs
    'liste_dispositifs_risque': 'd_voir', 'detail_dispositif': 'd_voir', 'api_statistiques_dispositif': 'd_voir',
    'telecharger_document_dispositif': 'd_voir', 'stress_test_dispositif': 'd_voir', 'benchmark_dispositifs': 'd_voir',
    'exporter_rapport_dispositifs': 'd_voir', 'api_dispositifs_a_verifier': 'd_voir',
    'api_stats_globales_dispositifs': 'd_voir', 'api_liste_dispositifs': 'd_voir', 'api_plan_dispositifs': 'p_voir',
    'formulaire_verification_dispositif': 'd_tester', 'api_formulaire_verification': 'd_tester',
    'ajouter_verification_dispositif': 'd_tester', 'formulaire_document_dispositif': 'd_tester',
    'uploader_document_dispositif': 'd_tester',
    'nouveau_dispositif': 'd_gerer', 'modifier_dispositif': 'd_gerer', 'evaluer_dispositif': 'd_gerer',
    'changer_statut_dispositif': 'd_gerer', 'archiver_dispositif': 'd_gerer', 'desarchiver_dispositif': 'd_gerer',
    'dispositifs_archives': 'd_gerer', 'supprimer_document_dispositif': 'd_gerer', 'api_detacher_plan': 'd_gerer',
    'lier_dispositif_plan_action': 'd_gerer', 'api_creer_plan_action_dispositif': 'd_gerer',
    'supprimer_definitivement_dispositif': 'd_supprimer',
    # plans d'action des risques
    'detail_plan_action_risque': 'p_voir', 'progression_detail_plan_risque': 'p_voir', 'progression_detail_plan': 'p_voir',
    'changer_statut_plan_risque_rapide': 'p_suivre', 'changer_statut_plan_rapide': 'p_suivre',
    'changer_statut_plan_risque': 'p_suivre', 'changer_progression_plan': 'p_suivre',
    'set_progression_fixe_plan': 'p_suivre', 'reorganiser_sous_actions_risque': 'p_suivre',
    'nouveau_sous_action_risque': 'p_suivre', 'terminer_plan_complet_risque': 'p_suivre',
    'modifier_plan_action_risque': 'p_gerer_ou_responsable', 'changer_responsable_plan_rapide': 'p_gerer',
    'archiver_plan_risque': 'p_gerer', 'desarchiver_plan_risque': 'p_gerer', 'archiver_plan_action_risque': 'p_gerer',
    'desarchiver_plan_action_risque': 'p_gerer', 'supprimer_plan_risque': 'p_gerer',
    'supprimer_plan_action_risque': 'p_gerer',
    # sous-actions des plans de risque (droits du plan parent ; le responsable de la sous-action peut la modifier)
    'modifier_sous_action_risque': 'p_suivre', 'supprimer_sous_action_risque': 'p_suivre',
    # plans d'action indépendants (même règle que les plans des risques)
    'modifier_plan_action_independant': 'p_gerer_ou_responsable', 'archiver_plan_action_independant': 'p_gerer',
    'desarchiver_plan_action_independant': 'p_gerer', 'nouveau_sous_action_independant': 'p_suivre',
}

# Efficacité retirée selon le résultat d'une vérification ; délai avant la prochaine vérification
BAISSE_EFFICACITE = {'Non conforme': 2, 'À corriger': 1, 'À améliorer': 1}
JOURS_PROCHAINE_VERIFICATION = {'Permanent': 90, 'Quotidien': 90, 'Hebdomadaire': 90, 'Mensuel': 90,
                                'Trimestriel': 180, 'Semestriel': 365, 'Annuel': 365, 'Exceptionnel': 365}
JOURS_APRES_ECHEC = 30


def _m():
    import models
    return models


def _super(u):
    return getattr(u, 'role', None) == 'super_admin'


def _meme_org(obj, u):
    return obj is not None and (_super(u) or getattr(obj, 'client_id', None) == getattr(u, 'client_id', None))


def _nomme(obj, u):
    uid = getattr(u, 'id', None)
    return bool(obj is not None and uid and uid in (getattr(obj, 'responsable_id', None), getattr(obj, 'created_by', None)))


# ---------------------------------------------------------------- dispositifs
def peut_voir_dispositif(d, u=None):
    u = u or current_user
    return _super(u) or (_meme_org(d, u) if d is not None else True) and (a_permission(*CARTO, u=u) or _nomme(d, u))


def peut_tester_dispositif(d, u=None):
    u = u or current_user
    if _super(u):
        return True
    if d is not None and not _meme_org(d, u):
        return False
    return a_permission(*RISQUES, u=u) or (d is not None and getattr(d, 'responsable_id', None) == getattr(u, 'id', None))


def peut_gerer_dispositif(d=None, u=None):
    u = u or current_user
    if _super(u):
        return True
    if d is not None and not _meme_org(d, u):
        return False
    return a_permission(*RISQUES, u=u)


# ---------------------------------------------------------------- plans d'action des risques
def peut_voir_plan(p, u=None):
    u = u or current_user
    if _super(u):
        return True
    if p is not None and not _meme_org(p, u):
        return False
    return a_permission(*PLANS_VOIR, u=u) or _nomme(p, u)


def peut_suivre_plan(p, u=None):
    u = u or current_user
    if _super(u):
        return True
    if p is not None and not _meme_org(p, u):
        return False
    return a_permission(*PLANS_GERER, u=u) or _nomme(p, u)


def peut_gerer_plan(p=None, u=None):
    u = u or current_user
    if _super(u):
        return True
    if p is not None and not _meme_org(p, u):
        return False
    return a_permission(*PLANS_GERER, u=u)


def _objet_requete():
    m = _m()
    va = request.view_args or {}
    if 'dispositif_id' in va:
        return m.db.session.get(m.DispositifMaitrise, va['dispositif_id'])
    if 'doc_id' in va and hasattr(m, 'DocumentDispositif'):
        doc = m.db.session.get(m.DocumentDispositif, va['doc_id'])
        return m.db.session.get(m.DispositifMaitrise, doc.dispositif_id) if doc else None
    if 'plan_id' in va:
        return m.db.session.get(m.PlanAction, va['plan_id'])
    if 'sous_action_id' in va and hasattr(m, 'SousAction'):
        sa = m.db.session.get(m.SousAction, va['sous_action_id'])
        return getattr(sa, 'plan_action', None) if sa else None
    return None


def droit(endpoint=None):
    """Remplace les anciens contrôles « can_manage_plans » / « can_manage_controls » (inexistants) d'app.py."""
    endpoint = endpoint or (request.endpoint if has_request_context() else None)
    niveau = DROITS.get(endpoint)
    if niveau is None:
        return True
    obj = _objet_requete()
    if niveau == 'd_voir':
        return peut_voir_dispositif(obj)
    if niveau == 'd_tester':
        return peut_tester_dispositif(obj)
    if niveau == 'd_gerer':
        return peut_gerer_dispositif(obj)
    if niveau == 'd_supprimer':
        return peut_gerer_dispositif(obj) and (est_admin_client() or _super(current_user))
    if niveau == 'p_voir':
        return peut_voir_plan(obj)
    if niveau == 'p_suivre':
        return peut_suivre_plan(obj)
    if niveau == 'p_gerer_ou_responsable':
        return peut_gerer_plan(obj) or (obj is not None and _meme_org(obj, current_user) and _nomme(obj, current_user))
    if niveau == 'p_gerer':
        return peut_gerer_plan(obj)
    return False


def _garde():
    ep = request.endpoint or ''
    if ep not in DROITS:
        return None
    if not getattr(current_user, 'is_authenticated', False) or _super(current_user):
        return None
    if droit(ep):
        return None
    dispositif = DROITS[ep].startswith('d_')
    message = ("Vous n'avez pas la permission nécessaire pour ce dispositif de maîtrise."
               if dispositif else "Vous n'avez pas la permission nécessaire pour ce plan d'action.")
    if request.path.startswith('/api/') or request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest' \
            or 'application/json' in (request.headers.get('Accept') or '') or request.method == 'DELETE':
        return jsonify({'success': False, 'error': message}), 403
    flash(message, 'warning')
    return redirect(request.referrer or url_for('dashboard'))


# ---------------------------------------------------------------- vérifications
def calculer_dmr(dispositifs):
    """Même formule que la fiche risque : 60 % efficacité + 40 % couverture, pondérée par type de dispositif."""
    mod = sys.modules.get('app') or sys.modules.get('__main__')
    f = getattr(mod, 'calculer_maitrise_depuis_dmr', None)
    if callable(f):
        return f(dispositifs)
    poids_type = {'Préventif': 1.0, 'Détectif': 0.8, 'Correctif': 0.6, 'Dirigeant': 0.9}
    total, poids_total = 0, 0
    for d in dispositifs:
        if getattr(d, 'is_archived', False) or not d.efficacite_reelle:
            continue
        poids = poids_type.get(d.type_dispositif, 0.7)
        total += (d.efficacite_reelle * 0.6 + (d.couverture or 0) * 0.4) * poids
        poids_total += poids
    return round(total / poids_total, 2) if poids_total else None


def recalculer_maitrise_suggeree(risque_id):
    """Met à jour le niveau suggéré par les dispositifs (et l'écart) sur les évaluations non confirmées du risque."""
    m = _m()
    if not risque_id:
        return
    dispositifs = m.DispositifMaitrise.query.filter_by(risque_id=risque_id).all()
    niveau = calculer_dmr(dispositifs)
    for e in m.EvaluationRisque.query.filter(m.EvaluationRisque.risque_id == risque_id,
                                             m.EvaluationRisque.date_confirmation.is_(None)).all():
        e.niveau_maitrise_dmr = niveau
        saisi = e.niveau_maitrise_conf or e.niveau_maitrise_val or e.niveau_maitrise_pre
        e.ecart_maitrise = abs(float(saisi) - float(niveau)) if (niveau is not None and saisi) else None


def apres_verification(dispositif, resultat, date_verif, verificateur_id=None):
    """Appelée après l'enregistrement d'une vérification (app.py)."""
    m = _m()
    jours = JOURS_APRES_ECHEC if resultat in BAISSE_EFFICACITE else \
        JOURS_PROCHAINE_VERIFICATION.get(dispositif.frequence or '', 180)
    dispositif.prochaine_verification = date_verif + timedelta(days=jours)
    baisse = BAISSE_EFFICACITE.get(resultat)
    if baisse and dispositif.efficacite_reelle:
        avant = dispositif.efficacite_reelle
        dispositif.efficacite_reelle = max(1, int(avant) - baisse)
        if dispositif.efficacite_reelle != avant:
            m.db.session.add(m.DispositifHistoriqueEfficacite(
                dispositif_id=dispositif.id, efficacite=dispositif.efficacite_reelle, ancienne_efficacite=avant,
                reduction=avant - dispositif.efficacite_reelle, cause='verification', date_changement=datetime.utcnow(),
                commentaire=f"Vérification du {date_verif.strftime('%d/%m/%Y')} : {resultat}."))
    recalculer_maitrise_suggeree(dispositif.risque_id)


# ---------------------------------------------------------------- « Ma semaine »
def taches(u, ajout, horizon, aujourd_hui, lien):
    m = _m()
    if not u.client_id:
        return
    gerer = a_permission(*RISQUES, u=u)
    q = m.DispositifMaitrise.query.filter(m.DispositifMaitrise.client_id == u.client_id,
                                          m.DispositifMaitrise.is_archived.isnot(True),
                                          m.DispositifMaitrise.prochaine_verification.isnot(None),
                                          m.DispositifMaitrise.prochaine_verification <= horizon)
    for d in q.all():
        if d.responsable_id == u.id or (gerer and not d.responsable_id):
            ajout('Dispositif à vérifier', d.nom, f'{d.reference} · {d.frequence or "fréquence ?"}',
                  d.prochaine_verification, lien('detail_dispositif', dispositif_id=d.id))


# ---------------------------------------------------------------- comparatif des dispositifs
def benchmark(client_id=None):
    """Indicateurs du tableau de pilotage des dispositifs (/dispositifs/benchmark et son rapport) : la page
    appelait DispositifMaitrise.get_benchmark_dispositifs, qui n'existait pas (erreur à chaque ouverture)."""
    m = _m()
    q = m.DispositifMaitrise.query.filter(m.DispositifMaitrise.is_archived.isnot(True))
    if client_id:
        q = q.filter(m.DispositifMaitrise.client_id == client_id)
    tous = q.all()
    evalues = [d for d in tous if d.efficacite_reelle]
    couverts = [d for d in tous if d.couverture]
    reductions = []
    for d in evalues:
        try:
            reductions.append(float(d.get_reduction_risque_detaille()['reduction_finale']))
        except Exception:  # noqa: BLE001
            pass
    par_type = {}
    for d in tous:
        cle = d.type_dispositif or 'Non précisé'
        par_type[cle] = par_type.get(cle, 0) + 1
    moyenne = lambda v: round(sum(v) / len(v), 1) if v else 0  # noqa: E731
    return {
        'total': len(tous),
        'total_actifs': sum(1 for d in tous if (d.statut or '').lower() in ('actif', 'active', 'en_place', 'opérationnel')),
        'efficacite_moyenne': moyenne([d.efficacite_reelle for d in evalues]),
        'couverture_moyenne': moyenne([d.couverture for d in couverts]),
        'reduction_moyenne': moyenne(reductions),
        'par_type': par_type,
        'a_verifier': sum(1 for d in tous if d.prochaine_verification and d.prochaine_verification <= date.today()),
    }


def enregistrer(app):
    m = _m()
    if not hasattr(m.DispositifMaitrise, 'get_benchmark_dispositifs'):
        m.DispositifMaitrise.get_benchmark_dispositifs = staticmethod(lambda client_id=None: benchmark(client_id))
    from egalyx.commun import exempter_controle_ancien
    exempter_controle_ancien(app, DROITS)
    app.before_request(_garde)
    app.jinja_env.globals.update(dmr_peut_gerer=peut_gerer_dispositif, dmr_peut_tester=peut_tester_dispositif,
                                 plan_risque_peut_gerer=peut_gerer_plan, plan_risque_peut_suivre=peut_suivre_plan)
