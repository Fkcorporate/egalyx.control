"""
egalyx/dossier_fige.py — dossier de mission figé après le rapport définitif (normes IIA : documentation des missions).

Une fois le rapport définitif émis (egalyx/audit_plus.py), plus aucune modification du dossier de mission :
  - feuilles de travail, tests, erreurs, références croisées, versions, commentaires de revue, preuves ;
  - constats (modification, suppression, statut, preuves), nouvelles recommandations, équipe, risques associés ;
  - fiche de l'audit (modification, suppression), circuit de revue.
Restent possibles : le suivi des recommandations et des plans d'action, le temps passé (activité de suivi),
le dépôt du rapport signé, la clôture/archivage de l'audit, les demandes de réévaluation des risques.

Réouverture : un gestionnaire de l'audit peut rouvrir le dossier avec un motif (journalisé, notifié à l'équipe),
puis le figer de nouveau. Pendant la réouverture, chaque modification reste tracée par le journal habituel.

Contrôle unique, avant chaque requête d'écriture : on retrouve l'audit concerné à partir des paramètres de
l'adresse (audit, feuille, test, erreur, référence, commentaire, constat) et on refuse si le dossier est figé.
"""
from datetime import datetime

from flask import Blueprint, abort, flash, jsonify, redirect, request, url_for
from flask_login import current_user, login_required

from egalyx.commun import journaliser

bp = Blueprint('dossier_fige', __name__, url_prefix='/audit-suivi')

ECRITURES = {'POST', 'PUT', 'PATCH', 'DELETE'}
MOTIF_MIN = 15
MESSAGE = ("Le rapport définitif est émis : le dossier de mission est figé. "
           "Un gestionnaire de l'audit peut le rouvrir avec un motif (fiche de l'audit → « Constats et réponses »).")

# Écritures toujours permises sur un dossier figé (suivi après rapport, dépôt du rapport signé, clôture…)
AUTORISES = {
    'audit_plus.temps', 'audit_plus.reponses',          # temps de suivi ; les réponses ont leur propre contrôle
    'dossier_fige.rouvrir', 'dossier_fige.figer', 'satisfaction_audit.questionnaire',   # avis des audités : après le rapport
    'changer_statut_audit', 'archive_audit', 'restaurer_audit',
    'upload_fichier_rapport_audit', 'upload_fichier_rapport',
    'nouveau_plan_action', 'nouvel_plan_action', 'supprimer_plan_action_audit', 'associer_risques_plan_action',
    'demander_reevaluation_constat', 'demander_reevaluation_risque', 'demander_nouveau_risque_audit',
    'regenerer_alertes_approbation', 'api_ajouter_favori_feuille', 'test_reevaluation_simple',
    'api_envoyer_lettre_mission', 'api_envoyer_lettre_mission_email', 'lettre_mission.route_envoyer',
    'api_exporter_lettre_word', 'api_calculer_progression_reelle',
}
# Routes dont le paramètre « id » désigne l'audit
AUDIT_PAR_ID = {'edit_audit', 'supprimer_audit'}


def _m():
    import models
    return models


def est_fige(audit):
    return audit is not None and audit.etat_rapport == 'definitif' and audit.dossier_rouvert_le is None


def audit_concerne(endpoint, va, corps=None):
    """Audit visé par une requête, d'après ses paramètres d'adresse (None si la requête ne vise pas un audit)."""
    m = _m()
    s = m.db.session
    va = va or {}
    if 'audit_id' in va and not endpoint.startswith(('modifier_audit_qualite', 'ajouter_non_conformite_qualite',
                                                      'repondre_audit_qualite', 'supprimer_audit_qualite')):
        return s.get(m.Audit, va['audit_id'])
    if endpoint in AUDIT_PAR_ID and 'id' in va:
        return s.get(m.Audit, va['id'])
    feuille_id = va.get('feuille_id')
    if feuille_id is None and 'test_id' in va:
        t = s.get(m.TestControleFeuille, va['test_id'])
        feuille_id = t.feuille_travail_id if t else None
    if feuille_id is None and 'erreur_id' in va:
        e = s.get(m.ErreurTest, va['erreur_id'])
        t = s.get(m.TestControleFeuille, e.test_id) if e else None
        feuille_id = t.feuille_travail_id if t else None
    if feuille_id is None and 'reference_id' in va:
        r = s.get(m.ReferenceCroiseeFeuille, va['reference_id'])
        feuille_id = r.feuille_travail_id if r else None
    if feuille_id is None and 'commentaire_id' in va and request.path.startswith('/api/feuille-travail/commentaire/'):
        c = s.get(m.CommentaireFeuille, va['commentaire_id'])
        feuille_id = c.feuille_travail_id if c else None
    if feuille_id is not None:
        f = s.get(m.FeuilleTravail, feuille_id)
        return s.get(m.Audit, f.audit_id) if f and f.audit_id else None
    cid = va.get('constatation_id', va.get('constat_id'))
    if cid is not None:
        c = s.get(m.Constatation, cid)
        return s.get(m.Audit, c.audit_id) if c and c.audit_id else None
    if corps and isinstance(corps, dict) and corps.get('audit_id'):
        try:
            return s.get(m.Audit, int(corps['audit_id']))
        except (TypeError, ValueError):
            return None
    return None


