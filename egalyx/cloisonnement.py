"""
egalyx/cloisonnement.py — cloisonnement des données entre organisations, pour TOUTES les routes.

Avant chaque requête d'un utilisateur connecté (hors super admin ; les opérateurs, rattachés à un client, sont contrôlés),
chaque identifiant présent dans l'URL (/audit/<audit_id>, /constatation/<id>…) est résolu vers
l'objet que la route va charger ; si cet objet appartient à une autre organisation, la requête
est refusée (404, sans révéler que l'objet existe).

- Correspondance route -> modèle : extraite du code de chaque route (cloisonnement_carte.py),
  complétée par le nom du paramètre (audit_id -> Audit…).
- Organisation d'un objet : sa colonne client_id, sinon celle de son parent (clé étrangère),
  récursivement : constatation -> audit -> organisation, étape -> processus -> organisation…
- Objet dont l'organisation est indéterminable : laissé passer (la route garde ses propres contrôles).

Second contrôle — droits d'écriture : une requête qui MODIFIE des données (POST, PUT, PATCH, DELETE)
dans un module (audit, processus, campagnes, plans d'action…) exige l'une des permissions de ce
module (voir modules_client.CATALOGUE) ou d'être la personne en charge de l'élément visé
(responsable, créateur, évaluateur désigné). Les opérateurs ont leurs propres permissions et ne
sont pas concernés. Chaque refus est journalisé.

Désactivation d'urgence : EGALYX_CLOISONNEMENT=0 (isolation) ou EGALYX_DROITS_ECRITURE=0 (écriture).
"""
import logging
import os

from flask import abort, jsonify, request
from flask_login import current_user

from egalyx.cloisonnement_carte import CARTE

journal = logging.getLogger('egalyx.cloisonnement')

PAR_NOM = {
    'audit_id': 'Audit', 'risque_id': 'Risque', 'cartographie_id': 'Cartographie', 'carto_id': 'Cartographie',
    'processus_id': 'Processus', 'activite_id': 'ProcessusActivite', 'constatation_id': 'Constatation',
    'constat_id': 'Constatation', 'recommandation_id': 'Recommandation', 'feuille_id': 'FeuilleTravail',
    'kri_id': 'KRI', 'mesure_id': 'MesureKRI', 'incident_id': 'Incident', 'dispositif_id': 'DispositifMaitrise',
    'veille_id': 'VeilleReglementaire', 'direction_id': 'Direction', 'pole_id': 'Pole', 'pays_id': 'Pays',
    'service_id': 'Service', 'element_id': 'ElementLogigramme', 'programme_id': 'ProgrammeAudit',
    'user_id': 'User', 'auditeur_id': 'User', 'ticket_id': 'TicketSupport', 'questionnaire_id': 'Questionnaire',
}
# Clés étrangères à ne pas suivre pour trouver l'organisation (référentiels partagés, auteurs…)
NE_PAS_SUIVRE = {'user', 'clients', 'formules_abonnement', 'secteurs_activite', 'categories', 'auteurs'}
PROFONDEUR = 4


def _modeles():
    import models
    from models import db
    par_nom, par_table = {}, {}
    for mapper in db.Model.registry.mappers:
        cls = mapper.class_
        par_nom[cls.__name__] = cls
        par_table[getattr(cls, '__tablename__', None)] = cls
    return models, db, par_nom, par_table


def client_de(obj, db, par_table, profondeur=PROFONDEUR):
    """Organisation propriétaire d'un objet (None si indéterminable)."""
    if obj is None or profondeur < 0:
        return None
    if type(obj).__name__ == 'Client':
        return obj.id
    cid = getattr(obj, 'client_id', None)
    if cid is not None:
        return cid
    table = getattr(obj, '__table__', None)
    if table is None:
        return None
    for fk in table.foreign_keys:
        cible = fk.column.table.name
        if cible in NE_PAS_SUIVRE:
            continue
        valeur = getattr(obj, fk.parent.key, None)
        modele = par_table.get(cible)
        if valeur is None or modele is None:
            continue
        parent = db.session.get(modele, valeur)
        cid = client_de(parent, db, par_table, profondeur - 1)
        if cid is not None:
            return cid
    return None


def modele_pour(endpoint, param, par_nom):
    nom = CARTE.get(endpoint, {}).get(param) or PAR_NOM.get(param)
    return par_nom.get(nom) if nom else None


ECRITURE = {'POST', 'PUT', 'PATCH', 'DELETE'}
# Actions déclenchées par un simple lien (GET) qui modifient pourtant des données : traitées comme des écritures.
ACTIONS_PAR_LIEN = {'cloturer_campagne_cartographie', 'cloturer_campagne_specifique', 'changer_campagne_cartographie',
                    'convertir_mission_audit'}
# Modules où une permission de consultation suffit pour écrire (chacun peut ouvrir un ticket de support, etc.)
ECRITURE_PAR_CONSULTATION = {'support', 'pilotage'}
CHAMPS_RESPONSABLE = ('responsable_id', 'created_by', 'createur_id', 'referent_pre_evaluation_id', 'evaluateur_final_id',
                      'responsable_resolution_id', 'responsable_mesure_id', 'auditeur_id', 'utilisateur_id', 'user_id',
                      'evaluateur_id', 'valideur_id', 'controleur_id', 'validateur_requis_id',
                      'superviseur_id', 'directeur_id')


