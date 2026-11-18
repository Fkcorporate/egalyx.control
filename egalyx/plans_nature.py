"""
egalyx/plans_nature.py — chaque plan d'action reste dans SON module (audit, risque, indépendant).

Les plans d'audit, de risque et indépendants sont stockés dans la même table (PlanAction) ; seule l'origine
change (audit_id, risque_id, aucun des deux). Plusieurs écrans envoyaient pourtant n'importe quel plan vers
les pages des risques : un plan d'audit s'ouvrait sur « Plan d'action risque », avec le fil d'Ariane des
cartographies, et le bouton Retour menait aux plans des risques.

Ce module :
  - donne la nature d'un plan et le lien de SA fiche (nature_plan / lien_plan, aussi dans les gabarits) ;
  - redirige une fiche ouverte par la mauvaise adresse vers la bonne (GET seulement, même organisation ;
    sinon la page d'origine applique ses propres contrôles) ;
  - fournit à l'espace de travail commun le fil d'Ariane et le retour propres à la nature du plan.
Règle identique à la liste des plans : audit si le plan est lié à un audit, sinon risque s'il est lié à un
risque, sinon indépendant.
"""
import logging

from flask import redirect, request, url_for

journal = logging.getLogger('egalyx.plans_nature')

FICHE = {'audit': 'detail_plan_action', 'risque': 'detail_plan_action_risque',
         'independant': 'detail_plan_action_independant'}
LIBELLE = {'audit': "Plan d'action d'audit", 'risque': "Plan d'action du risque", 'independant': "Plan d'action indépendant"}


def nature_plan(plan):
    if plan is None:
        return 'independant'
    if getattr(plan, 'audit_id', None):
        return 'audit'
    if getattr(plan, 'risque_id', None):
        return 'risque'
    return 'independant'


def lien_plan(plan):
    return url_for(FICHE[nature_plan(plan)], plan_id=plan.id)


def liste_plans(plan):
    """Où revenir depuis la fiche d'un plan : la liste de son module."""
    n = nature_plan(plan)
    if n == 'audit':
        return url_for('liste_plans_action', type='audit')
    if n == 'risque':
        return url_for('voir_plans_action_risque', risque_id=plan.risque_id)
    return url_for('liste_plans_action_independants')


def fil_ariane(plan):
    """[(libellé, lien)] du module du plan, pour l'espace de travail commun."""
    n = nature_plan(plan)
    if n == 'audit':
        f = [("Audits", url_for('liste_audits')), ("Plans d'action d'audit", url_for('liste_plans_action', type='audit'))]
        if getattr(plan, 'audit', None) is not None:
            f.insert(1, (plan.audit.reference or plan.audit.titre or 'Audit', url_for('detail_audit', id=plan.audit_id)))
        return f
    if n == 'risque':
        f = [("Cartographies", url_for('liste_cartographies'))]
        r = getattr(plan, 'risque', None)
        if r is not None and getattr(r, 'cartographie', None) is not None:
            f.append((r.cartographie.nom, url_for('detail_cartographie', id=r.cartographie_id)))
        if r is not None:
            f.append((r.reference, url_for('detail_risque', id=plan.risque_id)))
        return f
    return [("Plans d'action indépendants", url_for('liste_plans_action_independants'))]


# endpoint consulté -> natures qu'il sait afficher
PAGES = {
    'detail_plan_action_risque': {'risque'},
    'modifier_plan_action_risque': {'risque'},
    'detail_plan_action': {'audit', 'independant'},       # indépendants : ancien comportement gardé
    'afficher_modifier_plan_action': {'audit', 'independant'},
    'espace_travail_plan_action': {'audit', 'risque'},      # espace commun : en-tête adapté à la nature
}
CIBLE = {
    'detail_plan_action_risque': FICHE,
    'detail_plan_action': FICHE,
    'modifier_plan_action_risque': {'audit': 'afficher_modifier_plan_action', 'independant': 'modifier_plan_action_independant'},
    'afficher_modifier_plan_action': {'risque': 'modifier_plan_action_risque'},
    'espace_travail_plan_action': {'independant': 'espace_travail_plan_action_independant'},
}


def _rediriger():
    if request.method != 'GET' or request.endpoint not in PAGES:
        return None
    plan_id = (request.view_args or {}).get('plan_id')
    if not plan_id:
        return None
    try:
        import models as M
        from flask_login import current_user
        if not getattr(current_user, 'is_authenticated', False):
            return None
        plan = M.db.session.get(M.PlanAction, plan_id)
        if plan is None:
            return None
        if getattr(current_user, 'role', None) != 'super_admin' and plan.client_id != getattr(current_user, 'client_id', None):
            return None             # autre organisation : la page d'origine refuse elle-même
        n = nature_plan(plan)
        if n in PAGES[request.endpoint]:
            return None
        cible = CIBLE[request.endpoint].get(n)
        if not cible:
            return None
        from flask import current_app
        if cible not in current_app.view_functions:
            return None
        return redirect(url_for(cible, plan_id=plan.id))
    except Exception as e:  # noqa: BLE001
        journal.warning("Aiguillage du plan d'action %s impossible : %s", plan_id, e)
        return None


def enregistrer(app):
    app.before_request(_rediriger)
    app.jinja_env.globals.update(nature_plan=nature_plan, lien_plan=lien_plan, liste_plans_du_plan=liste_plans,
                                 fil_ariane_plan=fil_ariane, LIBELLE_NATURE_PLAN=LIBELLE)