def _refus():
    veut_json = (request.path.startswith('/api/') or request.is_json
                 or 'application/json' in (request.headers.get('Accept') or '')
                 or request.headers.get('X-Requested-With') == 'XMLHttpRequest')
    if veut_json:
        return jsonify({'success': False, 'error': MESSAGE, 'message': MESSAGE, 'dossier_fige': True}), 423
    flash(MESSAGE, 'warning')
    retour = request.referrer
    if not retour or not retour.startswith(request.host_url):
        retour = '/'
    return redirect(retour)


def controler():
    if request.method not in ECRITURES or not request.endpoint or request.endpoint in AUTORISES:
        return None
    if request.endpoint.startswith(('static', 'dossier_fige.')):
        return None
    try:
        corps = request.get_json(silent=True) if request.endpoint == 'api_creer_constat_depuis_ia' else None
        a = audit_concerne(request.endpoint, request.view_args, corps)
    except Exception:
        return None             # le contrôle d'accès habituel de la route s'appliquera
    if not est_fige(a):
        return None
    # Audit d'une autre organisation : on laisse la route répondre (404/403) sans rien révéler de son état.
    from egalyx.commun import client_id_courant
    if getattr(current_user, 'role', None) != 'super_admin' and a.client_id != client_id_courant():
        return None
    return _refus()


# ---------------------------------------------------------------- réouverture
def _charger(audit_id):
    from egalyx.audit_plus import charger_audit, est_gestionnaire_audit
    a = charger_audit(audit_id)
    if not est_gestionnaire_audit():
        abort(403)
    return a


@bp.route('/<int:audit_id>/dossier/rouvrir', methods=['POST'])
@login_required
def rouvrir(audit_id):
    from egalyx.audit_plus import _notifier, equipe
    m = _m()
    a = _charger(audit_id)
    retour = redirect(url_for('audit_plus.reponses', audit_id=a.id))
    if a.etat_rapport != 'definitif':
        flash("Le dossier n'est figé qu'après le rapport définitif.", 'info')
        return retour
    motif = ' '.join((request.form.get('motif') or '').split())
    if len(motif) < MOTIF_MIN:
        flash(f'Indiquez le motif de la réouverture ({MOTIF_MIN} caractères au moins) : il est conservé au dossier.', 'warning')
        return retour
    a.dossier_rouvert_le, a.dossier_rouvert_par_id, a.dossier_rouvert_motif = datetime.utcnow(), current_user.id, motif[:500]
    _notifier(equipe(a), f'Dossier rouvert : {a.reference}',
              f"Le dossier de l'audit « {a.titre} » a été rouvert après le rapport définitif. Motif : {motif[:300]}", a)
    m.db.session.commit()
    journaliser('audit_dossier_rouvert', {'audit_id': a.id, 'motif': motif[:500]}, valider=True)
    flash('Dossier rouvert : les modifications sont de nouveau possibles. Pensez à le figer une fois la correction faite.', 'warning')
    return retour


@bp.route('/<int:audit_id>/dossier/figer', methods=['POST'])
@login_required
def figer(audit_id):
    m = _m()
    a = _charger(audit_id)
    retour = redirect(url_for('audit_plus.reponses', audit_id=a.id))
    if a.dossier_rouvert_le is None:
        return retour
    duree = datetime.utcnow() - a.dossier_rouvert_le
    a.dossier_rouvert_le = a.dossier_rouvert_par_id = None
    m.db.session.commit()
    journaliser('audit_dossier_refige', {'audit_id': a.id, 'motif_reouverture': a.dossier_rouvert_motif,
                                         'duree_minutes': int(duree.total_seconds() // 60)}, valider=True)
    flash('Dossier de nouveau figé.', 'success')
    return retour


def enregistrer(app):
    from egalyx.commun import exempter_controle_ancien
    app.register_blueprint(bp)
    exempter_controle_ancien(app, {'dossier_fige.rouvrir', 'dossier_fige.figer'})
    app.before_request(controler)
    app.jinja_env.globals['dossier_fige'] = est_fige