def _dans_liste(valeur, uid):
    return bool(valeur) and str(uid) in [x.strip() for x in str(valeur).split(',')]


def _est_en_charge(obj, uid):
    """Responsable, créateur ou évaluateur désigné de l'élément ; membre de l'équipe de l'audit concerné ;
    référent d'une évaluation en cours du risque concerné."""
    if obj is None:
        return False
    if any(getattr(obj, c, None) == uid for c in CHAMPS_RESPONSABLE):
        return True
    audit = obj if type(obj).__name__ == 'Audit' else getattr(obj, 'audit', None)
    if audit is None and getattr(obj, 'feuille_travail', None) is not None:
        audit = getattr(obj.feuille_travail, 'audit', None)
    if audit is not None:
        if any(getattr(audit, c, None) == uid for c in ('responsable_id', 'created_by')):
            return True
        if any(_dans_liste(getattr(audit, c, None), uid) for c in ('equipe_audit_ids', 'participants_ids')):
            return True
    if type(obj).__name__ == 'Risque':
        try:
            from models import EvaluationRisque
            return EvaluationRisque.query.filter(
                EvaluationRisque.risque_id == obj.id,
                (EvaluationRisque.referent_pre_evaluation_id == uid) | (EvaluationRisque.validateur_id == uid)
                | (EvaluationRisque.evaluateur_final_id == uid)).first() is not None
        except Exception:
            return False
    return False


def _refus(message, code=403):
    from flask import flash, redirect, url_for
    if request.path.startswith('/api/') or request.is_json or 'application/json' in (request.headers.get('Accept') or ''):
        return jsonify({'success': False, 'error': message}), code
    flash(message, 'warning')
    return redirect(request.referrer or url_for('dashboard'))


def controler():
    if not getattr(current_user, 'is_authenticated', False) or getattr(current_user, 'role', None) == 'super_admin':
        return None
    if os.environ.get('EGALYX_CLOISONNEMENT', '1') != '1' or not request.view_args:
        return droits_ecriture([])
    mon_client = getattr(current_user, 'client_id', None)
    _m, db, par_nom, par_table = _modeles()
    objets = []
    for param, valeur in request.view_args.items():
        if not isinstance(valeur, int):
            continue
        modele = modele_pour(request.endpoint, param, par_nom)
        if modele is None:
            continue
        try:
            obj = db.session.get(modele, valeur)
            objets.append(obj)
            proprietaire = client_de(obj, db, par_table)
        except Exception as e:      # ne jamais bloquer à cause d'une erreur de résolution
            journal.warning("Cloisonnement : %s %s=%s non résolu (%s)", request.endpoint, param, valeur, e)
            continue
        if proprietaire is not None and proprietaire != mon_client:
            journal.warning("Accès refusé : utilisateur %s (organisation %s) -> %s %s=%s (organisation %s)",
                            getattr(current_user, 'id', '?'), mon_client, request.endpoint, param, valeur, proprietaire)
            if request.path.startswith('/api/') or request.is_json or 'application/json' in (request.headers.get('Accept') or ''):
                return jsonify({'success': False, 'error': 'Introuvable'}), 404
            abort(404)
    return droits_ecriture(objets)


def droits_ecriture(objets):
    """Écriture dans un module : permission de GESTION du module, ou personne en charge de l'élément visé.
    Une permission de consultation (« voir les rapports », « voir les campagnes »…) ne suffit plus pour modifier.
    Les opérateurs n'écrivent que par leurs propres pages (operateur_…) ou sur ce dont ils ont la charge."""
    if os.environ.get('EGALYX_DROITS_ECRITURE', '1') != '1':
        return None
    if request.method not in ECRITURE and request.endpoint not in ACTIONS_PAR_LIEN:
        return None
    if not request.endpoint or '.' in request.endpoint:
        return None
    if getattr(current_user, 'is_operateur', False) and request.endpoint.startswith('operateur_'):
        return None              # pages opérateur : chacune vérifie déjà que la campagne / l'action lui est confiée
    from egalyx.questionnaires_publics import REGLES as REPONSES_PUBLIQUES
    if request.url_rule is not None and request.url_rule.rule in REPONSES_PUBLIQUES:
        return None            # répondre à un questionnaire n'exige pas de gérer les questionnaires
    from egalyx.commun import a_permission
    from egalyx.modules_client import MODULES, module_de_la_requete
    module = module_de_la_requete(request.endpoint, request.path)
    if module is None:
        return None
    toutes = MODULES[module][4]
    gestion = toutes if module in ECRITURE_PAR_CONSULTATION else \
        tuple(p for p in toutes if not p.startswith(('can_view_', 'can_export_'))) or toutes
    if a_permission(*gestion):
        return None
    if any(_est_en_charge(o, current_user.id) for o in objets):
        return None
    journal.warning("Écriture refusée : utilisateur %s (rôle %s) -> %s %s (module %s)", current_user.id,
                    getattr(current_user, 'role', '?'), request.method, request.endpoint, module)
    return _refus(f"Vous n'avez pas la permission de modifier des données du module « {MODULES[module][1]} ». "
                  "Demandez-la à l'administrateur de votre organisation.")


def enregistrer(app):
    app.before_request(controler)
