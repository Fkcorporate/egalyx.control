"""
egalyx/recherche.py — recherche globale (Ctrl+K) dans les données de l'organisation.
GET /api/recherche?q=texte  ->  {"resultats": [{type, titre, sous_titre, url}]}
"""
from flask import Blueprint, current_app, jsonify, request, url_for

from egalyx.commun import a_permission, client_id_courant, connexion_requise

bp = Blueprint('recherche', __name__)

# (libellé, modèle, champs cherchés, champ titre, champ sous-titre, endpoint, nom du paramètre d'URL, filtre archivé)
SOURCES = [
    ('Risque', 'Risque', ('reference', 'intitule', 'categorie'), 'intitule', 'reference', 'detail_risque', 'id', 'is_archived'),
    ('Audit', 'Audit', ('reference', 'titre'), 'titre', 'reference', 'detail_audit', 'id', 'is_archived'),
    ("Plan d'action", 'PlanAction', ('reference', 'nom'), 'nom', 'reference', 'detail_plan_action', 'plan_id', 'is_archived'),
    ('Incident', 'Incident', ('reference', 'titre'), 'titre', 'reference', 'detail_incident', 'id', 'is_archived'),
    ('Tiers', 'Tiers', ('reference', 'nom', 'sigle'), 'nom', 'reference', 'tiers.detail', 'tid', 'is_archived'),
    ('Processus', 'Processus', ('nom',), 'nom', 'statut', 'detail_processus', 'id', None),
    ('KRI', 'KRI', ('nom',), 'nom', 'unite_mesure', 'detail_kri', 'kri_id', None),
    ('Cartographie', 'Cartographie', ('nom',), 'nom', 'type_cartographie', 'detail_cartographie', 'id', 'is_archived'),
]
PAR_SOURCE = 6
# On ne cherche que dans les modules que l'utilisateur a le droit de voir
PERMISSIONS = {
    'Risque': ('can_manage_risks', 'can_validate_risks', 'can_confirm_evaluations'),
    'Cartographie': ('can_manage_risks', 'can_validate_risks', 'can_confirm_evaluations'),
    'Audit': ('can_manage_audit', 'can_manage_audit_program', 'can_view_reports'),
    "Plan d'action": ('can_manage_action_plans', 'can_view_action_plans'),
    'Incident': ('can_manage_incidents', 'can_view_incidents'),
    'Tiers': ('can_view_tiers', 'can_manage_tiers'),
    'Processus': ('can_manage_logigram',),
    'KRI': ('can_manage_kri',),
}


def rechercher(cid, texte):
    texte = (texte or '').strip()
    if len(texte) < 2 or not cid:
        return []
    import models
    from sqlalchemy import or_
    motif = f'%{texte}%'
    resultats = []
    for libelle, nom_modele, champs, titre, sous_titre, endpoint, param, archive in SOURCES:
        if not a_permission(*PERMISSIONS.get(libelle, ('__aucune__',))):
            continue
        modele = getattr(models, nom_modele, None)
        if modele is None or not hasattr(modele, 'client_id'):
            continue
        try:
            q = modele.query.filter(modele.client_id == cid)
            if archive and hasattr(modele, archive):
                q = q.filter(getattr(modele, archive) == False)  # noqa: E712
            q = q.filter(or_(*[getattr(modele, c).ilike(motif) for c in champs if hasattr(modele, c)]))
            for o in q.limit(PAR_SOURCE).all():
                try:
                    url = url_for(endpoint, **{param: o.id})
                except Exception:
                    continue
                resultats.append({'type': libelle, 'titre': str(getattr(o, titre, '') or '')[:140],
                                  'sous_titre': str(getattr(o, sous_titre, '') or ''), 'url': url})
        except Exception as e:
            current_app.logger.warning("Recherche %s : %s", nom_modele, e)
    return resultats


@bp.route('/api/recherche')
@connexion_requise
def api():
    return jsonify({'resultats': rechercher(client_id_courant(), request.args.get('q'))})


def enregistrer(app):
    app.register_blueprint(bp)
